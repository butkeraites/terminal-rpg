"""Quest board + quest visibility, status, rewards, and triggers.

Extracted from ``locations.py`` during the v2.3 quality audit. Everything
quest-related on the bookkeeping side lives here:

  * ``_quest_status`` — available / active / completable / claimed
  * ``_hidden_quest_trigger_holds`` / ``scan_hidden_quest_triggers`` —
    Batch-7 hidden quest plumbing (zone_visited, mark_fired, flag_set)
  * ``_quest_category`` / ``_group_catalog_by_category`` — Batch-9 board
    UI grouping (Bounties / Chains / Special)
  * ``_apply_quest_rewards`` — the extended reward schema (consumables,
    marks, chronicle_line, ending_unlock)
  * ``_run_composition_quest`` — the melody-quest dispatch handler
  * ``_quest_is_visible`` / ``_quests_newly_visible`` — visibility gates
    (cleanse, level, class, flag, mark, ending, discovery)
  * ``quest_board`` — the Gravewatch quest board service itself

The cluster is re-exported by ``locations.py`` so existing code that
wrote ``locations.quest_board`` or ``locations.scan_hidden_quest_triggers``
keeps working unchanged.
"""

from __future__ import annotations
from . import chronicle, composer, marks
from .combat import CLASS_CONSUMABLE
from .ui import hud


# ── Status ─────────────────────────────────────────────────────────────


def _quest_status(state, quest_id):
    """Return one of: 'available', 'active', 'completable', 'claimed'."""
    if quest_id in state.flags.get("completed_quests", []):
        return "claimed"
    if quest_id not in state.flags.get("active_quests", []):
        return "available"
    progress = state.flags.get("quest_progress", {}).get(quest_id, 0)
    if progress >= state.content.quests[quest_id]["needed"]:
        return "completable"
    return "active"


# --- Phase-1 Batch-7: hidden quest triggers ------------------------------
#
# Hidden quests live in content.quests with ``hidden: true`` and a
# ``trigger_action: {type, params}``. They never appear on the board until
# the trigger fires. When it does, the quest is auto-pinned to active_quests
# and a small notification shows. The scanner runs at zone_arrival (inside
# try_travel) and save_action (inside _save_menu).


def _hidden_quest_trigger_holds(state, trigger):
    """Return True if the given trigger predicate currently holds.

    Vocabulary shipping in Batch-7 (more types will be added in future
    batches as their hooks become non-invasive to wire):

      - ``zone_visited``   {zone_id} — player is currently in this zone
      - ``mark_fired``     {mark_id} — this mark is in player.marks
      - ``flag_set``       {flag_name} — state.flags[flag_name] is truthy

    Unknown trigger types never fire; the schema validator doesn't enforce
    the vocabulary yet (so authoring batches stay flexible), but the
    runtime is conservative.
    """
    if not trigger:
        return False
    ttype = trigger.get("type")
    params = trigger.get("params") or {}
    if ttype == "zone_visited":
        return state.current_location == params.get("zone_id")
    if ttype == "mark_fired":
        return params.get("mark_id") in (getattr(state.player, "marks", []) or [])
    if ttype == "flag_set":
        return bool(state.flags.get(params.get("flag_name")))
    return False


def scan_hidden_quest_triggers(state):
    """Pin hidden quests whose trigger has fired. Idempotent.

    Called at zone_arrival and save_action. A quest already in
    active_quests or completed_quests is skipped — the scan only ever
    promotes a NEW hidden quest from invisible-and-untriggered to
    pinned-and-active.
    """
    quests = state.content.quests
    active = state.flags.get("active_quests", []) or []
    completed = state.flags.get("completed_quests", []) or []
    triggered_now = []
    for qid, quest in quests.items():
        if not quest.get("hidden"):
            continue
        if qid in active or qid in completed:
            continue
        if _hidden_quest_trigger_holds(state, quest.get("trigger_action") or {}):
            state.flags.setdefault("active_quests", []).append(qid)
            state.flags.setdefault("quest_progress", {}).setdefault(qid, 0)
            triggered_now.append((qid, quest))
    for _qid, quest in triggered_now:
        state.io.show_slow(
            f"\n📜 A slip appears in your hand: {quest['name']}.")
        if quest.get("flavor"):
            state.io.show(f"   {quest['flavor']}")
    return [qid for qid, _ in triggered_now]


# --- Phase-1 Batch-9: board UI categorization -----------------------------
#
# A flat catalog works fine for the 6 cleanse-gated bounties. At the
# 2000-quest design horizon, players need visual grouping to navigate.
# The board now groups visible quests into three buckets — Bounties,
# Chains, Special — with headers above each, while the numbering stays
# sequential across the whole list (player UX unchanged: pick a number).

_QUEST_CATEGORY_ORDER = ("bounty", "chain", "special")
_QUEST_CATEGORY_HEADERS = {
    "bounty":  "── Bounties ──",
    "chain":   "── Chains ──",
    "special": "── Special ──",
}


def _quest_category(quest):
    """Return one of 'bounty' / 'chain' / 'special' for the board UI.

    Heuristic:
      * 'chain'   — has any chain-shape field (requires_quest, denies_quest,
                    or chain_next).
      * 'special' — has any "rare-condition" gate or unusual completion:
                    requires_mark(s), requires_class, requires_ending,
                    requires_discovery, requires_chronicle_entry,
                    completion_condition, or any reward_* field beyond
                    the default gold+consumable.
      * 'bounty'  — everything else (the cleanse-gated kill/trophy basics).

    A quest can match multiple heuristics; the FIRST match wins in
    chain → special → bounty order. This is deliberate: chains are
    structurally distinctive; specials are *content*-distinctive;
    bounties are the rest.
    """
    if (quest.get("requires_quest")
            or quest.get("denies_quest")
            or quest.get("chain_next")):
        return "chain"
    if (quest.get("requires_mark")
            or quest.get("requires_marks")
            or quest.get("requires_class")
            or quest.get("requires_ending")
            or quest.get("requires_discovery")
            or quest.get("requires_chronicle_entry")
            or quest.get("completion_condition")
            or quest.get("reward_consumables")
            or quest.get("reward_marks")
            or quest.get("reward_chronicle_line")
            or quest.get("reward_ending_unlock")):
        return "special"
    return "bounty"


def _group_catalog_by_category(catalog):
    """Order ``catalog`` (list of (qid, quest)) by category.

    Within each category, original ordering is preserved.
    Returns a list of (category_label, qid, quest) tuples in display order.
    """
    by_cat = {cat: [] for cat in _QUEST_CATEGORY_ORDER}
    for qid, quest in catalog:
        by_cat[_quest_category(quest)].append((qid, quest))
    rows = []
    for cat in _QUEST_CATEGORY_ORDER:
        if not by_cat[cat]:
            continue
        rows.append(("__header__", cat, None))
        for qid, quest in by_cat[cat]:
            rows.append((cat, qid, quest))
    return rows


# ── Rewards & composition-quest dispatch ───────────────────────────────


def _apply_quest_rewards(state, quest):
    """Phase-1 Batch-8: dispatch every reward_* field on a just-claimed quest.

    The default reward — ``reward_gold`` + a class-themed consumable — is
    applied inline in ``quest_board()`` so the existing 6 bounties retain
    their exact behaviour. This function adds the optional reward fields:

      * ``reward_consumables`` — append each named consumable to player.consumables
      * ``reward_marks``       — fire each named mark (engine: marks.fire_mark)
      * ``reward_chronicle_line`` — display the line now AND store it for
                                    Batch-10 to write into the player's
                                    Chronicle entry on fall / Warden.
      * ``reward_ending_unlock`` — append the ending id to chronicle.unlocks

    Order: consumables, marks, chronicle_line, ending_unlock. The order
    is intentional so a mark that, say, sets a flag is fired before the
    Chronicle line is composed.
    """
    io = state.io
    # 1) Consumables
    for cons in (quest.get("reward_consumables") or []):
        state.player.consumables.append(cons)
        io.show(f"   +1 {cons}")
    # 2) Marks
    for mark_id in (quest.get("reward_marks") or []):
        mark = state.content.marks.get(mark_id)
        if mark is None:
            continue
        # fire_mark prints its own narrative; we don't double-announce.
        marks.fire_mark(state, mark)
    # 3) Chronicle line — store for later, also show now.
    line = quest.get("reward_chronicle_line")
    if line:
        state.flags.setdefault("quest_chronicle_lines", []).append(line)
        io.show(f"   ✒ Chronicle: {line}")
    # 4) Ending unlock
    ending = quest.get("reward_ending_unlock")
    if ending:
        chronicle.unlock(ending, state.chronicle_dir)
        io.show(f"   ✦ A path opens: {ending}")


def _run_composition_quest(state, arg):
    """Dispatch handler for the "compose" menu option.

    Runs the composer flow; on success, applies the quest's rewards inline
    so the player doesn't walk back to the quest board for a melody quest.
    No automatic class consumable on success — the composition is the
    reward; combat loot would feel like an apology for the kindness.
    """
    qid, quest = arg
    if not composer.compose(state, quest):
        return  # the player walked away
    io = state.io
    player = state.player
    # Move from active to completed
    if qid in state.flags.get("active_quests", []):
        state.flags["active_quests"].remove(qid)
    state.flags.setdefault("completed_quests", []).append(qid)
    # Optional gold — melody quests typically set this to zero
    gold = quest.get("reward_gold", 0)
    if gold:
        player.gold += gold
        io.show(f"\n   +{gold} gold")
    # Extended rewards — consumables, marks, chronicle_line, ending_unlock
    _apply_quest_rewards(state, quest)
    io.pause(2)


# ── Visibility gates ───────────────────────────────────────────────────


def _quest_is_visible(quest, state, cleanses):
    """Return True if this quest should appear on the board for this player.

    Phase-1 gates honoured here:
      Batch-1 / -3 — cleanse_required, requires_quest, denies_quest.
      Batch-4    — min_level, requires_class, requires_flag(s),
                   requires_mark(s), requires_ending.

    Hidden quests (``hidden: true``) never show up regardless — they wait
    for an explicit trigger (Batch-7).
    """
    if quest.get("hidden"):
        return False
    if quest.get("cleanse_required", 0) > cleanses:
        return False

    # Chain gates (Batch-3)
    completed = set(state.flags.get("completed_quests", []))
    needs = quest.get("requires_quest") or []
    if needs and not all(qid in completed for qid in needs):
        return False
    denies = quest.get("denies_quest") or []
    if any(qid in completed for qid in denies):
        return False

    # Level gate (Batch-4)
    min_level = quest.get("min_level")
    if min_level is not None and state.player.level < min_level:
        return False

    # Class gate (Batch-4)
    classes = quest.get("requires_class") or []
    if classes and state.player.class_id not in classes:
        return False

    # Flag gates (Batch-4) — single string and list-of-strings both supported.
    rflag = quest.get("requires_flag")
    if rflag and not state.flags.get(rflag):
        return False
    for f in (quest.get("requires_flags") or []):
        if not state.flags.get(f):
            return False

    # Mark gates (Batch-4) — read from player.marks (a list).
    player_marks = set(getattr(state.player, "marks", []) or [])
    rmark = quest.get("requires_mark")
    if rmark and rmark not in player_marks:
        return False
    for m in (quest.get("requires_marks") or []):
        if m not in player_marks:
            return False

    # Ending gate (Batch-4) — Chronicle's endings_seen across runs.
    endings_needed = quest.get("requires_ending") or []
    if endings_needed:
        seen = chronicle.endings_seen(state.chronicle_dir)
        if not all(eid in seen for eid in endings_needed):
            return False

    # Discovery gate (Batch-5) — state.flags['discoveries_seen'] tracks which
    # lore fragments the player has read this run. Discovery-gated quests
    # appear once the prerequisite reading has happened.
    discoveries_needed = quest.get("requires_discovery") or []
    if discoveries_needed:
        seen = set(state.flags.get("discoveries_seen", []))
        if not all(did in seen for did in discoveries_needed):
            return False

    return True


def _quests_newly_visible(state, cleanses, just_completed_id):
    """Return quest_ids that become visible *because* just_completed_id was claimed.

    A quest is *newly visible* if it was hidden before the claim (because
    just_completed_id was not yet in completed_quests) but is visible after.
    Used to render the chain-step notification on claim.
    """
    quests = state.content.quests
    newly = []
    for qid, q in quests.items():
        if qid == just_completed_id:
            continue
        needs = q.get("requires_quest") or []
        if just_completed_id not in needs:
            continue
        # Was visible without the just-completed prereq? If yes, not newly.
        # We test that by checking visibility now, then removing the
        # just-completed from completed_quests temporarily.
        if _quest_is_visible(q, state, cleanses):
            completed = set(state.flags.get("completed_quests", []))
            others = completed - {just_completed_id}
            if not all(n in others for n in needs):
                newly.append(qid)
    return newly


# ── The board ─────────────────────────────────────────────────────────


def quest_board(state):
    """The Gravewatch quest board: pick up bounty quests, claim rewards on completion.

    Higher-tier bounties are gated by cleanse count — the Board only pins a
    new slip after each successful run, so deeper quests open as the realm
    is cleansed. Chain quests (Phase-1 Batch-3) are gated by requires_quest:
    a follow-up slip stays off the board until its prerequisite is claimed.
    """
    player, io = state.player, state.io
    cleanses = chronicle.cleanses(state.chronicle_dir)
    io.clear()
    io.show_slow("📜 The Quest Board — slips of vellum pinned with rust nails.\n")
    while True:
        # Rebuild catalog every loop so chain steps that just opened on a
        # claim appear without needing to leave and re-enter.
        catalog = [(qid, q) for qid, q in state.content.quests.items()
                   if _quest_is_visible(q, state, cleanses)]
        # Phase-1 Batch-9: group the catalog by category for navigation at
        # the 2000-quest horizon. Numbering stays sequential across the
        # whole list — `selectable` is the index→(qid, quest) mapping the
        # input parser uses.
        grouped = _group_catalog_by_category(catalog)
        selectable = []  # [(qid, quest), ...] in display order
        io.show(hud(player))
        for row in grouped:
            if row[0] == "__header__":
                _cat = row[1]
                io.show(f"\n{_QUEST_CATEGORY_HEADERS[_cat]}")
                continue
            _cat, quest_id, quest = row
            selectable.append((quest_id, quest))
            index = len(selectable)
            status = _quest_status(state, quest_id)
            progress = state.flags.get("quest_progress", {}).get(quest_id, 0)
            # Phase-1 Batch-2: trophy-target quests display their trophy
            # name in the progress tag, not target_enemy.
            target_label = (quest.get("target_enemy")
                            or quest.get("target_trophy")
                            or "?")
            tag = {
                "available":   f"[{quest['reward_gold']}g + a class flask]",
                "active":      f"[{progress}/{quest['needed']} {target_label}s]",
                "completable": "[READY TO CLAIM]",
                "claimed":     "[done]",
            }[status]
            io.show(f"\n{index}. {quest['name']}  {tag}")
            io.show(f"   {quest.get('flavor', '')}")
        io.show(f"\n{len(selectable) + 1}. Leave")
        choice = io.ask("\nWhat would you like? ")
        if choice == str(len(selectable) + 1):
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(selectable)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        quest_id, quest = selectable[int(choice) - 1]
        status = _quest_status(state, quest_id)
        if status == "available":
            state.flags.setdefault("active_quests", []).append(quest_id)
            state.flags.setdefault("quest_progress", {})[quest_id] = 0
            io.show_slow(f"\n📜 You take the slip: {quest['name']}.")
            io.pause(1)
        elif status == "active":
            tcomp = quest.get("target_composition")
            if tcomp is not None:
                altar_loc = state.content.locations.get(tcomp["altar"], {})
                altar_name = altar_loc.get("name", tcomp["altar"])
                io.show(f"\nNot finished yet — compose at {altar_name} "
                        f"when you're ready.")
            else:
                progress = state.flags["quest_progress"][quest_id]
                target_label = (quest.get("target_enemy")
                                or quest.get("target_trophy")
                                or "?")
                io.show(f"\nNot finished yet: {progress}/{quest['needed']} "
                        f"{target_label}s.")
            io.pause(1)
        elif status == "completable":
            player.gold += quest["reward_gold"]
            consumable = CLASS_CONSUMABLE.get(player.class_id)
            if consumable is not None:
                player.consumables.append(consumable)
            state.flags["active_quests"].remove(quest_id)
            state.flags.setdefault("completed_quests", []).append(quest_id)
            io.show_slow("\n📜 The Board takes the slip back, marked done.")
            io.show(f"   +{quest['reward_gold']} gold")
            if consumable is not None:
                io.show(f"   +1 {consumable}")
            # Phase-1 Batch-8: optional reward fields (consumables, marks,
            # chronicle line, ending unlock). Default reward stays inline
            # above; this dispatches the extended schema.
            _apply_quest_rewards(state, quest)
            # Phase-1 Batch-3: chain forward — if claiming this quest opens
            # any follow-up slip, tell the player so they don't have to
            # leave-and-reenter to notice.
            newly = _quests_newly_visible(state, cleanses, quest_id)
            for nqid in newly:
                nq = state.content.quests[nqid]
                io.show_slow(f"\n📜 A new slip is pinned: {nq['name']}.")
            # chain_next is a forward-pointer hint. If the author set it but
            # the next slip is gated by something else (e.g. min_level),
            # _quests_newly_visible already filtered it out. We trust that
            # filtering and only emit on truly-visible follow-ups.
            io.pause(2)
        else:  # claimed
            io.show("\nAlready claimed. The Board has no other use for you.")
            io.pause(1)

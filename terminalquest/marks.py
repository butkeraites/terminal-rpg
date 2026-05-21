"""The Marks system — irreversible, per-character events.

A "mark" is something that happens to the player exactly once, mid-run, and
cannot be undone. The user's framing: *no turning point decisions* — if it
happens, it happens; only this character experiences it; the next character
will not.

The system is **save-scum proof** by design. When a mark fires, the engine:

1. Adds the mark id to ``player.marks``.
2. Applies the mark's mechanical effect to the player (stat ±, flag set,
   consumable added, future encounter unlocked/locked).
3. Writes the mark id to a sidecar file ``~/.terminalquest/marks/{run_id}.json``
   BEFORE printing any narrative text.
4. Returns. The text is shown to the player AFTER the disk write.

If the player reloads an older save, the engine reads the sidecar on
``Player.from_dict`` and merges the recorded marks back in — so the mark
persists across reloads of the same character. When the character dies
(or the player chooses Reborn), the sidecar is deleted.

Marks live in ``data/marks.json``. Each entry is a dict with these fields::

    {
      "id":             unique mark id (string),
      "category":       one of forgetting | body | mind | bond | broken |
                        found | lost | promise_kept | promise_broken | half_truth,
      "trigger": {
        "at":           one or more fire-site keys (zone_arrival, combat_victory,
                        combat_low_hp, defend_action, save_action, discovery_read,
                        ...) — empty means "any site",
        "location":     optional list of location ids the mark may fire at,
        "min_level":    optional player-level gate,
        "min_visits":   optional zone-visits-this-run gate,
        "requires_flag":     optional flag id the player must have set,
        "denies_mark":  optional list of mark ids that block this one,
        "chance":       float 0..1 — base roll chance per check
      },
      "effect": null | {
        "stat":         optional ("max_hp" | "attack" | "defense" | "max_stamina"),
        "delta":        signed integer to add to that stat,
        "flag":         optional state flag id to set
      },
      "lines": [ "first narrative line", ... ]
    }

The engine is intentionally small. It does one thing: when invoked at a
fire-site, it rolls the mark pool, picks at most one, and applies it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_MARKS_DIRNAME = "marks"


def marks_dir(chronicle_dir):
    """Return (and create) the per-run marks sidecar directory.

    Stored alongside the chronicle so it shares the same hermetic location
    contract (``~/.terminalquest/``). One file per active run_id.
    """
    path = Path(chronicle_dir) / _MARKS_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sidecar_path(chronicle_dir, run_id):
    return marks_dir(chronicle_dir) / f"{run_id}.json"


def load_sidecar(chronicle_dir, run_id):
    """Read the run's sidecar marks list. Never raises."""
    path = _sidecar_path(chronicle_dir, run_id)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("marks", []))
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return []


def write_sidecar(chronicle_dir, run_id, mark_ids):
    """Write the run's sidecar marks list atomically.

    This is the **save-scum guard**: by the time this returns, the disk
    record of the fired mark exists. The player cannot undo by reloading
    an earlier save (because ``Player.from_dict`` will merge this list
    back into player.marks).
    """
    path = _sidecar_path(chronicle_dir, run_id)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps({"marks": list(mark_ids)}),
                       encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def clear_sidecar(chronicle_dir, run_id):
    """Delete the sidecar — called when the character dies or is Reborn."""
    path = _sidecar_path(chronicle_dir, run_id)
    try:
        path.unlink()
    except OSError:
        pass


def merge_sidecar_into_player(player, chronicle_dir):
    """At save-load time, fold sidecar marks back into ``player.marks``.

    A reloaded save has whatever marks were in the saved dict. The sidecar
    has whatever marks have fired during the actual run so far. Their union
    is the truth. This is the mechanism by which reloading a pre-mark save
    still produces a marked character — the disk remembers what the save
    forgot.
    """
    if not getattr(player, "run_id", None):
        return
    sidecar = load_sidecar(chronicle_dir, player.run_id)
    if not sidecar:
        return
    existing = set(player.marks)
    for mark_id in sidecar:
        if mark_id not in existing:
            player.marks.append(mark_id)
            existing.add(mark_id)


def eligible(state, mark, fire_site):
    """Return True if ``mark`` may roll at this fire-site for this state."""
    if mark["id"] in state.player.marks:
        return False
    trigger = mark.get("trigger", {})
    sites = trigger.get("at") or []
    if sites and fire_site not in sites:
        return False
    locs = trigger.get("location") or []
    if locs and state.current_location not in locs:
        return False
    min_level = trigger.get("min_level")
    if min_level is not None and state.player.level < min_level:
        return False
    min_visits = trigger.get("min_visits")
    if min_visits is not None:
        visits = state.flags.get("zone_visits", {}).get(state.current_location, 0)
        if visits < min_visits:
            return False
    requires_flag = trigger.get("requires_flag")
    if requires_flag and not state.flags.get(requires_flag):
        return False
    denies = trigger.get("denies_mark") or []
    for blocker in denies:
        if blocker in state.player.marks:
            return False
    return True


# --- Effects -------------------------------------------------------------

# Effect application is intentionally minimal — marks are not abilities,
# they are weather. The full mechanical vocabulary is small because most
# of the depth comes from the narrative lines, not the numerical changes.
def apply_effect(state, mark):
    """Apply the mark's mechanical effect to the player (no narrative)."""
    effect = mark.get("effect") or {}
    if not effect:
        return
    stat = effect.get("stat")
    delta = effect.get("delta", 0)
    if stat and delta:
        current = getattr(state.player, stat, None)
        if current is not None:
            setattr(state.player, stat, max(1, current + delta))
            # Keep current values within bounds for max stats.
            if stat == "max_hp":
                state.player.hp = min(state.player.hp, state.player.max_hp)
            elif stat == "max_stamina":
                state.player.stamina = min(state.player.stamina,
                                            state.player.max_stamina)
    flag = effect.get("flag")
    if flag:
        state.flags[flag] = True
    consumable = effect.get("consumable")
    if consumable:
        state.player.consumables.append(consumable)


# --- Firing --------------------------------------------------------------

# v1.53 — per-fire-site BASE rate. The pool grows toward 1000; we cannot
# let a 1-5% per-mark chance compound to ~100% fire-on-every-arrival.
# Instead: gate at the fire-site first (BASE_RATE), THEN sample one mark
# from the eligible pool weighted by each mark's ``chance`` field. The
# per-mark ``chance`` becomes a relative weight, not an absolute probability.
#
# Target spread: a 30–50 fire-site run produces 5–15 marks total.
_BASE_RATES = {
    "zone_arrival":     0.10,
    "combat_victory":   0.08,
    "combat_low_hp":    0.20,  # the recklessness site, higher by design
    "save_action":      0.05,
    "discovery_read":   0.07,
}


def fire_mark(state, mark):
    """Apply the mark — *atomic save first*, then narrative.

    The order matters: by the time the player sees the first line, the
    disk already knows this mark fired. ALT-F4 in mid-text doesn't help.
    """
    state.player.marks.append(mark["id"])
    apply_effect(state, mark)
    write_sidecar(state.chronicle_dir, state.player.run_id, state.player.marks)

    io = state.io
    io.show("")
    io.show_slow("⊕ Atrél has received something.")
    for line in mark.get("lines", []):
        io.show_slow(line)
    io.show_slow("⊕ It is yours. Only yours. It will not happen to anyone else.")
    io.pause(2)


def roll_at(state, fire_site):
    """Roll the mark pool at the given fire site.

    Two-stage: first roll the per-fire-site BASE_RATE to decide whether
    ANY mark fires; if so, sample one from the eligible pool weighted by
    each mark's ``chance`` field. Returns the fired mark's id, or None.

    Cheap to call from any code path — the function is a no-op when the
    content has no marks pool loaded.
    """
    pool = getattr(state.content, "marks", None)
    if not pool:
        return None
    base = _BASE_RATES.get(fire_site, 0.05)
    rng = state.rng
    if rng.random() >= base:
        return None
    # Collect eligible marks with their weights. Sort by id so the
    # cumulative-weight selection is deterministic given the same RNG.
    eligible_marks = []
    weights = []
    cumulative = 0.0
    for mark in sorted(pool.values(), key=lambda m: m["id"]):
        if not eligible(state, mark, fire_site):
            continue
        weight = float(mark.get("trigger", {}).get("chance", 0.0))
        if weight <= 0:
            continue
        eligible_marks.append(mark)
        weights.append(weight)
        cumulative += weight
    if not eligible_marks:
        return None
    # Sample one via cumulative-weight walk. rng.random() ∈ [0,1).
    target = rng.random() * cumulative
    running = 0.0
    for mark, weight in zip(eligible_marks, weights):
        running += weight
        if target < running:
            fire_mark(state, mark)
            return mark["id"]
    # Numeric edge: pick the last one if floating-point pushed us past.
    chosen = eligible_marks[-1]
    fire_mark(state, chosen)
    return chosen["id"]


def describe(player, marks_pool):
    """Return a list of one-line summaries of the player's fired marks.

    Used by the character-sheet ``Marks`` section and the title screen's
    "marked by N" counter.
    """
    if not marks_pool:
        return []
    out = []
    for mark_id in player.marks:
        mark = marks_pool.get(mark_id)
        if not mark:
            out.append(f"  • (an unknown mark: {mark_id})")
            continue
        first_line = (mark.get("lines") or [""])[0]
        out.append(f"  • {first_line}")
    return out

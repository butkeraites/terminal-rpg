"""Explorable locations and the main game loop.

The world is a graph of locations loaded from ``data/locations.json``.
``location_loop`` is the central loop: it renders the player's current
location, offers its services, encounters and travel routes, and runs
until the player dies, wins, or quits.
"""
from . import banners as _banners
from . import chronicle, marks, saves
# Ending screens were extracted to endings_screens.py. Re-export every
# moved name so external callers (and tests) that wrote
# ``locations._warden_screen`` keep working. Importing this module also
# fires the endings.register calls at the bottom of endings_screens.
from .endings_screens import (  # noqa: F401
    PURIFY_CLEANSES_REQUIRED,
    REBORN_ECHO_BASE,
    REBORN_ECHO_PER_LEVEL,
    REBORN_ECHO_PER_UNLOCK,
    _atrel_peace_screen,
    _old_seal_screen,
    _other_mournhold_screen,
    _purify_screen,
    _reborn_screen,
    _reckoning_screen,
    _run_summary,
    _sister_realm_addendum,
    _victory_screen,
    _warden_screen,
)
# Side-quest services were extracted to sq_services.py. Re-export every
# moved name so external callers (and tests) that wrote `locations.reader`
# or `locations._pet_the_cat` keep working unchanged.
from .sq_services import (  # noqa: F401
    CARETAKER_THRESHOLD,
    CAT_PET_HEAL,
    CAT_PET_STAMINA,
    CAT_ZONE_VISITS_REQUIRED,
    INSOMNIAC_THRESHOLD,
    READER_THRESHOLD,
    _honor_the_dead,
    _maybe_open_border,
    _maybe_remember_verse,
    _maybe_wake_forgotten_thing,
    _pet_the_cat,
    _read_piranesi_map,
    _witnessed_dead_here,
    _write_first_line,
    caretaker,
    insomniac,
    reader,
    sing_the_verse,
    write_hearth_line,
)
# Quest helpers + the board itself moved to quests.py. Re-export every
# name so callers that wrote `locations.quest_board` or
# `locations.scan_hidden_quest_triggers` keep working.
from .quests import (  # noqa: F401
    _apply_quest_rewards,
    _group_catalog_by_category,
    _hidden_quest_trigger_holds,
    _quest_category,
    _quest_is_visible,
    _quest_status,
    _quests_newly_visible,
    _run_composition_quest,
    quest_board,
    scan_hidden_quest_triggers,
)
# Settlement vendors + combat services moved to vendors.py. Re-export
# functions AND pricing constants — the constants are also consumed by
# _SERVICE_LABELS f-strings just below.
from .vendors import (  # noqa: F401
    ATTACK_UPGRADE_GOLD_PER_POINT,
    DEFENSE_UPGRADE_GOLD_PER_POINT,
    GREATER_POTION_COST,
    INN_COST,
    NIGHT_HUNT_COST,
    NIGHT_HUNT_REWARD_MULT,
    NIGHT_HUNT_STAT_BOOST,
    PALL_DRINKER_COST,
    PALL_DRINKER_UNLOCK_CHAMPIONS,
    POTION_COST,
    SCHOLAR_PAYOUT,
    SOVEREIGN_POTION_COST,
    SOVEREIGN_UNLOCK_CHAMPIONS,
    SURVIVOR_CLEANSES_REQUIRED,
    SURVIVOR_STOCK,
    _buy_potion,
    _potion_label,
    _rest_at_inn,
    _run_service,
    beastmaster,
    echo_trader,
    hireling_hall,
    night_hunt,
    pact_broker,
    quartermaster,
    scholar,
    shop,
    smith,
    survivor,
)
# Encounter dispatch (combat / discovery / NPC / drops + Hollowed/Forsaken
# spawn machinery) moved to encounters.py. Re-export every name so external
# callers and tests that wrote `locations.run_encounter` or
# `locations._make_forsaken_sworn` keep working.
from .encounters import (  # noqa: F401
    ATREL_LORE_FRAGMENTS,
    FORSAKEN_CHANCE,
    HOLLOWED_CHANCE,
    WEAPON_DROP_CHANCE,
    _DISCOVERY_FLAGS,
    _HARDEST_GATE_NPCS,
    _entry_act,
    _hollowed_candidates,
    _make_forsaken_sworn,
    _maybe_open_hardest_gate,
    _npc_progress,
    _offer_drop,
    _run_discovery,
    _run_npc,
    run_encounter,
)
from .ui import hud, show_stats
from .weapon import WEAPON_SLOTS

SIGNPOST_THRESHOLD = 2


_SERVICE_LABELS = {
    "shop": "🏪 Visit the Shop",
    "inn": f"😴 Rest at the Inn ({INN_COST} gold)",
    "smith": "⚒  Visit the Smith",
    "quartermaster": "🛡️  Visit the Quartermaster",
    "pact_broker": "🐺 Visit the Pact-Broker",
    "echo_trader": "🕯️  Visit the Echo Trader",
    "night_hunt": f"🌑 Hunt at Night ({NIGHT_HUNT_COST} gold)",
    "quest_board": "📜 Read the Quest Board",
    "survivor": "🕊️  Speak with the Survivor",
    "beastmaster": "🐾 Visit the Beastmaster",
    "hireling_hall": "🛡️  Hire a Sworn",
    "scholar": "📚 Speak with the Mournhold Scholar",
    "reader": "📖 Read with the Reader",
    "insomniac": "🕯️  Sit with the Insomniac",
    "caretaker": "🌹 Become the Caretaker",
    "hearth_line": "📝 Write a line in the hearth-keeper's book",
}

# SQ1 — The Reader Who Watches Back surfaces in Gravewatch after this many
# unique lore discoveries have been read across all runs.

# SQ6 — The Insomniac of Gravewatch surfaces after this many cross-run visits.

# SQ2 — The Caretaker ending surfaces after this many small kindnesses.

# v1.2 — after this many cross-run visits to a zone, switch to its
# ``intro_familiar`` variant if defined: the kingdom starts speaking
# to the player in past-tense recognition instead of cold-open description.
FAMILIAR_VISITS = 5


# Reborn / Purify tuning constants live in endings_screens.py and are
# re-exported above for backwards compat.


# (Vendor services moved to terminalquest/vendors.py — re-exported at top.)


# (Encounter dispatch moved to terminalquest/encounters.py — re-exported at top.)


def try_travel(state, dest_id):
    """Travel to a connected location, applying gates and warnings.

    Returns True if the player travelled, False if blocked or turned back.
    """
    player, content, io = state.player, state.content, state.io
    dest = content.locations[dest_id]
    if dest.get("boss"):
        unlock = dest.get("unlock_level", 1)
        if player.level < unlock:
            io.show(f"\n🔒 {dest['name']} is sealed. "
                    f"Reach level {unlock} to challenge it.")
            io.pause(1)
            return False
    else:
        rec = dest.get("recommended_level", 1)
        if rec - player.level > SIGNPOST_THRESHOLD:
            io.show(f"\n⚠️  {dest['name']} is recommended for level {rec}+. "
                    f"At level {player.level}, this will be deadly.")
            io.show("1. Travel anyway")
            io.show("2. Turn back")
            if io.ask("\nYour choice? ") != "1":
                io.show("\nYou turn back, leaving that road for another day.")
                io.pause(1)
                return False
    state.current_location = dest_id
    # Phase-1 Batch-7: arrival into a new zone may trigger a hidden quest.
    scan_hidden_quest_triggers(state)
    return True


# (Ending screens moved to terminalquest/endings_screens.py — re-exported at top.)

def _save_menu(state):
    io = state.io
    saved = saves.list_saves()
    io.show("\nSave slots:")
    for slot in saves.SLOTS:
        io.show(f"{slot}. {saved.get(slot, '(empty)')}")
    io.show("4. Cancel")
    choice = io.ask("\nSave to which slot? ")
    if choice in ("1", "2", "3"):
        saves.save_game(state, int(choice))
        io.show(f"\n💾 Game saved to slot {choice}.")
        # v1.51 — saving is a fire site. Atrél is the kingdom's audit log.
        marks.roll_at(state, "save_action")
        # Phase-1 Batch-7: the saving sometimes reveals a slip.
        scan_hidden_quest_triggers(state)
    elif choice != "4":
        io.show("\n❌ Invalid choice!")
    io.pause(1)


def _encounter_label(encounter, content):
    """A menu label for one encounter.

    An encounter may carry an explicit ``label`` (mini-bosses, discoveries);
    otherwise a boss is named and a plain combat pool is 'Search for a fight'.
    """
    if "label" in encounter:
        return encounter["label"]
    if encounter.get("boss"):
        name = content.enemies[encounter["enemies"][0]]["name"]
        return f"⚔️  Challenge the {name}"
    return "⚔️  Search for a fight"


def _travel_label(dest, player):
    """A menu label for travelling to ``dest``, with gating annotations."""
    name = dest["name"]
    if dest.get("boss"):
        unlock = dest.get("unlock_level", 1)
        if player.level >= unlock:
            return f"⚔️  Travel to {name}  [BOSS]"
        return f"🔒 {name}  [BOSS — requires level {unlock}]"
    rec = dest.get("recommended_level")
    suffix = f"  (recommended Lv {rec})" if rec else ""
    return f"Travel to {name}{suffix}"


def _grave_here(state, loc, fallen):
    """True if this zone holds an unsearched grave from this act's fallen."""
    if loc.get("kind") != "zone" or loc.get("boss"):
        return False
    if state.current_location in state.flags.get("graves_searched", []):
        return False
    act = loc.get("act")
    return act is not None and any(_entry_act(state, e) == act for e in fallen)


def _search_grave(state, fallen):
    """Search the current zone for the remains of one who fell in this act."""
    player, io = state.player, state.io
    act = state.content.locations[state.current_location].get("act")
    entry = state.rng.choice([e for e in fallen if _entry_act(state, e) == act])
    p = entry["player"]
    fell_at = state.content.locations.get(entry.get("location", ""), {})
    place = fell_at.get("name", "the grey")
    io.show_slow(f"\n🪦 Half-buried in the grey earth: {p['name']} the {p['class_name']}.")
    io.show(f"{place} took them at level {p['level']}. It will take you too, in time.")
    # v1.16: a line they left behind, if they left one.
    last_words = entry.get("last_words", "")
    if last_words:
        io.show("")
        io.show_slow("A scrap of paper, folded once, weighted with a stone:")
        io.show_slow(f"   '{last_words}'")
    coins = min(p.get("gold", 0), 40)
    if coins:
        player.gold += coins
        io.show(f"You prise {coins} coins from the cold — they have no use for them now.")
    else:
        io.show("They left nothing behind. The dead here rarely do.")
    io.pause(1)
    state.flags.setdefault("graves_searched", []).append(state.current_location)


def _inspect_weapon(state):
    """Show the equipped weapon — its bonuses, and each component's flavor."""
    io, player = state.io, state.player
    weapon = player.equipment.get("weapon")
    io.clear()
    if weapon is None:
        io.show("\nYou carry no weapon. Your hands will have to do.")
        io.pause(1)
        return
    io.show(f"\n🗡️  {weapon.name}")
    io.show(f"   {weapon.summary()}\n")
    for slot in WEAPON_SLOTS:
        component = state.content.components[slot][weapon.components[slot]]
        io.show(f"  {slot.title()}: {component['name']}")
        io.show(f"    {component['flavor']}")
    io.pause(2)


# (SQ services moved to terminalquest/sq_services.py — re-exported at top.)


def _service_is_visible(state, service):
    """Some services are New Game Plus unlocks — hidden until the kingdom is cleansed.

    The Pact-Broker and the Echo Trader appear after the first ending. The
    Survivor (a deeper NG+ vendor) appears after the realm has been cleansed
    SURVIVOR_CLEANSES_REQUIRED times.
    """
    if service in ("pact_broker", "echo_trader"):
        return chronicle.has_completed_run(state.chronicle_dir)
    if service == "survivor":
        return chronicle.cleanses(state.chronicle_dir) >= SURVIVOR_CLEANSES_REQUIRED
    if service in ("beastmaster", "hireling_hall"):
        # Both pet + hireling unlock after the first run — but only while the
        # realm remains un-purified. They are the brother's "if you choose not
        # to save the world" rewards: the cycle continuing buys you more help.
        return (chronicle.has_completed_run(state.chronicle_dir)
                and not chronicle.purified(state.chronicle_dir))
    if service == "reader":
        # SQ1 — the Reader Who Watches Back surfaces once a completionist
        # threshold of cross-run lore reading has been crossed.
        return chronicle.discoveries_read(state.chronicle_dir) >= READER_THRESHOLD
    if service == "insomniac":
        # SQ6 — the Insomniac of Gravewatch surfaces after this many
        # cross-run visits to the village.
        return chronicle.gravewatch_visits(state.chronicle_dir) >= INSOMNIAC_THRESHOLD
    if service == "caretaker":
        # SQ2 — the Caretaker ending surfaces once enough kindnesses
        # have been done across all runs.
        return chronicle.kind_acts(state.chronicle_dir) >= CARETAKER_THRESHOLD
    return True


CAT_THRESHOLDS = (10, 25, 50, 100)


def _build_options(state, loc, fallen):
    """Build the ordered list of ``(label, (kind, arg))`` menu entries.

    v0.9 adds two flag-driven extensions: services unlocked by NPC quests
    (state.flags['unlocked_services'], e.g. the Scholar) and connections
    unlocked by NPC quests (state.flags['unlocked_connections'] — sub-zones
    that join the location graph once their gating NPC is satisfied).

    v0.15 adds the Recurring Cat: any kind=="zone" location visited
    CAT_ZONE_VISITS_REQUIRED+ times this run gains a "Pet the cat" option.
    """
    player, content = state.player, state.content
    options = []
    for service in loc.get("services", []):
        if not _service_is_visible(state, service):
            continue
        options.append((_SERVICE_LABELS[service], ("service", service)))
    # Services unlocked by NPC quests appear at all locations where they belong.
    for service in state.flags.get("unlocked_services", []):
        if (service in _SERVICE_LABELS
                and service in loc.get("npc_services", [])):
            options.append((_SERVICE_LABELS[service], ("service", service)))
    for encounter in loc.get("encounters", []):
        if (encounter["type"] == "discovery"
                and encounter["id"] in state.flags.get("discoveries_seen", [])):
            continue
        # Optional flag gating: an encounter can require a state flag to
        # appear (requires_flag) and/or be removed by a different flag
        # (denied_flag). Used by SQ7's one-time Forgotten Thing fight.
        rflag = encounter.get("requires_flag")
        if rflag and not state.flags.get(rflag):
            continue
        dflag = encounter.get("denied_flag")
        if dflag and state.flags.get(dflag):
            continue
        options.append((_encounter_label(encounter, content), ("encounter", encounter)))
    if _grave_here(state, loc, fallen):
        options.append(("🪦 Search a grave", ("grave", None)))
    for dest_id in loc.get("connections", []):
        dest = content.locations[dest_id]
        options.append((_travel_label(dest, player), ("travel", dest_id)))
    # Conditional connections — sub-zones the NPC quest opens up.
    # Also: any zone with `unlock_flag` opens when that flag is True
    # (the Atrél lore route reuses this mechanism without an NPC).
    for dest_id in loc.get("conditional_connections", []):
        dest = content.locations[dest_id]
        unlock_flag = dest.get("unlock_flag")
        if unlock_flag is not None:
            if not state.flags.get(unlock_flag):
                continue
        elif dest_id not in state.flags.get("unlocked_connections", []):
            continue
        options.append((_travel_label(dest, player), ("travel", dest_id)))
    # Fast travel back to the Crossroads — one-way, available from any zone
    # (not from hub/settlements, not from the Summit). Preserves the descent
    # outbound while letting the player shortcut the long walk home.
    if loc.get("kind") == "zone" and not loc.get("boss"):
        options.append(("🛤️  Walk back to the Crossroads", ("fast_travel", None)))
    # SQ3 — the Recurring Cat. After visiting the same zone enough times
    # in one run, the cat starts being here. It doesn't fight; it sits.
    visits = state.flags.get("zone_visits", {}).get(state.current_location, 0)
    if (loc.get("kind") == "zone" and not loc.get("boss")
            and visits >= CAT_ZONE_VISITS_REQUIRED):
        options.append(("🐈 Pet the cat", ("cat_pet", None)))
    # SQ4 — Piranesi's map. Once all 10 of his notes have been read
    # cross-run, a folded square of vellum waits in the Pre-Pall Shrine.
    if (state.current_location == "pre_pall_shrine"
            and state.flags.get("piranesi_map_unlocked")):
        options.append(("🪶 Read Piranesi's map", ("piranesi_map", None)))
    # SQ8 — Sing the Lost Verse at the Last Altar of Atrél. Per-run, once.
    if (state.current_location == "last_altar"
            and state.flags.get("lost_verse_known")
            and not state.flags.get("lost_verse_sung")):
        options.append(("🎼 Sing the Lost Verse", ("sing_verse", None)))
    # SQ10 — A child at the Crossroads with a book, once every side-quest
    # has been completed across runs and the first line has not been written.
    if (state.current_location == "crossroads"
            and chronicle.all_side_quests_done(state.chronicle_dir)
            and not chronicle.first_line(state.chronicle_dir)):
        options.append(("📖 A child stands at the Crossroads with a book",
                        ("write_first_line", None)))
    # SQ9 — the Witnessed Dead. A presence in zones where a fallen had
    # unfinished NPC-quest progress; offers to pass the work to you.
    for witnessed in _witnessed_dead_here(state, fallen):
        _entry, _npc_id, npc, partial, needed = witnessed
        dead_name = witnessed[0].get("player", {}).get("name", "a stranger")
        label = (f"🕯️  Honor {dead_name}'s work "
                 f"({partial}/{needed} {npc['target_enemy']}s)")
        options.append((label, ("honor", witnessed)))
    # At the Crossroads, if the player fast-travelled here from somewhere,
    # offer a paired "Return to ..." so the round-trip isn't a long walk back.
    return_target = state.flags.get("fast_travel_return")
    if (state.current_location == "crossroads"
            and return_target in content.locations):
        target_name = content.locations[return_target]["name"]
        options.append((f"🛤️  Return to {target_name}",
                        ("fast_travel_return", return_target)))
    # Melody quests: if any active quest has a target_composition whose altar
    # matches the current location, surface a "Compose for the ..." option.
    # The composer service handles the typed-input puzzle inline.
    active_qids = state.flags.get("active_quests", [])
    for qid in active_qids:
        quest = content.quests.get(qid)
        if quest is None:
            continue
        tcomp = quest.get("target_composition")
        if tcomp is None:
            continue
        if tcomp.get("altar") != state.current_location:
            continue
        voice = tcomp.get("voice", "voice")
        options.append((f"🎼 Compose for the {voice}",
                        ("compose", (qid, quest))))

    options.append(("🗡️  Inspect Weapon", ("weapon", None)))
    options.append(("View Stats", ("stats", None)))
    options.append(("Save Game", ("save", None)))
    options.append(("Quit Game", ("quit", None)))
    return options


def _print_background_presences(state):
    """v1.9 — recurring presences exist in the world between visits.

    After the intro is read, drop one or two quiet lines per zone showing
    that the cat / Piranesi / the Reader / the Insomniac / the child are
    HERE — they have not left, the kingdom is populated by them. Each
    line is gated by the same threshold that surfaces the character.
    """
    io = state.io
    loc_id = state.current_location
    cdir = state.chronicle_dir
    if loc_id == "village":
        if chronicle.cat_pets(cdir) >= 10:
            io.show_slow("  (The cat is asleep by the inn's hearth.)")
        if chronicle.discoveries_read(cdir) >= READER_THRESHOLD:
            io.show_slow("  (A figure at the desk in the corner has not "
                         "looked up. They are reading.)")
        if chronicle.gravewatch_visits(cdir) >= INSOMNIAC_THRESHOLD:
            io.show_slow("  (An old woman by the cold hearth is counting "
                         "something quietly.)")
        if chronicle.kind_acts(cdir) >= CARETAKER_THRESHOLD:
            io.show_slow("  (A basket of small flowers is set by the door, "
                         "fresh today.)")
        # v1.50 — once the player has left a line in the hearth-keeper's book,
        # the book is open on the corner of the hearth when you arrive.
        if chronicle.hearth_lines(cdir):
            io.show_slow("  (The leather book is open on the corner of the "
                         "hearth. Someone has been writing in it again.)")
    elif loc_id == "pre_pall_shrine":
        if state.flags.get("piranesi_map_unlocked"):
            io.show_slow("  (Piranesi's vellum is folded on the altar where "
                         "he left it for you.)")
    elif loc_id == "crossroads":
        if chronicle.first_line(cdir):
            io.show_slow("  (A small wooden box sits at the road's edge. "
                         "Whose, no one knows. It has not been moved.)")


def location_loop(state):
    """The central game loop. Runs until the player dies, wins, or quits."""
    player, content, io = state.player, state.content, state.io
    _entries = chronicle.load(state.chronicle_dir)
    fallen = chronicle.fallen(_entries)
    wardens = chronicle.wardens(_entries)
    arrived = True
    _maybe_open_border(state)  # 2-cleanse signal that the world has neighbours
    _maybe_remember_verse(state)  # SQ8: cross-run knowledge of the Lost Verse
    _maybe_wake_forgotten_thing(state)  # SQ7: the Boss the Pall Forgot
    while player.is_alive():
        loc = content.locations[state.current_location]
        # SQ3: each arrival in a zone increments its per-run visit count.
        # The cat surfaces in zones that have been visited often enough.
        if arrived and loc.get("kind") == "zone":
            visits = state.flags.setdefault("zone_visits", {})
            visits[state.current_location] = visits.get(state.current_location, 0) + 1
        # SQ6: each arrival at Gravewatch increments a cross-run counter.
        # At 50, the Insomniac surfaces in the village's service list.
        if arrived and state.current_location == "village":
            chronicle.add_gravewatch_visit(state.chronicle_dir)
        # v1.2: every arrival anywhere increments the cross-run zone counter,
        # used to switch to intro_familiar once the player has been here often.
        if arrived:
            chronicle.add_zone_visit(state.current_location, state.chronicle_dir)
        io.clear()
        if arrived:
            # Ambient drone follows the player from zone to zone. A disabled
            # engine is a no-op, so the headless test path and audio-off
            # players cost nothing.
            state.audio.play_zone(state.current_location)
            # Tell the TUI's map panel where we are and where past climbers
            # lie. On non-TUI io this is a no-op.
            ghost_locs = [e.get("location") for e in fallen if e.get("location")]
            io.set_location(state.current_location, ghost_locs)
            # Banner prints on every arrival — the kingdom announcing itself
            # each time, not just once per run. Repetition is the texture.
            _banners.print_banner(io, state.current_location)
            # Intro variants stack: intro_familiar (after FAMILIAR_VISITS+ cross-
            # run visits to this zone) is most specific; intro_cleansed (after
            # any completed run) is next; intro is the cold open.
            visits_here = chronicle.zone_visits_total(
                state.chronicle_dir).get(state.current_location, 0)
            if "intro_familiar" in loc and visits_here >= FAMILIAR_VISITS:
                intro_key = "intro_familiar"
            elif (chronicle.cleanses(state.chronicle_dir) >= 1
                    and "intro_cleansed" in loc):
                intro_key = "intro_cleansed"
            else:
                intro_key = "intro"
            for line in loc[intro_key]:
                io.show_slow(line)
            _print_background_presences(state)
            # v1.51 — irreversible per-character event roll on every arrival.
            # Atomic-saves to a sidecar before printing; save-scum has no power here.
            marks.roll_at(state, "zone_arrival")
            arrived = False
        io.show(f"\n📍 {loc['name']}")
        io.show(hud(player))
        # TUI status bar mirrors the inline hud — colour codes stripped because
        # curses renders ANSI escapes as literal text. No-op on line-mode io.
        io.set_status(
            f"{player.name} · Lv{player.level} · "
            f"❤ {player.hp}/{player.max_hp} · "
            f"⚡ {player.stamina}/{player.max_stamina} · "
            f"💰 {player.gold} · {loc['name']}")

        options = _build_options(state, loc, fallen)
        for index, (label, _action) in enumerate(options, start=1):
            io.show(f"{index}. {label}")
        choice = io.ask("\nWhat do you do? ")
        if not (choice.isdigit() and 1 <= int(choice) <= len(options)):
            io.show("\n❌ Invalid choice!")
            continue
        kind, arg = options[int(choice) - 1][1]

        if kind == "service":
            _run_service(state, arg)
            # SQ2: the Caretaker service ends the run on its own terms.
            if state.flags.get("run_ended"):
                return
        elif kind == "encounter":
            here = state.current_location
            outcome = run_encounter(state, arg, fallen, wardens)
            if outcome == "boss_victory":
                _victory_screen(state)
                return
            if state.current_location != here:
                arrived = True
        elif kind == "grave":
            _search_grave(state, fallen)
        elif kind == "travel":
            if try_travel(state, arg):
                arrived = True
        elif kind == "fast_travel":
            # Remember where we came from so the Crossroads can offer a return.
            state.flags["fast_travel_return"] = state.current_location
            io.show_slow("\n🛤️  You leave the grey road behind and walk back "
                         "the long way to the Crossroads.")
            io.pause(1)
            state.current_location = "crossroads"
            arrived = True
        elif kind == "cat_pet":
            _pet_the_cat(state)
        elif kind == "piranesi_map":
            _read_piranesi_map(state)
        elif kind == "sing_verse":
            sing_the_verse(state)
        elif kind == "write_first_line":
            _write_first_line(state)
        elif kind == "honor":
            _honor_the_dead(state, arg)
            # Re-load fallen so the just-laid-to-rest entry drops out.
            _entries = chronicle.load(state.chronicle_dir)
            fallen = chronicle.fallen(_entries)
        elif kind == "compose":
            _run_composition_quest(state, arg)
        elif kind == "fast_travel_return":
            target_name = content.locations[arg]["name"]
            io.show_slow(f"\n🛤️  You retrace the long road back to {target_name}.")
            io.pause(1)
            state.flags.pop("fast_travel_return", None)
            state.current_location = arg
            arrived = True
        elif kind == "weapon":
            _inspect_weapon(state)
        elif kind == "stats":
            show_stats(io, player, content)
        elif kind == "save":
            _save_menu(state)
        elif kind == "quit":
            io.show("\n👋 Thanks for playing!")
            return

    # v1.16: a dying character may leave one line for whoever climbs next.
    # The line is stored on the chronicle entry and surfaces at their grave
    # and as the first thing the Hollowed says when raised by the Pall.
    io.clear()
    io.show_slow("💀 The Pall takes you. You have a moment, before the dark.")
    io.show_slow("If you have something to say to whoever climbs after you, say it now.")
    io.show_slow("(One line. Enter alone to leave nothing.)")
    last_words = io.ask("\n> ").strip()
    chronicle.record(state, "fell", state.chronicle_dir, last_words=last_words)
    # v1.51 — the character is gone; the marks die with them. Clear sidecar.
    marks.clear_sidecar(state.chronicle_dir, state.player.run_id)
    io.clear()
    _banners.print_banner(io, "death")
    io.show_slow("💀 The Pall takes another. It always does.")
    _run_summary(state)
    io.show("\nGame Over!")

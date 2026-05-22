"""Encounters: combat dispatch, discoveries, NPCs, and grave drops.

Extracted from ``locations.py`` during the v2.3 quality audit. Every
function here is part of how a zone's encounters get rendered to the
player:

  * ``run_encounter`` — the main dispatcher (combat / discovery / npc /
    dialogue), including Hollowed candidate selection and Forsaken Sworn
    spawn rolls.
  * ``_make_forsaken_sworn`` — beefed-up enemy from a dead hireling.
  * ``_hollowed_candidates`` / ``_entry_act`` — eligibility logic for
    raising past characters as Hollowed.
  * ``_run_discovery`` — reading a lore fragment (with cross-run accounting
    for the Reader Who Watches Back and Piranesi's map).
  * ``_run_npc`` / ``_npc_progress`` — the NPC quest interface (a
    side-running kill/turn-in tracker).
  * ``_offer_drop`` — post-victory weapon-roll prompt.
  * ``_maybe_open_hardest_gate`` — unlocks the Bone Tomb once everything
    Mournhold could ask of the player has been done.

Configuration constants for these behaviours (roll chances, NPC roster,
discovery flag map) live here too. Everything is re-exported from
locations.py so existing callers and tests keep working.
"""

from __future__ import annotations
from . import boss_music_synth as _boss_music
from . import chronicle, marks
from . import dialogue as _dialogue
from .combat import run_combat
from .enemy import Enemy, make_enemy, make_hollowed, make_warden
from .weapon import roll_weapon


# ── Encounter tuning constants ─────────────────────────────────────
HOLLOWED_CHANCE = 0.25
WEAPON_DROP_CHANCE = 0.35
FORSAKEN_CHANCE = 0.15  # chance a random pool encounter spawns the fallen hireling instead


def _make_forsaken_sworn(fallen_dict):
    """Build a beefed-up enemy from a hireling's dying form. v0.8 mechanic.

    A fallen hireling rises grimdark — same stats, but the Pall has sharpened
    them. Returns an ``Enemy`` the combat loop accepts.
    """
    return Enemy("forsaken_sworn", {
        "name": f"the Forsaken {fallen_dict['name']}",
        "hp": int(fallen_dict["max_hp"] * 1.5),
        "attack": 14 + fallen_dict["defense"] * 2,
        "defense": fallen_dict["defense"] + 2,
        "xp_reward": 120,
        "gold_reward": 60,
        "ai": "relentless",
        "flavor": ("They were yours. They are not anymore. They will say "
                   "your name when they swing."),
    })


def _entry_act(state, entry):
    """The act of the zone where a Chronicle entry's character fell, or None."""
    loc = state.content.locations.get(entry.get("location", ""), {})
    return loc.get("act")


def _hollowed_candidates(state, fallen):
    """Fallen characters eligible to rise as the Hollowed in the current act.

    Graves and Hollowed match by act, not exact zone, so a larger world's
    deaths still pool densely enough that the Chronicle keeps being felt.
    """
    act = state.content.locations[state.current_location].get("act")
    if act is None:
        return []
    return [e for e in fallen
            if _entry_act(state, e) == act
            and e["player"]["level"] <= state.player.level + 1]


ATREL_LORE_FRAGMENTS = ("atrel_marker", "atrel_register", "atrel_side_altar")

# Some discoveries set named state flags as a side effect — used by arcs to
# unlock conditional connections, ending variants, or recontextualization.
_DISCOVERY_FLAGS = {
    "mourncross_scuffmarks": "sealed_chamber_found",
    "real_minutes": "read_real_minutes",
    "verren_fragment": "verren_found",
    "drowned_holds_petition": "hidden_hold_found",  # reading the petition opens the way north
    "first_kings_pommel": "read_garren_pommel",  # unlocks Cael's memory of her father
    "small_uns_drawing": "read_small_uns_drawing",  # gates the Small Un's second drawing
    "atrel_original_rite": "read_atrel_folio",  # unlocks Atrél's "of_renaud" branch
    "bone_tomb_column_of_seals": "read_column_of_seals",  # unlocks Cael's "of_column" branch
    "palls_only_words": "read_palls_words",  # unlocks Cael's "of_pall_words" branch
}

# The Bone Tomb requires the player to have done everything Mournhold can
# offer them — all four NPC quests completed AND the Verren fragment found.
_HARDEST_GATE_NPCS = ("old_halna", "weir_engineer", "lampkeeper", "old_penitent")


def _maybe_open_hardest_gate(state):
    """If every NPC quest is complete and Verren is found, open the Bone Tomb."""
    if state.flags.get("the_hardest_gate"):
        return
    if not state.flags.get("verren_found"):
        return
    done = set(state.flags.get("npcs_done", []))
    if set(_HARDEST_GATE_NPCS).issubset(done):
        state.flags["the_hardest_gate"] = True
        state.io.show_slow("\n🪨 You have spoken with every keeper. You have read every "
                           "stone Mournhold left for you to read.")
        state.io.show_slow("Behind the Pre-Pall Shrine's altar, a stair is opening.")
        state.io.pause(2)


def _run_discovery(state, encounter):
    """Reveal a one-time lore fragment, then mark it found in ``state.flags``.

    A discovery may also set named flags (see ``_DISCOVERY_FLAGS``) used by
    later arcs to unlock zones or overlay endings.

    Atrél's three fragments collectively set ``atrel_lore_found`` when all
    three are seen — gating the Last Altar zone and overlaying Cantor Vael's
    flavour with the recontextualized version.
    """
    io = state.io
    io.clear()
    for line in encounter["lines"]:
        io.show_slow(line)
    # v1.40 — the hearth-keeper's book also displays what previous climbers
    # have written. Appended after the discovery's static lines.
    if encounter["id"] == "hearthkeepers_book":
        past = chronicle.hearth_lines(state.chronicle_dir)
        if past:
            io.show("")
            io.show_slow("Turned to the back of the book, in many hands over many runs,")
            io.show_slow("what previous climbers have written:")
            io.show("")
            for past_line in past:
                io.show_slow(f"  '{past_line}'")
    io.pause(2)
    discovery_id = encounter["id"]
    state.flags.setdefault("discoveries_seen", []).append(discovery_id)
    # SQ1 — every discovery the player reads is also recorded cross-run.
    chronicle.add_read_discovery(discovery_id, state.chronicle_dir)
    # SQ2 — reading lore is one of the small kindnesses.
    chronicle.add_kind_act(state.chronicle_dir)
    # v1.51 — reading a discovery is a fire site for the Marks system.
    marks.roll_at(state, "discovery_read")
    if discovery_id in _DISCOVERY_FLAGS:
        state.flags[_DISCOVERY_FLAGS[discovery_id]] = True
    # SQ4: Piranesi notes accumulate cross-run via the Chronicle.
    if discovery_id.startswith("piranesi_"):
        chronicle.add_piranesi_note(discovery_id, state.chronicle_dir)
        count = chronicle.piranesi_notes(state.chronicle_dir)
        if count == 10 and not state.flags.get("piranesi_map_unlocked"):
            state.flags["piranesi_map_unlocked"] = True
            io.show_slow("\n🪶 You have read enough of Piranesi to know the hand.")
            io.show_slow("In the Pre-Pall Shrine, a folded square of vellum awaits.")
            io.show_slow("It is the map he left for the climber who would read enough.")
            io.pause(2)
    # SQ8: Lost Verse fragments accumulate cross-run. Four found → the verse
    # is known. The player can Sing it at the Last Altar of Atrél thereafter.
    if discovery_id.startswith("lost_verse_"):
        chronicle.add_lost_verse_fragment(discovery_id, state.chronicle_dir)
        count = chronicle.lost_verse_fragments(state.chronicle_dir)
        if count == 4 and not state.flags.get("lost_verse_known"):
            state.flags["lost_verse_known"] = True
            io.show_slow("\n🎼 Four lines. The whole verse, in your throat now.")
            io.show_slow("It was the verse the kingdom would not sing.")
            io.show_slow("At Atrél's altar, you will be able to sing it.")
            io.pause(2)
    seen = set(state.flags["discoveries_seen"])
    if (set(ATREL_LORE_FRAGMENTS).issubset(seen)
            and not state.flags.get("atrel_lore_found")):
        state.flags["atrel_lore_found"] = True
        io.show_slow("\n📿 You have gathered all three traces of Atrél.")
        io.show_slow("Something in the Choir has noticed you noticing.")
        io.pause(2)
    _maybe_open_hardest_gate(state)


def _npc_progress(state, npc):
    """How close the player is to the NPC's quest threshold (0..needed)."""
    if "target_enemy" in npc:
        return state.flags.get("npc_kills", {}).get(npc["target_enemy"], 0)
    if "target_trophy" in npc:
        return state.player.trophies.get(npc["target_trophy"], 0)
    return 0


def _run_npc(state, encounter):
    """Run the NPC interaction. Three states: offered, in_progress, complete.

    Tracks state in state.flags['npcs_seen'] (offered+) and
    state.flags['npcs_done'] (claimed). On completion, the unlocks_connection
    flag and unlocks_service flag (if any) are set, persisting via save/load.
    """
    io, content = state.io, state.content
    npc_id = encounter["id"]
    npc = content.npcs[npc_id]
    seen = state.flags.setdefault("npcs_seen", [])
    done = state.flags.setdefault("npcs_done", [])
    needed = npc["needed"]
    progress = _npc_progress(state, npc)
    io.clear()
    if npc_id in done:
        # Already claimed — small greeting, no quest re-offer.
        io.show_slow(f"\n{npc['name']} nods at you. The road is open.")
        io.pause(1)
        return
    if npc_id not in seen:
        for line in npc["intro"]:
            io.show_slow(line)
        seen.append(npc_id)
        io.pause(1)
        return
    if progress < needed:
        for line in npc["in_progress"]:
            io.show_slow(line)
        target = npc.get("target_enemy") or npc.get("target_trophy")
        io.show(f"\nProgress: {progress}/{needed} {target.replace('_', ' ')}.")
        io.pause(1)
        return
    # Completion path.
    for line in npc["complete"]:
        io.show_slow(line)
    if "target_trophy" in npc:
        # Consume the spent trophies.
        state.player.trophies[npc["target_trophy"]] -= needed
    done.append(npc_id)
    state.flags.setdefault("unlocked_connections", []).append(npc["unlocks_connection"])
    if "unlocks_service" in npc:
        state.flags.setdefault("unlocked_services", []).append(npc["unlocks_service"])
    io.pause(2)


def _offer_drop(state):
    """After a victory, maybe drop a salvaged weapon to equip or leave behind."""
    act = state.content.locations[state.current_location].get("act")
    if act is None or state.rng.random() >= WEAPON_DROP_CHANCE:
        return
    player, io = state.player, state.io
    weapon = roll_weapon(state.content, act, state.rng,
                         chronicle.unlocked(state.chronicle_dir))
    current = player.equipment.get("weapon")
    io.show_slow(f"\n🗡️  Salvaged from the dead: {weapon.name}")
    io.show(f"   {weapon.summary()}")
    if current is not None:
        io.show(f"   you wield: {current.name} — {current.summary()}")
    io.show("\n1. Take it up")
    io.show("2. Leave it")
    if io.ask("\nYour choice? ") == "1":
        player.equip_weapon(weapon)
        io.show(f"\n✅ You take up the {weapon.name}.")
    else:
        io.show("\nYou leave it for the grey.")


def run_encounter(state, encounter, fallen, wardens):
    """Run one encounter at the current location.

    A 'discovery' encounter reveals a lore fragment and returns None. A
    'combat' encounter returns its outcome ('victory'/'defeat'/'fled'/
    'enemy_fled'), or 'boss_victory' when a boss encounter is won. A
    random-pick combat may instead raise a Hollowed — a past character who
    fell nearby — and a boss encounter becomes the last victor, kept by the
    Pall as the Warden.
    """
    if encounter["type"] == "discovery":
        _run_discovery(state, encounter)
        return None
    if encounter["type"] == "npc":
        _run_npc(state, encounter)
        return None
    if encounter["type"] == "dialogue":
        tree = state.content.dialogues[encounter["dialogue_id"]]
        state.io.clear()
        _dialogue.run_dialogue(state, tree)
        return None
    io, rng, content = state.io, state.rng, state.content
    if encounter["type"] != "combat":
        return None

    candidates = _hollowed_candidates(state, fallen)
    hollowed_entry = None

    def _voice_the_hollowed(entry):
        """Print one line of the rising character's persistence — the last
        moment of them, before the Pall fully takes their face for the fight.

        v1.16 — if the dying character left ``last_words``, the Hollowed
        speaks those instead of a generic template. The words they chose
        are the first thing through, before the Pall takes their face.
        """
        p = entry["player"]
        zone_id = entry.get("location", "")
        place = content.locations.get(zone_id, {}).get("name", "the grey")
        name, class_name = p["name"], p["class_name"]
        io.show("")
        last_words = entry.get("last_words", "")
        if last_words:
            io.show_slow(f"'I am {name}. I said one thing, before. I said it for you.'")
            io.show_slow(f"   '{last_words}'")
            io.pause(1)
            return
        bank = (
            (f"'I am... I was {name}. The {class_name}. I fell at {place}.'",
             "'I almost made it. Don't make me almost make it again.'"),
            ("'I know you. Stand still. Stand still and I will know.'",
             f"'I am {name}. The {class_name}. I am {name}.'"),
            ("'Don't lay me down yet. I have not finished it.'",
             f"'I have not finished. I am {name}, and I have not finished.'"),
            ("(They lift their hand. They put it down again, slowly.)",
             f"'I was {name}. {place} took me. The Pall kept what was left.'"),
            ("'Did I leave anything? My pack — did anyone take it?'",
             f"'I was {name} the {class_name}. Tell them I made it this far.'"),
        )
        lines = bank[rng.randint(0, len(bank) - 1) % len(bank)]
        for line in lines:
            io.show_slow(line)
        io.pause(1)

    fallen_hireling = state.flags.get("fallen_hireling")
    if encounter.get("boss") and wardens:
        enemies = [make_warden(wardens[-1], content)]
    elif (encounter.get("pick") == "random" and fallen_hireling
          and rng.random() < FORSAKEN_CHANCE):
        enemies = [_make_forsaken_sworn(fallen_hireling)]
    elif (encounter.get("pick") == "random" and candidates
          and rng.random() < HOLLOWED_CHANCE):
        hollowed_entry = rng.choice(candidates)
        _voice_the_hollowed(hollowed_entry)
        enemies = [make_hollowed(hollowed_entry)]
    elif encounter.get("pick") == "random":
        enemies = [make_enemy(rng.choice(encounter["enemies"]),
                              content, state.flags)]
    else:
        enemies = [make_enemy(eid, content, state.flags)
                   for eid in encounter["enemies"]]

    # Boss-music handoff: if this encounter is a boss fight AND the
    # boss has a music theme, swap from ambient to the boss's theme. The
    # Shadow Warden uses runtime context (which bosses this run defeated)
    # so its quotes are dynamic; every other boss just plays its cached
    # WAV. Disabled audio is a no-op.
    boss_theme_id = None
    if encounter.get("boss"):
        for eid in encounter.get("enemies", []):
            if eid in _boss_music.BOSS_IDS:
                boss_theme_id = eid
                break
    if boss_theme_id is not None:
        state.audio.play_boss(
            boss_theme_id,
            context={"defeated_bosses":
                     list(state.flags.get("bosses_defeated", []))},
        )

    outcome = None
    enemy = None
    last_index = len(enemies) - 1
    for index, enemy in enumerate(enemies):
        is_last = index == last_index
        # Chained sub-fights share one breath: stamina persists between them,
        # restored only after the last fight ends.
        outcome = run_combat(state, enemy, refresh_after=is_last)
        if outcome != "victory":
            # The chain ended off-script (fled, enemy fled, or defeat). For
            # the survivable outcomes the tension is over — restore stamina
            # here, since run_combat skipped it.
            if not is_last and outcome != "defeat":
                state.player.stamina = state.player.max_stamina
            break

    # Boss fight over — restore the zone's ambient drone. play_zone is a
    # no-op if audio is disabled or if the zone was already playing.
    if boss_theme_id is not None:
        state.audio.play_zone(state.current_location)

    if outcome == "enemy_fled":
        io.show(f"\nThe {enemy.name} escaped. You earn nothing this time.")
    elif outcome == "fled":
        io.show("\nYou retreat to the Crossroads, shaken but alive.")
        state.current_location = "crossroads"
    if hollowed_entry is not None and outcome == "victory":
        chronicle.lay_to_rest(hollowed_entry, state.chronicle_dir)
        chronicle.add_kind_act(state.chronicle_dir)  # SQ2: laying-to-rest is kindness
        name = hollowed_entry["player"]["name"]
        io.show_slow(f"\n🕯️  {name} is still, at last. The Pall will not raise "
                     f"them again — you have given them that much.")
    if outcome == "victory" and enemy is not None and enemy.unique:
        chronicle.unlock(enemy.enemy_id, state.chronicle_dir)
    # SQ7 — defeating the Forgotten Thing marks it remembered.
    # The flag is per-run (cannot be re-fought in this character's run);
    # the Chronicle unlock above persists the trophy across characters.
    if (outcome == "victory" and encounter.get("id") == "forgotten_thing_fight"):
        state.flags["forgotten_thing_defeated"] = True
        io.show("")
        io.show_slow("🌳 The Forgotten Thing is named, by you alone, in this run.")
        io.show_slow("It will not be there again. It does not need to be.")
        io.pause(2)
    if outcome == "victory" and not encounter.get("boss"):
        _offer_drop(state)
    if encounter.get("boss") and outcome == "victory":
        # Record the kill so subsequent boss fights (most notably the
        # Shadow Warden, who quotes only the bosses this run defeated)
        # know about it.
        if boss_theme_id is not None:
            defeated = state.flags.setdefault("bosses_defeated", [])
            if boss_theme_id not in defeated:
                defeated.append(boss_theme_id)
        return "boss_victory"
    return outcome



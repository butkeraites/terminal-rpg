"""Travel, save menu, weapon inspect, and grave search.

Extracted from ``locations.py`` during the v2.3 quality audit — the
last sibling-module split. These are the small per-zone actions the
player picks from a settlement menu: walk to a new zone, save the
game, look at your weapon, dig at a grave, plus the two label helpers
that name menu entries.

Everything is re-exported from ``locations.py`` so existing callers
(and the dispatch lines inside ``location_loop``) keep working.
"""
from . import marks, saves
from .encounters import _entry_act
from .quests import scan_hidden_quest_triggers
from .weapon import WEAPON_SLOTS


# How many recommended levels above the player a zone may be before
# its signpost prompts a "turn back?" warning. Used by try_travel.
SIGNPOST_THRESHOLD = 2


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



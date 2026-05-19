"""Explorable locations and the main game loop.

The world is a graph of locations loaded from ``data/locations.json``.
``location_loop`` is the central loop: it renders the player's current
location, offers its services, encounters and travel routes, and runs
until the player dies, wins, or quits.
"""
from . import chronicle, saves
from .combat import run_combat
from .enemy import make_enemy, make_hollowed, make_warden
from .ui import hud, show_stats

INN_COST = 20
POTION_COST = 30
GREATER_POTION_COST = 70
ATTACK_UPGRADE_GOLD_PER_POINT = 8
DEFENSE_UPGRADE_GOLD_PER_POINT = 14
SIGNPOST_THRESHOLD = 2
HOLLOWED_CHANCE = 0.25

_SERVICE_LABELS = {
    "shop": "🏪 Visit the Shop",
    "inn": f"😴 Rest at the Inn ({INN_COST} gold)",
}


def shop(state):
    player, io = state.player, state.io
    io.clear()
    io.show_slow("🏪 Welcome to the Shop!\n")
    while True:
        atk_cost = player.attack * ATTACK_UPGRADE_GOLD_PER_POINT
        def_cost = player.defense * DEFENSE_UPGRADE_GOLD_PER_POINT
        io.show(hud(player))
        io.show(f"\n1. Health Potion ({POTION_COST} gold)")
        io.show(f"2. Greater Potion ({GREATER_POTION_COST} gold)")
        io.show(f"3. Upgrade Attack (+5 attack, {atk_cost} gold)")
        io.show(f"4. Upgrade Defense (+3 defense, {def_cost} gold)")
        io.show("5. Leave Shop")
        choice = io.ask("\nWhat would you like? ")

        if choice == "1":
            if player.gold >= POTION_COST:
                player.gold -= POTION_COST
                player.inventory.append("Health Potion")
                io.show("\n✅ Bought a Health Potion!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "2":
            if player.gold >= GREATER_POTION_COST:
                player.gold -= GREATER_POTION_COST
                player.inventory.append("Greater Potion")
                io.show("\n✅ Bought a Greater Potion!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "3":
            if player.gold >= atk_cost:
                player.gold -= atk_cost
                player.attack += 5
                io.show(f"\n✅ Attack increased to {player.attack}!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "4":
            if player.gold >= def_cost:
                player.gold -= def_cost
                player.defense += 3
                io.show(f"\n✅ Defense increased to {player.defense}!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "5":
            return
        else:
            io.show("\n❌ Invalid choice!")
        io.pause(1)


def _rest_at_inn(state):
    """The settlement 'inn' service: pay to fully recover."""
    player, io = state.player, state.io
    if player.gold >= INN_COST:
        player.gold -= INN_COST
        player.hp = player.max_hp
        player.stamina = player.max_stamina
        player.statuses.clear()
        io.show("\n😴 You rest at the inn and recover fully!")
    else:
        io.show("\n❌ Not enough gold!")
    io.pause(1)


def _run_service(state, service):
    """Dispatch a settlement service by name."""
    if service == "shop":
        shop(state)
    elif service == "inn":
        _rest_at_inn(state)


def _hollowed_candidates(state, fallen):
    """Fallen characters eligible to rise as the Hollowed in the current zone."""
    return [e for e in fallen
            if e.get("location") == state.current_location
            and e["player"]["level"] <= state.player.level + 1]


def run_encounter(state, encounter, fallen, wardens):
    """Run one encounter at the current location.

    Returns the combat outcome ('victory'/'defeat'/'fled'/'enemy_fled'),
    or 'boss_victory' when a boss encounter is won. A random-pick combat
    may instead raise a Hollowed — a past character who fell here — and a
    boss encounter becomes the last victor, kept by the Pall as the Warden.
    """
    io, rng, content = state.io, state.rng, state.content
    if encounter["type"] != "combat":
        return None

    candidates = _hollowed_candidates(state, fallen)
    hollowed_entry = None
    if encounter.get("boss") and wardens:
        enemies = [make_warden(wardens[-1], content)]
    elif (encounter.get("pick") == "random" and candidates
          and rng.random() < HOLLOWED_CHANCE):
        hollowed_entry = rng.choice(candidates)
        enemies = [make_hollowed(hollowed_entry)]
    elif encounter.get("pick") == "random":
        enemies = [make_enemy(rng.choice(encounter["enemies"]), content)]
    else:
        enemies = [make_enemy(eid, content) for eid in encounter["enemies"]]

    outcome = None
    enemy = None
    for enemy in enemies:
        outcome = run_combat(state, enemy)
        if outcome != "victory":
            break

    if outcome == "enemy_fled":
        io.show(f"\nThe {enemy.name} escaped. You earn nothing this time.")
    elif outcome == "fled":
        io.show("\nYou retreat to the Crossroads, shaken but alive.")
        state.current_location = "crossroads"
    if hollowed_entry is not None and outcome == "victory":
        chronicle.lay_to_rest(hollowed_entry, state.chronicle_dir)
        name = hollowed_entry["player"]["name"]
        io.show_slow(f"\n🕯️  {name} is still, at last. The Pall will not raise "
                     f"them again — you have given them that much.")
    if encounter.get("boss") and outcome == "victory":
        return "boss_victory"
    return outcome


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
    return True


def _victory_screen(state):
    """The end screen: the Warden falls, and the Pall keeps the victor."""
    player, io = state.player, state.io
    chronicle.record(state, "warden", state.chronicle_dir)
    io.clear()
    io.show_slow("The Shadow Warden comes apart like wet ash — and the Pall,")
    io.show_slow("finding itself without a Warden, turns to the soul still")
    io.show_slow("standing on the Summit. It pours into you. You never feel it take.")
    io.show("\n" + "=" * 50)
    io.show("🥀  THE PALL KEEPS YOU")
    io.show(f"{player.name} the {player.class_name} — Warden of the Shrouded Summit")
    io.show("\nYou will not climb down. You will wait here, wearing your own")
    io.show("face, until the next soul reaches the Summit to break you —")
    io.show("as you broke the one before.")
    io.show("=" * 50)
    io.show("\nThank you for playing Terminal Quest.")


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
    elif choice != "4":
        io.show("\n❌ Invalid choice!")
    io.pause(1)


def _encounter_label(encounter, content):
    """A menu label for one encounter."""
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
    """True if this zone holds an unsearched grave from a past character."""
    if loc.get("kind") != "zone":
        return False
    if state.current_location in state.flags.get("graves_searched", []):
        return False
    return any(e.get("location") == state.current_location for e in fallen)


def _search_grave(state, fallen):
    """Search the current zone for the remains of one who fell here."""
    player, io = state.player, state.io
    here = [e for e in fallen if e.get("location") == state.current_location]
    p = state.rng.choice(here)["player"]
    place = state.content.locations[state.current_location]["name"]
    io.show_slow(f"\n🪦 Half-buried in the grey earth: {p['name']} the {p['class_name']}.")
    io.show(f"{place} took them at level {p['level']}. It will take you too, in time.")
    coins = min(p.get("gold", 0), 40)
    if coins:
        player.gold += coins
        io.show(f"You prise {coins} coins from the cold — they have no use for them now.")
    else:
        io.show("They left nothing behind. The dead here rarely do.")
    io.pause(1)
    state.flags.setdefault("graves_searched", []).append(state.current_location)


def _build_options(state, loc, fallen):
    """Build the ordered list of ``(label, (kind, arg))`` menu entries."""
    player, content = state.player, state.content
    options = []
    for service in loc.get("services", []):
        options.append((_SERVICE_LABELS[service], ("service", service)))
    for encounter in loc.get("encounters", []):
        options.append((_encounter_label(encounter, content), ("encounter", encounter)))
    if _grave_here(state, loc, fallen):
        options.append(("🪦 Search a grave", ("grave", None)))
    for dest_id in loc.get("connections", []):
        dest = content.locations[dest_id]
        options.append((_travel_label(dest, player), ("travel", dest_id)))
    options.append(("View Stats", ("stats", None)))
    options.append(("Save Game", ("save", None)))
    options.append(("Quit Game", ("quit", None)))
    return options


def location_loop(state):
    """The central game loop. Runs until the player dies, wins, or quits."""
    player, content, io = state.player, state.content, state.io
    _entries = chronicle.load(state.chronicle_dir)
    fallen = chronicle.fallen(_entries)
    wardens = chronicle.wardens(_entries)
    arrived = True
    while player.is_alive():
        loc = content.locations[state.current_location]
        io.clear()
        if arrived:
            for line in loc["intro"]:
                io.show_slow(line)
            arrived = False
        io.show(f"\n📍 {loc['name']}")
        io.show(hud(player))

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
        elif kind == "stats":
            show_stats(io, player)
        elif kind == "save":
            _save_menu(state)
        elif kind == "quit":
            io.show("\n👋 Thanks for playing!")
            return

    chronicle.record(state, "fell", state.chronicle_dir)
    io.clear()
    io.show_slow("💀 The Pall takes another. It always does.")
    io.show("\nFinal Stats:")
    io.show(f"Level: {player.level}")
    io.show(f"Gold: {player.gold}")
    io.show("\nGame Over!")

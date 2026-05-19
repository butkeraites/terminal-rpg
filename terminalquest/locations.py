"""Explorable locations and the main game loop.

The world is a graph of locations loaded from ``data/locations.json``.
``location_loop`` is the central loop: it renders the player's current
location, offers its services, encounters and travel routes, and runs
until the player dies, wins, or quits.
"""
from . import saves
from .combat import run_combat
from .enemy import make_enemy
from .ui import show_stats

INN_COST = 20
POTION_COST = 30
GREATER_POTION_COST = 70
ATTACK_UPGRADE_COST = 100
DEFENSE_UPGRADE_COST = 80
SIGNPOST_THRESHOLD = 2

_SERVICE_LABELS = {
    "shop": "🏪 Visit the Shop",
    "inn": f"😴 Rest at the Inn ({INN_COST} gold)",
}


def shop(state):
    player, io = state.player, state.io
    io.clear()
    io.show_slow("🏪 Welcome to the Shop!\n")
    while True:
        io.show(f"Your gold: {player.gold}")
        io.show(f"\n1. Health Potion ({POTION_COST} gold)")
        io.show(f"2. Greater Potion ({GREATER_POTION_COST} gold)")
        io.show(f"3. Upgrade Attack (+5 attack, {ATTACK_UPGRADE_COST} gold)")
        io.show(f"4. Upgrade Defense (+3 defense, {DEFENSE_UPGRADE_COST} gold)")
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
            if player.gold >= ATTACK_UPGRADE_COST:
                player.gold -= ATTACK_UPGRADE_COST
                player.attack += 5
                io.show(f"\n✅ Attack increased to {player.attack}!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "4":
            if player.gold >= DEFENSE_UPGRADE_COST:
                player.gold -= DEFENSE_UPGRADE_COST
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


def run_encounter(state, encounter):
    """Run one encounter at the current location.

    Returns the combat outcome ('victory'/'defeat'/'fled'/'enemy_fled'),
    or 'boss_victory' when a boss encounter is won. Currently only the
    'combat' encounter type exists; the dispatch leaves room for more.
    """
    io, rng, content = state.io, state.rng, state.content
    if encounter["type"] != "combat":
        return None

    pool = encounter["enemies"]
    if encounter.get("pick") == "random":
        enemy_ids = [rng.choice(pool)]
    else:
        enemy_ids = list(pool)

    outcome = None
    enemy = None
    for enemy_id in enemy_ids:
        enemy = make_enemy(enemy_id, content)
        outcome = run_combat(state, enemy)
        if outcome != "victory":
            break

    if outcome == "enemy_fled":
        io.show(f"\nThe {enemy.name} escaped. You earn nothing this time.")
    elif outcome == "fled":
        io.show("\nYou retreat to the Crossroads, shaken but alive.")
        state.current_location = "crossroads"
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
    """Render the win screen after the final boss is defeated."""
    player, io = state.player, state.io
    io.clear()
    io.show_slow("🌟 The shadow dissolves into fading light...")
    io.show_slow("Dawn breaks over the realm. You have won!")
    io.show("\n" + "=" * 50)
    io.show("🏆  VICTORY")
    io.show(f"{player.name} the {player.class_name} — Level {player.level}")
    io.show(f"💰 Gold: {player.gold}")
    io.show("=" * 50)
    io.show("\nThank you for playing Terminal Quest!")


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


def _build_options(state, loc):
    """Build the ordered list of ``(label, (kind, arg))`` menu entries."""
    player, content = state.player, state.content
    options = []
    for service in loc.get("services", []):
        options.append((_SERVICE_LABELS[service], ("service", service)))
    for encounter in loc.get("encounters", []):
        options.append((_encounter_label(encounter, content), ("encounter", encounter)))
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
    arrived = True
    while player.is_alive():
        loc = content.locations[state.current_location]
        io.clear()
        if arrived:
            for line in loc["intro"]:
                io.show_slow(line)
            arrived = False
        io.show(f"\n📍 {loc['name']}")
        io.show(f"HP: {player.hp}/{player.max_hp} | Gold: {player.gold} "
                f"| Potions: {player.potion_count()}")

        options = _build_options(state, loc)
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
            outcome = run_encounter(state, arg)
            if outcome == "boss_victory":
                _victory_screen(state)
                return
            if state.current_location != here:
                arrived = True
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

    io.clear()
    io.show_slow("💀 You have been defeated...")
    io.show("\nFinal Stats:")
    io.show(f"Level: {player.level}")
    io.show(f"Gold: {player.gold}")
    io.show("\nGame Over!")

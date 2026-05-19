"""Explorable locations. Each renders a menu loop and mutates the player.

A location is entered from ``world_map`` and returns control to it; the
world map is the central hub and the game's main loop.
"""
import random

from . import saves
from .combat import run_combat
from .enemy import make_enemy
from .ui import show_stats

INN_COST = 20
POTION_COST = 30
ATTACK_UPGRADE_COST = 100
DEFENSE_UPGRADE_COST = 80


def shop(player, io):
    io.clear()
    io.show_slow("🏪 Welcome to the Shop!\n")
    while True:
        io.show(f"Your gold: {player.gold}")
        io.show(f"\n1. Health Potion ({POTION_COST} gold)")
        io.show(f"2. Upgrade Attack (+5 attack, {ATTACK_UPGRADE_COST} gold)")
        io.show(f"3. Upgrade Defense (+3 defense, {DEFENSE_UPGRADE_COST} gold)")
        io.show("4. Leave Shop")
        choice = io.ask("\nWhat would you like? ")

        if choice == "1":
            if player.gold >= POTION_COST:
                player.gold -= POTION_COST
                player.inventory.append("Health Potion")
                io.show("\n✅ Bought a Health Potion!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "2":
            if player.gold >= ATTACK_UPGRADE_COST:
                player.gold -= ATTACK_UPGRADE_COST
                player.attack += 5
                io.show(f"\n✅ Attack increased to {player.attack}!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "3":
            if player.gold >= DEFENSE_UPGRADE_COST:
                player.gold -= DEFENSE_UPGRADE_COST
                player.defense += 3
                io.show(f"\n✅ Defense increased to {player.defense}!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "4":
            return
        else:
            io.show("\n❌ Invalid choice!")
        io.pause(1)


def village(player, io):
    io.clear()
    io.show_slow("🏘️  Welcome to the Village")
    io.show("\nA peaceful place with a shop and an inn.\n")
    while True:
        io.show("1. Visit Shop")
        io.show(f"2. Rest at Inn ({INN_COST} gold)")
        io.show("3. View Stats")
        io.show("4. Leave Village")
        choice = io.ask("\nWhat do you do? ")

        if choice == "1":
            shop(player, io)
        elif choice == "2":
            if player.gold >= INN_COST:
                player.gold -= INN_COST
                player.hp = player.max_hp
                player.stamina = player.max_stamina
                player.statuses.clear()
                io.show("\n😴 You rest at the inn and recover fully!")
            else:
                io.show("\n❌ Not enough gold!")
            io.pause(1)
        elif choice == "3":
            show_stats(io, player)
        elif choice == "4":
            player.position = "world"
            return
        else:
            io.show("\n❌ Invalid choice!")


def explore_zone(player, zone_id, content, io, rng=None):
    """Enter a zone, fight a random resident enemy, and report the result."""
    rng = rng or random.Random()
    zone = content.zones[zone_id]
    io.clear()
    for line in zone["intro"]:
        io.show_slow(line)
    io.pause(1)

    enemy = make_enemy(rng.choice(zone["enemies"]), content)
    outcome = run_combat(player, enemy, content, io, rng)
    if outcome == "enemy_fled":
        io.show(f"\nThe {enemy.name} escaped. You earn nothing this time.")
    elif outcome == "fled":
        io.show("\nYou retreat to the crossroads, shaken but alive.")
    player.position = "world"
    return outcome


def _save_menu(player, io):
    saved = saves.list_saves()
    io.show("\nSave slots:")
    for slot in saves.SLOTS:
        io.show(f"{slot}. {saved.get(slot, '(empty)')}")
    io.show("4. Cancel")
    choice = io.ask("\nSave to which slot? ")
    if choice in ("1", "2", "3"):
        saves.save_game(player, int(choice))
        io.show(f"\n💾 Game saved to slot {choice}.")
    elif choice != "4":
        io.show("\n❌ Invalid choice!")
    io.pause(1)


def world_map(player, content, io, rng=None):
    """The central hub and main game loop. Runs until the player dies or quits."""
    rng = rng or random.Random()
    io.clear()
    io.show_slow("🗺️  World Map\n")

    zone_ids = list(content.zones)
    while player.is_alive():
        io.show("\nCurrent Location: Crossroads")
        io.show(f"HP: {player.hp}/{player.max_hp} | Gold: {player.gold} "
                f"| Potions: {player.potion_count()}")

        io.show("\n1. Return to Village")
        for index, zone_id in enumerate(zone_ids, start=2):
            io.show(f"{index}. Explore {content.zones[zone_id]['name']}")
        stats_opt = len(zone_ids) + 2
        save_opt = stats_opt + 1
        quit_opt = save_opt + 1
        io.show(f"{stats_opt}. View Stats")
        io.show(f"{save_opt}. Save Game")
        io.show(f"{quit_opt}. Quit Game")
        choice = io.ask("\nWhere do you want to go? ")

        if choice == "1":
            village(player, io)
        elif choice.isdigit() and 2 <= int(choice) < stats_opt:
            explore_zone(player, zone_ids[int(choice) - 2], content, io, rng)
        elif choice == str(stats_opt):
            show_stats(io, player)
        elif choice == str(save_opt):
            _save_menu(player, io)
        elif choice == str(quit_opt):
            io.show("\n👋 Thanks for playing!")
            return
        else:
            io.show("\n❌ Invalid choice!")

    io.clear()
    io.show_slow("💀 You have been defeated...")
    io.show("\nFinal Stats:")
    io.show(f"Level: {player.level}")
    io.show(f"Gold Earned: {player.gold}")
    io.show("\nGame Over!")

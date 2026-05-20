"""Explorable locations and the main game loop.

The world is a graph of locations loaded from ``data/locations.json``.
``location_loop`` is the central loop: it renders the player's current
location, offers its services, encounters and travel routes, and runs
until the player dies, wins, or quits.
"""
from . import chronicle, saves
from .accessory import make_accessory
from .armor import make_armor
from .combat import CLASS_CONSUMABLE, QUESTS, _consumable_label, run_combat
from .companion import make_companion
from .enemy import make_enemy, make_hollowed, make_warden
from .hireling import make_hireling
from .pet import make_pet
from .ui import hud, show_stats
from .weapon import WEAPON_SLOTS, WEAPON_UPGRADES, roll_weapon

INN_COST = 20
POTION_COST = 30
GREATER_POTION_COST = 70
SOVEREIGN_POTION_COST = 200
PALL_DRINKER_COST = 500
SOVEREIGN_UNLOCK_CHAMPIONS = 1
PALL_DRINKER_UNLOCK_CHAMPIONS = 3
ATTACK_UPGRADE_GOLD_PER_POINT = 8
DEFENSE_UPGRADE_GOLD_PER_POINT = 14
SIGNPOST_THRESHOLD = 2
HOLLOWED_CHANCE = 0.25
WEAPON_DROP_CHANCE = 0.35
FORSAKEN_CHANCE = 0.15  # chance a random pool encounter spawns the fallen hireling instead
NIGHT_HUNT_COST = 40
NIGHT_HUNT_STAT_BOOST = 1.5  # enemy hp/atk multiplied by this for night hunts
NIGHT_HUNT_REWARD_MULT = 2.5  # XP and gold rewards scale up the same way
SURVIVOR_CLEANSES_REQUIRED = 3  # the Survivor NPC appears after this many cleanses

SURVIVOR_STOCK = [
    ("Saint's Reliquary",     800),
    ("Bonesinger's Salt",     600),
    ("Pall-Banishing Tonic", 1000),
]

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
}

REBORN_ECHO_BASE = 30  # baseline Echo for a Reborn — boosted by what was done
REBORN_ECHO_PER_LEVEL = 3
REBORN_ECHO_PER_UNLOCK = 5
PURIFY_CLEANSES_REQUIRED = 5  # the realm needs to be cleansed this many times


def _buy_potion(player, io, name, cost):
    """Common path for a 'spend gold, gain one consumable' shop transaction."""
    if player.gold >= cost:
        player.gold -= cost
        player.consumables.append(name)
        io.show(f"\n✅ Bought a {name}!")
    else:
        io.show("\n❌ Not enough gold!")


def _potion_label(name, cost, unlocked, need, have):
    """One menu line for a potion, locked or unlocked."""
    if unlocked:
        return f"{name} ({cost} gold)"
    return (f"🔒 {name} ({cost} gold) — defeat {need} region champion"
            f"{'s' if need != 1 else ''} to unlock (now: {have})")


def shop(state):
    player, io = state.player, state.io
    io.clear()
    io.show_slow("🏪 Welcome to the Shop!\n")
    while True:
        atk_cost = player.attack * ATTACK_UPGRADE_GOLD_PER_POINT
        def_cost = player.defense * DEFENSE_UPGRADE_GOLD_PER_POINT
        champions = len(chronicle.unlocked(state.chronicle_dir))
        sovereign_unlocked = champions >= SOVEREIGN_UNLOCK_CHAMPIONS
        pall_unlocked = champions >= PALL_DRINKER_UNLOCK_CHAMPIONS
        io.show(hud(player))
        io.show(f"\n1. Health Potion ({POTION_COST} gold)")
        io.show(f"2. Greater Potion ({GREATER_POTION_COST} gold)")
        io.show("3. " + _potion_label("Sovereign Potion", SOVEREIGN_POTION_COST,
                                      sovereign_unlocked,
                                      SOVEREIGN_UNLOCK_CHAMPIONS, champions))
        io.show("4. " + _potion_label("Pall-Drinker", PALL_DRINKER_COST,
                                      pall_unlocked,
                                      PALL_DRINKER_UNLOCK_CHAMPIONS, champions))
        io.show(f"5. Upgrade Attack (+5 attack, {atk_cost} gold)")
        io.show(f"6. Upgrade Defense (+3 defense, {def_cost} gold)")
        io.show("7. Leave Shop")
        choice = io.ask("\nWhat would you like? ")

        if choice == "1":
            _buy_potion(player, io, "Health Potion", POTION_COST)
        elif choice == "2":
            _buy_potion(player, io, "Greater Potion", GREATER_POTION_COST)
        elif choice == "3":
            if not sovereign_unlocked:
                io.show(f"\n🔒 Sovereign Potion stays locked until "
                        f"{SOVEREIGN_UNLOCK_CHAMPIONS} region champion"
                        f"{'s have' if SOVEREIGN_UNLOCK_CHAMPIONS != 1 else ' has'}"
                        f" fallen to you.")
            else:
                _buy_potion(player, io, "Sovereign Potion", SOVEREIGN_POTION_COST)
        elif choice == "4":
            if not pall_unlocked:
                io.show(f"\n🔒 The Pall-Drinker stays locked until "
                        f"{PALL_DRINKER_UNLOCK_CHAMPIONS} region champions "
                        f"have fallen to you.")
            else:
                _buy_potion(player, io, "Pall-Drinker", PALL_DRINKER_COST)
        elif choice == "5":
            if player.gold >= atk_cost:
                player.gold -= atk_cost
                player.attack += 5
                io.show(f"\n✅ Attack increased to {player.attack}!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "6":
            if player.gold >= def_cost:
                player.gold -= def_cost
                player.defense += 3
                io.show(f"\n✅ Defense increased to {player.defense}!")
            else:
                io.show("\n❌ Not enough gold!")
        elif choice == "7":
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
    elif service == "smith":
        smith(state)
    elif service == "quartermaster":
        quartermaster(state)
    elif service == "pact_broker":
        pact_broker(state)
    elif service == "echo_trader":
        echo_trader(state)
    elif service == "night_hunt":
        night_hunt(state)
    elif service == "quest_board":
        quest_board(state)
    elif service == "survivor":
        survivor(state)
    elif service == "beastmaster":
        beastmaster(state)
    elif service == "hireling_hall":
        hireling_hall(state)


def hireling_hall(state):
    """Hire a Sworn — a vulnerable ally that tanks blows in your place.

    Only one hireling at a time. Hiring replaces any current one. Cost is
    gold. If the hireling dies in combat they are gone for the rest of the
    run and may return as a Forsaken Sworn in the random encounter pool.
    """
    player, content, io = state.player, state.content, state.io
    catalog = list(content.hirelings.items())
    io.clear()
    io.show_slow("🛡️  The Hireling Hall: men and women without a banner to follow.\n")
    while True:
        io.show(hud(player))
        if player.hireling is not None:
            io.show(f"\nSworn to you: {player.hireling.name}")
            io.show(f"  {player.hireling.summary()}")
        else:
            io.show("\nNo one walks at your side.")
        for index, (hireling_id, entry) in enumerate(catalog, start=1):
            tag = ""
            if (player.hireling is not None
                    and player.hireling.hireling_id == hireling_id):
                tag = "  (already with you)"
            io.show(f"\n{index}. {entry['name']} ({entry['cost']} gold){tag}")
            io.show(f"   ❤️{entry['max_hp']} HP, 🛡️{entry['defense']} def, "
                    f"heals you {entry['heal_per_round']}/round")
            io.show(f"   {entry['flavor']}")
        leave_idx = len(catalog) + 1
        io.show(f"\n{leave_idx}. Leave")
        choice = io.ask("\nWhat would you like? ")
        if choice == str(leave_idx):
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(catalog)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        hireling_id, entry = catalog[int(choice) - 1]
        if (player.hireling is not None
                and player.hireling.hireling_id == hireling_id):
            io.show("\nThis one already walks at your side.")
            io.pause(1)
            continue
        if player.gold < entry["cost"]:
            io.show("\n❌ Not enough gold!")
            io.pause(1)
            continue
        player.gold -= entry["cost"]
        player.hireling = make_hireling(content, hireling_id)
        io.show_slow(f"\n🛡️  {player.hireling.name} swears to walk with you.")
        io.pause(1)


def beastmaster(state):
    """The Beastmaster: buy a pet for gold OR trade enemy trophies for one.

    Pets are equipment in the new pet slot — bought once, owned forever
    across runs via the Chronicle. The trophy path is the brother's
    'impossible quest': hoard ~50 of a specific enemy's drops to claim the
    pet thematically tied to that enemy.
    """
    player, content, io = state.player, state.content, state.io
    catalog = list(content.pets.items())
    io.clear()
    io.show_slow("🐾 The Beastmaster's pen smells of grey rain and warm fur.\n")
    while True:
        owned = chronicle.owned_pets(state.chronicle_dir)
        equipped = player.equipment.get("pet")
        io.show(hud(player))
        if player.trophies:
            io.show("\nTrophies in your bag: " + ", ".join(
                f"{n.replace('_', ' ')}×{c}" for n, c in player.trophies.items()))
        io.show(f"\nWorn pet: {equipped.name if equipped else '(none)'}")
        for index, (pet_id, entry) in enumerate(catalog, start=1):
            is_owned = pet_id in owned
            is_eq = equipped is not None and equipped.pet_id == pet_id
            tag = "  ✓ equipped" if is_eq else ("  (owned)" if is_owned else "")
            io.show(f"\n{index}. {entry['name']}{tag}")
            stats_bits = [f"+{v} {k.replace('_', ' ')}"
                          for k, v in entry.get("stats", {}).items()]
            if entry.get("regen_per_round"):
                stats_bits.append(f"+{entry['regen_per_round']} HP/round")
            io.show(f"   {'  '.join(stats_bits) or '(no bonuses)'}")
            if not is_owned:
                trophy = entry["trophy"]
                req = entry["trophy_required"]
                have = player.trophies.get(trophy, 0)
                io.show(f"   {entry['gold_cost']} gold  OR  "
                        f"{req}×{trophy.replace('_', ' ')} ({have} carried)")
        leave_idx = len(catalog) + 1
        io.show(f"\n{leave_idx}. Leave")
        choice = io.ask("\nWhat would you like? ")
        if choice == str(leave_idx):
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(catalog)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        pet_id, entry = catalog[int(choice) - 1]
        if pet_id in owned:
            # Equip / unequip toggle.
            if equipped is not None and equipped.pet_id == pet_id:
                player.unequip_pet()
                io.show(f"\nYou release the {entry['name']} from your side.")
            else:
                player.equip_pet(make_pet(content, pet_id))
                io.show(f"\nThe {entry['name']} comes to heel.")
            io.pause(1)
            continue
        # Not owned — buy with gold OR trade trophies.
        trophy = entry["trophy"]
        have = player.trophies.get(trophy, 0)
        if have >= entry["trophy_required"]:
            io.show("\nYou pour the trophies onto the table. The Beastmaster nods.")
            player.trophies[trophy] = have - entry["trophy_required"]
        elif player.gold >= entry["gold_cost"]:
            io.show("\nYou hand over the gold. The Beastmaster pockets it without counting.")
            player.gold -= entry["gold_cost"]
        else:
            io.show(f"\n❌ Not enough gold AND not enough trophies "
                    f"(need {entry['trophy_required']}, have {have}).")
            io.pause(1)
            continue
        chronicle.own_pet(pet_id, state.chronicle_dir)
        player.equip_pet(make_pet(content, pet_id))
        io.show_slow(f"\n🐾 The {entry['name']} is yours now, and stays yours.")
        io.pause(1)


def survivor(state):
    """The Gravewatch Survivor: a fighter who outlived the Pall, now selling relics."""
    player, io = state.player, state.io
    io.clear()
    io.show_slow("🕊️  The Survivor — pale, scarred, still warm. She has fought it longer.\n")
    while True:
        io.show(hud(player))
        for index, (name, cost) in enumerate(SURVIVOR_STOCK, start=1):
            io.show(f"\n{index}. {name} ({cost} gold)")
            io.show(f"   {_consumable_label(name)}")
        leave_idx = len(SURVIVOR_STOCK) + 1
        io.show(f"\n{leave_idx}. Leave")
        choice = io.ask("\nWhat would you like? ")
        if choice == str(leave_idx):
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(SURVIVOR_STOCK)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        name, cost = SURVIVOR_STOCK[int(choice) - 1]
        if player.gold < cost:
            io.show("\n❌ Not enough gold!")
            io.pause(1)
            continue
        player.gold -= cost
        player.consumables.append(name)
        io.show(f"\n✅ The Survivor presses the {name} into your hand.")
        io.pause(1)


def _quest_status(state, quest_id):
    """Return one of: 'available', 'active', 'completable', 'claimed'."""
    if quest_id in state.flags.get("completed_quests", []):
        return "claimed"
    if quest_id not in state.flags.get("active_quests", []):
        return "available"
    progress = state.flags.get("quest_progress", {}).get(quest_id, 0)
    if progress >= QUESTS[quest_id]["needed"]:
        return "completable"
    return "active"


def quest_board(state):
    """The Gravewatch quest board: pick up bounty quests, claim rewards on completion.

    Higher-tier bounties are gated by cleanse count — the Board only pins a
    new slip after each successful run, so deeper quests open as the realm
    is cleansed.
    """
    player, io = state.player, state.io
    cleanses = chronicle.cleanses(state.chronicle_dir)
    catalog = [(qid, q) for qid, q in QUESTS.items()
               if q.get("cleanse_required", 0) <= cleanses]
    io.clear()
    io.show_slow("📜 The Quest Board — slips of vellum pinned with rust nails.\n")
    while True:
        io.show(hud(player))
        for index, (quest_id, quest) in enumerate(catalog, start=1):
            status = _quest_status(state, quest_id)
            progress = state.flags.get("quest_progress", {}).get(quest_id, 0)
            tag = {
                "available":   f"[{quest['reward_gold']}g + a class flask]",
                "active":      f"[{progress}/{quest['needed']} {quest['target_enemy']}s]",
                "completable": "[READY TO CLAIM]",
                "claimed":     "[done]",
            }[status]
            io.show(f"\n{index}. {quest['name']}  {tag}")
            io.show(f"   {quest['flavor']}")
        io.show(f"\n{len(catalog) + 1}. Leave")
        choice = io.ask("\nWhat would you like? ")
        if choice == str(len(catalog) + 1):
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(catalog)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        quest_id, quest = catalog[int(choice) - 1]
        status = _quest_status(state, quest_id)
        if status == "available":
            state.flags.setdefault("active_quests", []).append(quest_id)
            state.flags.setdefault("quest_progress", {})[quest_id] = 0
            io.show_slow(f"\n📜 You take the slip: {quest['name']}.")
            io.pause(1)
        elif status == "active":
            progress = state.flags["quest_progress"][quest_id]
            io.show(f"\nNot finished yet: {progress}/{quest['needed']} "
                    f"{quest['target_enemy']}s.")
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
            io.pause(2)
        else:  # claimed
            io.show("\nAlready claimed. The Board has no other use for you.")
            io.pause(1)


def night_hunt(state):
    """Pay gold to go out at night and pick one boosted fight from the road's pool.

    Pulls an enemy id from a zone the player has already passed through (one
    at or below their level), boosts its stats by NIGHT_HUNT_STAT_BOOST, and
    runs a single fight. Rewards (XP + gold) are scaled by NIGHT_HUNT_REWARD_MULT
    on success. Brother's design — risk for reward — without inventing a full
    day/night clock.
    """
    player, content, io, rng = state.player, state.content, state.io, state.rng
    if player.gold < NIGHT_HUNT_COST:
        io.show(f"\n❌ The Night Hunt costs {NIGHT_HUNT_COST} gold — "
                f"you don't carry enough.")
        io.pause(1)
        return
    # Pool: enemies from zones the player is allowed to be in (act-relevant).
    pool = []
    for loc in content.locations.values():
        rec = loc.get("recommended_level", 1)
        if loc.get("kind") != "zone" or loc.get("boss") or rec > player.level + 1:
            continue
        for encounter in loc.get("encounters", []):
            if encounter.get("type") != "combat" or encounter.get("boss"):
                continue
            pool.extend(encounter.get("enemies", []))
    pool = [e for e in pool if not content.enemies[e].get("unique")]
    if not pool:
        io.show("\n🌑 No prey worth chasing tonight.")
        io.pause(1)
        return
    player.gold -= NIGHT_HUNT_COST
    enemy_id = rng.choice(pool)
    enemy = make_enemy(enemy_id, content)
    enemy.max_hp = int(enemy.max_hp * NIGHT_HUNT_STAT_BOOST)
    enemy.hp = enemy.max_hp
    enemy.attack = int(enemy.attack * NIGHT_HUNT_STAT_BOOST)
    enemy.xp_reward = int(enemy.xp_reward * NIGHT_HUNT_REWARD_MULT)
    enemy.gold_reward = int(enemy.gold_reward * NIGHT_HUNT_REWARD_MULT)
    enemy.name = f"Night-Stalking {enemy.name}"
    io.clear()
    io.show_slow("🌑 You leave the firelight behind. The grey closes in faster.")
    io.show_slow("Something heavier waits at the road's edge tonight.\n")
    io.pause(1)
    run_combat(state, enemy)


def echo_trader(state):
    """The Gravewatch Echo Trader: buy trinkets and rings with Echo currency.

    Echo is earned only by completing the run and choosing Reborn — the
    prestige loop. Bought accessories are permanently owned across all
    future runs (stored in the Chronicle) and can be equipped here.
    """
    player, content, io = state.player, state.content, state.io
    catalog = list(content.accessories.items())
    io.clear()
    io.show_slow("🕯️  The Echo Trader speaks softly. The dead can be heard, "
                 "if you brought their coin.\n")
    while True:
        balance = chronicle.echoes(state.chronicle_dir)
        owned = chronicle.owned_accessories(state.chronicle_dir)
        equipped = {slot: player.equipment.get(slot)
                    for slot in ("trinket", "ring")}
        io.show(hud(player))
        io.show(f"\n💀 Echoes: {balance}")
        io.show(f"\nTrinket: {equipped['trinket'].name if equipped['trinket'] else '(none)'}")
        io.show(f"Ring:    {equipped['ring'].name if equipped['ring'] else '(none)'}")
        for index, (accessory_id, entry) in enumerate(catalog, start=1):
            is_owned = accessory_id in owned
            is_equipped = (equipped[entry["slot"]] is not None
                           and equipped[entry["slot"]].accessory_id == accessory_id)
            tag = "  ✓ equipped" if is_equipped else (
                "  (owned)" if is_owned else f"  cost {entry['cost']} Echo")
            stats_bits = [f"+{int(v * 100)}% {k.replace('_', ' ')}"
                          if k in ("crit_bonus", "dodge_chance")
                          else f"+{v} {k.replace('_', ' ')}"
                          for k, v in entry.get("stats", {}).items()]
            io.show(f"\n{index}. {entry['name']} [{entry['slot']}]{tag}")
            io.show(f"   {'  '.join(stats_bits) or '(no bonuses)'}")
        leave_idx = len(catalog) + 1
        io.show(f"\n{leave_idx}. Leave")
        choice = io.ask("\nWhat would you like? ")
        if choice == str(leave_idx):
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(catalog)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        accessory_id, entry = catalog[int(choice) - 1]
        if accessory_id in owned:
            # Owned — toggle equip/unequip.
            slot = entry["slot"]
            if (equipped[slot] is not None
                    and equipped[slot].accessory_id == accessory_id):
                player.unequip_accessory(slot)
                io.show(f"\nYou take off the {entry['name']}.")
            else:
                player.equip_accessory(make_accessory(content, accessory_id))
                io.show(f"\nYou put on the {entry['name']}.")
            io.pause(1)
            continue
        # Not owned — try to buy with Echoes.
        if balance < entry["cost"]:
            io.show(f"\n💀 Not enough Echoes "
                    f"(have {balance}, need {entry['cost']}).")
            io.pause(1)
            continue
        chronicle.spend_echoes(entry["cost"], state.chronicle_dir)
        chronicle.own_accessory(accessory_id, state.chronicle_dir)
        player.equip_accessory(make_accessory(content, accessory_id))
        io.show_slow(f"\n🕯️  The {entry['name']} is yours, and stays yours.")
        io.pause(1)


def pact_broker(state):
    """The Gravewatch Pact-Broker: bind a spirit companion to your run.

    A companion strikes (or mends) once per round after your turn. Only one
    companion at a time — you must release the current one to bind another.
    Persists for the run via state save/load.
    """
    player, content, io = state.player, state.content, state.io
    catalog = list(content.companions.items())
    io.clear()
    io.show_slow("🐺 Welcome to the Pact-Broker.\n")
    while True:
        io.show(hud(player))
        if player.companion is not None:
            io.show(f"\nBound to you: {player.companion.name}")
            io.show(f"  {player.companion.summary()}")
        else:
            io.show("\nNo spirit walks with you yet.")
        for index, (companion_id, entry) in enumerate(catalog, start=1):
            bound = (player.companion is not None
                     and player.companion.companion_id == companion_id)
            tag = "  (bound)" if bound else ""
            effect = (f"strikes for {entry['power']}" if entry["kind"] == "damage"
                      else f"mends {entry['power']} HP/turn")
            io.show(f"\n{index}. {entry['name']} ({entry['cost']} gold){tag}")
            io.show(f"   {effect}")
        next_index = len(catalog) + 1
        if player.companion is not None:
            io.show(f"\n{next_index}. Release current companion")
            io.show(f"{next_index + 1}. Leave")
            leave_choice = str(next_index + 1)
            release_choice = str(next_index)
        else:
            io.show(f"\n{next_index}. Leave")
            leave_choice = str(next_index)
            release_choice = None
        choice = io.ask("\nWhat would you like? ")
        if choice == leave_choice:
            return
        if release_choice is not None and choice == release_choice:
            io.show_slow(f"\nYou release {player.companion.name}. The road "
                         f"is yours alone again.")
            player.companion = None
            io.pause(1)
            continue
        if not (choice.isdigit() and 1 <= int(choice) <= len(catalog)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        companion_id, entry = catalog[int(choice) - 1]
        if (player.companion is not None
                and player.companion.companion_id == companion_id):
            io.show("\nThis spirit already walks with you.")
            io.pause(1)
            continue
        if player.companion is not None:
            io.show("\nRelease your current companion first.")
            io.pause(1)
            continue
        if player.gold < entry["cost"]:
            io.show("\n❌ Not enough gold!")
            io.pause(1)
            continue
        player.gold -= entry["cost"]
        player.companion = make_companion(content, companion_id)
        io.show_slow(f"\n🐺 {player.companion.name} pledges to walk the road "
                     f"with you.")
        io.pause(1)


def quartermaster(state):
    """The Gravewatch quartermaster: buy armor pieces (defense + dodge chance).

    Each piece is an alternative to the one you wear. Buying auto-equips the
    new piece; the old armor is simply discarded — these are not collected,
    only worn.
    """
    player, content, io = state.player, state.content, state.io
    catalog = list(content.armor.items())
    io.clear()
    io.show_slow("🛡️  Welcome to the Quartermaster.\n")
    while True:
        current = player.equipment.get("armor")
        io.show(hud(player))
        if current is not None:
            io.show(f"\nYou wear: {current.name}")
            io.show(f"  {current.summary()}")
        else:
            io.show("\nYou wear no armor.")
        for index, (armor_id, entry) in enumerate(catalog, start=1):
            equipped = current is not None and current.armor_id == armor_id
            tag = "  (equipped)" if equipped else ""
            io.show(f"\n{index}. {entry['name']} ({entry['cost']} gold){tag}")
            stats_bits = [f"+{v} {k.replace('_', ' ')}"
                          for k, v in entry.get("stats", {}).items()]
            dodge = entry.get("dodge_chance", 0)
            if dodge:
                stats_bits.append(f"{int(dodge * 100)}% dodge")
            io.show(f"   {'  '.join(stats_bits) or '(no bonuses)'}")
        io.show(f"\n{len(catalog) + 1}. Leave")
        choice = io.ask("\nWhat would you like? ")
        if choice == str(len(catalog) + 1):
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(catalog)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        armor_id, entry = catalog[int(choice) - 1]
        if current is not None and current.armor_id == armor_id:
            io.show("\nYou already wear this piece.")
            io.pause(1)
            continue
        if player.gold < entry["cost"]:
            io.show("\n❌ Not enough gold!")
            io.pause(1)
            continue
        player.gold -= entry["cost"]
        player.equip_armor(make_armor(content, armor_id))
        io.show_slow(f"\n🛡️  You buckle on the {entry['name']}.")
        io.pause(1)


def smith(state):
    """The Gravewatch smith: enchant your weapon with one permanent upgrade.

    Each weapon can only be upgraded once — the smith refuses to re-temper a
    blade already touched. The player's currently-equipped weapon is the only
    candidate; an upgrade is paid in gold and persists through save/load.
    """
    player, io = state.player, state.io
    io.clear()
    io.show_slow("⚒  Welcome to the Smith.\n")
    while True:
        weapon = player.equipment.get("weapon")
        io.show(hud(player))
        if weapon is None:
            io.show("\nYou carry no weapon to temper.")
            io.show("\n1. Leave")
            io.ask("\nWhat would you like? ")
            return
        io.show(f"\nWeapon on the anvil: {weapon.name}")
        io.show(f"  {weapon.summary()}")
        if weapon.upgrade is not None:
            io.show(f"\nThis weapon has already been worked "
                    f"({WEAPON_UPGRADES[weapon.upgrade]['name']}).")
            io.show("The smith refuses to temper it a second time.")
            io.show("\n1. Leave")
            choice = io.ask("\nWhat would you like? ")
            if choice == "1":
                return
            io.show("\n❌ Invalid choice!")
            continue
        upgrades = list(WEAPON_UPGRADES.items())
        for index, (_uid, upgrade) in enumerate(upgrades, start=1):
            io.show(f"\n{index}. {upgrade['name']} ({upgrade['cost']} gold) "
                    f"— {upgrade['blurb']}")
        io.show(f"\n{len(upgrades) + 1}. Leave")
        choice = io.ask("\nWhat would you like? ")
        if choice == str(len(upgrades) + 1):
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(upgrades)):
            io.show("\n❌ Invalid choice!")
            io.pause(1)
            continue
        uid, upgrade = upgrades[int(choice) - 1]
        if player.gold < upgrade["cost"]:
            io.show("\n❌ Not enough gold!")
            io.pause(1)
            continue
        # Re-equip to apply the upgrade's stat bonuses cleanly.
        player.unequip_weapon()
        weapon.upgrade = uid
        player.equip_weapon(weapon)
        player.gold -= upgrade["cost"]
        io.show_slow(f"\n⚒  The smith works the {weapon.name} into the "
                     f"{upgrade['name']}.")
        io.show(f"   {weapon.summary()}")
        io.pause(1)


def _make_forsaken_sworn(fallen_dict):
    """Build a beefed-up enemy from a hireling's dying form. v0.8 mechanic.

    A fallen hireling rises grimdark — same stats, but the Pall has sharpened
    them. Returns an ``Enemy`` the combat loop accepts.
    """
    from .enemy import Enemy
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


def _run_discovery(state, encounter):
    """Reveal a one-time lore fragment, then mark it found in ``state.flags``."""
    io = state.io
    io.clear()
    for line in encounter["lines"]:
        io.show_slow(line)
    io.pause(2)
    state.flags.setdefault("discoveries_seen", []).append(encounter["id"])


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
    io, rng, content = state.io, state.rng, state.content
    if encounter["type"] != "combat":
        return None

    candidates = _hollowed_candidates(state, fallen)
    hollowed_entry = None
    fallen_hireling = state.flags.get("fallen_hireling")
    if encounter.get("boss") and wardens:
        enemies = [make_warden(wardens[-1], content)]
    elif (encounter.get("pick") == "random" and fallen_hireling
          and rng.random() < FORSAKEN_CHANCE):
        enemies = [_make_forsaken_sworn(fallen_hireling)]
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
    if outcome == "victory" and enemy is not None and enemy.unique:
        chronicle.unlock(enemy.enemy_id, state.chronicle_dir)
    if outcome == "victory" and not encounter.get("boss"):
        _offer_drop(state)
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


def _run_summary(state):
    """The end-of-run recap — the hero, the build they carried, and the seed."""
    player, io = state.player, state.io
    place = state.content.locations[state.current_location]["name"]
    weapon = player.equipment.get("weapon")
    io.show("\n" + "─" * 50)
    io.show(f"  {player.name} the {player.class_name}, level {player.level}")
    io.show(f"  Last stood in {place}, with {player.gold} gold.")
    if weapon is not None:
        io.show(f"  Wielding {weapon.name} — {weapon.summary()}")
    if state.seed:
        io.show(f"  This run was seeded: {state.seed}")
    io.show("─" * 50)


def _victory_screen(state):
    """The end screen: the Warden falls — and the player chooses their fate.

    Two endings, with a third unlocked once the realm has been cleansed
    PURIFY_CLEANSES_REQUIRED times. Warden = kept by the Pall (canon).
    Reborn = refuse and earn Echoes (prestige). Purify = end the cycle
    forever (mythic, gated).
    """
    player, io = state.player, state.io
    cleanses = chronicle.cleanses(state.chronicle_dir)
    can_purify = cleanses >= PURIFY_CLEANSES_REQUIRED
    io.clear()
    io.show_slow("The Shadow Warden comes apart like wet ash. The Pall, finding")
    io.show_slow("itself without a Warden, turns to the soul still standing on")
    io.show_slow("the Summit. It reaches.\n")
    io.pause(1)
    io.show("You can let it take you, and become the next Warden — the one")
    io.show("future climbers will have to break to free this place.")
    io.show("\nOr you can refuse it. The Pall does not let go for nothing.")
    io.show("It will take everything you have, except what the dead carry —")
    io.show("the Echoes of what you've done. With those, you can come back.")
    if can_purify:
        io.show("\nOr — for the first and last time — you can refuse the cycle itself.")
        io.show("Five times the realm has been cleansed by your hand. The Pall is thin")
        io.show("enough now to be unmade. You will not come back from this choice.")
    io.show("\n1. Be kept by the Pall  (end the run, become the Warden)")
    io.show("2. Reborn               (end this hero — earn Echoes — start again)")
    if can_purify:
        io.show("3. 🌅 Purify Mournhold  (end the cycle — the Pall is undone)")
    choice = io.ask("\nYour choice? ")
    if choice == "2":
        _reborn_screen(state)
        return
    if choice == "3" and can_purify:
        _purify_screen(state)
        return
    chronicle.record(state, "warden", state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    io.clear()
    io.show("=" * 50)
    io.show("🥀  THE PALL KEEPS YOU")
    io.show(f"{player.name} the {player.class_name} — Warden of the Shrouded Summit")
    io.show("\nYou will not climb down. You will wait here, wearing your own")
    io.show("face, until the next soul reaches the Summit to break you —")
    io.show("as you broke the one before.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _reborn_screen(state):
    """The Reborn ending — earn Echoes (Chronicle currency) and end this run."""
    player, io = state.player, state.io
    unlock_count = len(chronicle.unlocked(state.chronicle_dir))
    echoes_earned = (REBORN_ECHO_BASE
                     + player.level * REBORN_ECHO_PER_LEVEL
                     + unlock_count * REBORN_ECHO_PER_UNLOCK)
    chronicle.add_echoes(echoes_earned, state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    # The Reborn hero is NOT chronicled as a Warden — they refused the Pall.
    io.clear()
    io.show_slow("You turn the Pall's reach aside. The Summit empties of you,")
    io.show_slow("the road empties of you, the kingdom forgets you — almost.")
    io.show_slow("Only the Echoes follow you back. The dead remember coin.\n")
    io.show("=" * 50)
    io.show("💀  REBORN")
    io.show(f"{player.name} the {player.class_name} — refused.")
    io.show(f"\nEchoes earned this run: {echoes_earned}")
    io.show(f"Echoes total: {chronicle.echoes(state.chronicle_dir)}")
    owned = chronicle.owned_accessories(state.chronicle_dir)
    if owned:
        io.show(f"\nAccessories you carry across the dark: {len(owned)}")
    io.show("=" * 50)
    io.show("\nStart a new run from the title screen — visit the Echo Trader")
    io.show("at Gravewatch to spend what you earned.")
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _purify_screen(state):
    """The mythic ending — the Pall is undone permanently."""
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    io.clear()
    io.show_slow("You do not let the Pall take you, and you do not refuse it,")
    io.show_slow("and you do not climb back down. You stand still, and you")
    io.show_slow("speak — every name the kingdom forgot, from the first sealed gate")
    io.show_slow("to the last hold under the silt. You speak them all. Aloud. In order.\n")
    io.pause(1)
    io.show_slow("The Pall stops, the way a wound stops. The summit goes quiet,")
    io.show_slow("the way a long-held breath goes quiet. The grey thins, and thins,")
    io.show_slow("and is gone. The road behind you is bright. The road behind that")
    io.show_slow("is bright. The kingdom remembers itself.\n")
    io.pause(2)
    io.show("=" * 50)
    io.show("🌅  MOURNHOLD IS PURIFIED")
    io.show(f"{player.name} the {player.class_name} — who said the names back.")
    io.show("\nThe Pall is undone. The Warden is no more. The road is only road.")
    io.show("Future climbers will find a kingdom, not a kingdom's grave.")
    io.show("\nThe Chronicle remembers — you will see, on every next run,")
    io.show("that Mournhold lies PURIFIED. The cycle is broken.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


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
    return True


def _build_options(state, loc, fallen):
    """Build the ordered list of ``(label, (kind, arg))`` menu entries."""
    player, content = state.player, state.content
    options = []
    for service in loc.get("services", []):
        if not _service_is_visible(state, service):
            continue
        options.append((_SERVICE_LABELS[service], ("service", service)))
    for encounter in loc.get("encounters", []):
        if (encounter["type"] == "discovery"
                and encounter["id"] in state.flags.get("discoveries_seen", [])):
            continue
        options.append((_encounter_label(encounter, content), ("encounter", encounter)))
    if _grave_here(state, loc, fallen):
        options.append(("🪦 Search a grave", ("grave", None)))
    for dest_id in loc.get("connections", []):
        dest = content.locations[dest_id]
        options.append((_travel_label(dest, player), ("travel", dest_id)))
    # Fast travel back to the Crossroads — one-way, available from any zone
    # (not from hub/settlements, not from the Summit). Preserves the descent
    # outbound while letting the player shortcut the long walk home.
    if loc.get("kind") == "zone" and not loc.get("boss"):
        options.append(("🛤️  Walk back to the Crossroads", ("fast_travel", None)))
    # At the Crossroads, if the player fast-travelled here from somewhere,
    # offer a paired "Return to ..." so the round-trip isn't a long walk back.
    return_target = state.flags.get("fast_travel_return")
    if (state.current_location == "crossroads"
            and return_target in content.locations):
        target_name = content.locations[return_target]["name"]
        options.append((f"🛤️  Return to {target_name}",
                        ("fast_travel_return", return_target)))
    options.append(("🗡️  Inspect Weapon", ("weapon", None)))
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
            # Cleansed intros (v0.7) show after the first completed run — the
            # world begins to remember itself as the player keeps climbing.
            intro_key = ("intro_cleansed"
                         if chronicle.cleanses(state.chronicle_dir) >= 1
                         and "intro_cleansed" in loc
                         else "intro")
            for line in loc[intro_key]:
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
        elif kind == "fast_travel":
            # Remember where we came from so the Crossroads can offer a return.
            state.flags["fast_travel_return"] = state.current_location
            io.show_slow("\n🛤️  You leave the grey road behind and walk back "
                         "the long way to the Crossroads.")
            io.pause(1)
            state.current_location = "crossroads"
            arrived = True
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
            show_stats(io, player)
        elif kind == "save":
            _save_menu(state)
        elif kind == "quit":
            io.show("\n👋 Thanks for playing!")
            return

    chronicle.record(state, "fell", state.chronicle_dir)
    io.clear()
    io.show_slow("💀 The Pall takes another. It always does.")
    _run_summary(state)
    io.show("\nGame Over!")

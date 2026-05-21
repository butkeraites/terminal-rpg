"""Explorable locations and the main game loop.

The world is a graph of locations loaded from ``data/locations.json``.
``location_loop`` is the central loop: it renders the player's current
location, offers its services, encounters and travel routes, and runs
until the player dies, wins, or quits.
"""
from . import chronicle, endings, saves
from . import dialogue as _dialogue
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
    "scholar": "📚 Speak with the Mournhold Scholar",
    "reader": "📖 Read with the Reader",
    "insomniac": "🕯️  Sit with the Insomniac",
    "caretaker": "🌹 Become the Caretaker",
}

# SQ1 — The Reader Who Watches Back surfaces in Gravewatch after this many
# unique lore discoveries have been read across all runs.
READER_THRESHOLD = 25

# SQ6 — The Insomniac of Gravewatch surfaces after this many cross-run visits.
INSOMNIAC_THRESHOLD = 50

# SQ2 — The Caretaker ending surfaces after this many small kindnesses.
CARETAKER_THRESHOLD = 40

# v1.2 — after this many cross-run visits to a zone, switch to its
# ``intro_familiar`` variant if defined: the kingdom starts speaking
# to the player in past-tense recognition instead of cold-open description.
FAMILIAR_VISITS = 5

SCHOLAR_PAYOUT = 75  # gold per unique lore discovery she records

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
    elif service == "scholar":
        scholar(state)
    elif service == "reader":
        reader(state)
    elif service == "insomniac":
        insomniac(state)
    elif service == "caretaker":
        caretaker(state)


def scholar(state):
    """The Mournhold Scholar — unlocked by the Old Penitent NPC's quest.

    Pays gold for every lore discovery the player has logged in their
    state.flags['discoveries_seen'] list, AND for state.flags['scholar_paid']
    tracks which ones she has already paid for so she doesn't double-pay.
    """
    player, io = state.player, state.io
    seen = state.flags.get("discoveries_seen", [])
    paid = state.flags.setdefault("scholar_paid", [])
    unpaid = [d for d in seen if d not in paid]
    io.clear()
    io.show_slow("📚 The Mournhold Scholar settles at her desk, quill ready.\n")
    io.show(hud(player))
    if not unpaid:
        io.show("\n'I have written down everything you have brought me. "
                "Bring me more.'")
        io.show("\n1. Leave")
        io.ask("\nWhat would you like? ")
        return
    io.show(f"\nShe has not yet paid you for {len(unpaid)} of your discoveries.")
    io.show(f"At {SCHOLAR_PAYOUT} gold each, she owes you "
            f"{len(unpaid) * SCHOLAR_PAYOUT} gold.")
    io.show("\n1. Hand them over and take payment")
    io.show("2. Leave")
    choice = io.ask("\nWhat would you like? ")
    if choice == "1":
        payout = len(unpaid) * SCHOLAR_PAYOUT
        player.gold += payout
        paid.extend(unpaid)
        io.show_slow(f"\n📚 She takes the lot, and counts out {payout} gold.")
        io.pause(1)


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
    enemy = make_enemy(enemy_id, content, state.flags)
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
    io.pause(2)
    discovery_id = encounter["id"]
    state.flags.setdefault("discoveries_seen", []).append(discovery_id)
    # SQ1 — every discovery the player reads is also recorded cross-run.
    chronicle.add_read_discovery(discovery_id, state.chronicle_dir)
    # SQ2 — reading lore is one of the small kindnesses.
    chronicle.add_kind_act(state.chronicle_dir)
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


_VICTORY_LEAD_IN = [
    "The Shadow Warden comes apart like wet ash. The Pall, finding",
    "itself without a Warden, turns to the soul still standing on",
    "the Summit. It reaches.\n",
]


def _victory_screen(state):
    """Dispatch to the player's chosen ending via the endings registry."""
    endings.choose_and_render(state, _VICTORY_LEAD_IN)


def _warden_screen(state):
    """The canonical ending: the Pall keeps the victor as the next Warden.

    If the player has read the Real Minutes (Arc I), the ending names the
    full council vote — they are the seventh to keep this place, fully
    informed of what they inherit.
    """
    player, io = state.player, state.io
    chronicle.record(state, "warden", state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("warden", state.chronicle_dir)
    io.clear()
    io.show("=" * 50)
    io.show("🥀  THE PALL KEEPS YOU")
    io.show(f"{player.name} the {player.class_name} — Warden of the Shrouded Summit")
    io.show("\nYou will not climb down. You will wait here, wearing your own")
    io.show("face, until the next soul reaches the Summit to break you —")
    io.show("as you broke the one before.")
    if state.flags.get("read_real_minutes"):
        io.show("")
        io.show("You know the names of the six who voted to seal the gates.")
        io.show("You know the names of the five who voted to open them, and were silenced.")
        io.show("You know which side the Chairman sat on, and what he did to the five.")
        io.show("You knew all of this and you let the Pall take you anyway.")
        io.show("You are the seventh to keep this place. You are the first to keep it knowing.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _sister_realm_addendum(state, io):
    """Print a closing paragraph naming the sister-realm alliance, if any.

    v0.14 adds these flavour-only addenda — they do not alter the Chronicle.
    They confirm to the player that what they did at the Border carried.
    """
    if state.flags.get("allied_karst"):
        io.show("")
        io.show("In Karst, the bread moves both ways across the border again,")
        io.show("slowly, with a long winter to teach the merchants not to forget.")
    if state.flags.get("allied_wynne"):
        io.show("")
        io.show("In Wynne, the Devoured Captain lies in a grave with her name on it.")
        io.show("The Chancellor's chancellery burns the year after. No one is surprised.")
    if state.flags.get("opposed_margrave"):
        io.show("")
        io.show("In the Margrave's lands, three names are added to the relief plaque")
        io.show("for free — by a Censor who has begun to understand what it is.")


def _reborn_screen(state):
    """The Reborn ending — earn Echoes (Chronicle currency) and end this run."""
    player, io = state.player, state.io
    unlock_count = len(chronicle.unlocked(state.chronicle_dir))
    echoes_earned = (REBORN_ECHO_BASE
                     + player.level * REBORN_ECHO_PER_LEVEL
                     + unlock_count * REBORN_ECHO_PER_UNLOCK)
    chronicle.add_echoes(echoes_earned, state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("reborn", state.chronicle_dir)
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
    _sister_realm_addendum(state, io)
    io.show("=" * 50)
    io.show("\nStart a new run from the title screen — visit the Echo Trader")
    io.show("at Gravewatch to spend what you earned.")
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _reckoning_screen(state):
    """The 8th ending — help Tálva. Mournhold is unmade for what it did to the holds.

    Requires ``talva_asked`` flag — you promised Tálva at the Hidden Hold.
    Records the Chronicle as 'reckoning'. Not a clean ending. Not meant to be.
    """
    player, io = state.player, state.io
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("reckoning", state.chronicle_dir)
    io.clear()
    io.show_slow("You break the Warden. The Pall reaches.")
    io.show_slow("You do not let it take you. You do not bring the rite back to Atrél.")
    io.show_slow("You do not sit at Cael's feet. You walk down.")
    io.show_slow("You walk down past the Pre-Pall Shrine. You take a hammer to the iron tablet.")
    io.show_slow("The vow under the mountain breaks. The hunger comes up. It comes up steadily.\n")
    io.pause(1)
    io.show_slow("It eats Mournhold's name first. Then the names of every councilor who voted to seal.")
    io.show_slow("Then the rite of unremembering, eaten by what the rite was meant to forget.")
    io.show_slow("Then the holds that died inside the gates — but their names are safe.")
    io.show_slow("Their names are at the Hidden Hold. Tálva has them. She kept them.\n")
    io.pause(1)
    io.show_slow("Mournhold is unwritten. The roads bend wrong again — but they bend toward the holds.")
    io.show_slow("You walk down to the Hidden Hold. Tálva nods at you. Kerris bakes you a loaf.")
    io.show_slow("Ondrek says nothing. The Small Un asks why your hands are shaking.")
    io.show_slow("You stay. You become the kingdom's last historian. You write what was, and what wasn't.\n")
    io.pause(2)
    io.show("=" * 50)
    io.show("⚖️  THE RECKONING")
    io.show(f"{player.name} the {player.class_name} — who broke the kingdom that broke the holds.")
    io.show("\nMournhold is unmade. The Pall is undone with it.")
    io.show("Future climbers will find a country that ate itself, and a Hidden Hold that did not.")
    io.show("Symmetry. The hardest thing the holds had left to ask for.")
    io.show("\nThe Chronicle records: reckoning. The Pall is gone. So is the kingdom that fed it.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _old_seal_screen(state):
    """The seventh ending — take Cael's place as the seal beneath the mountain.

    Requires ``offered_old_seal`` (player accepted Cael's offer). Records
    'old_seal_taken' in the Chronicle. Mournhold lives without knowing.
    The hunger is sealed, not undone — the player IS the seal now.
    """
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)  # the realm survives, after all
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("old_seal", state.chronicle_dir)
    io.clear()
    io.show_slow("You break the Warden. The Pall reaches for you.")
    io.show_slow("You walk past its reaching. You walk down — past the Choir,")
    io.show_slow("past Mourncross, past the Reach, past the Witherwood, past the road.")
    io.show_slow("You walk down the stair below the Pre-Pall Shrine.\n")
    io.pause(1)
    io.show_slow("Cael stands. The stone lets her stand. Her mouth empties of names.")
    io.show_slow("She passes them to you, name by name, until you can say them all.")
    io.show_slow("Then she lies down. The stone takes her, gently, like a sheet pulled up.")
    io.show_slow("She rests. She has rested. She is resting.\n")
    io.pause(1)
    io.show_slow("You sit where she sat. The stone closes over your mouth, and your hands,")
    io.show_slow("and your name. You begin to say the names she taught you.")
    io.show_slow("Quietly. Quietly. The Pall above ground unmakes itself in silence —")
    io.show_slow("the hunger has its mouth back, and the mouth is yours now.\n")
    io.pause(2)
    io.show("=" * 50)
    io.show("🪨  THE OLD SEAL")
    io.show(f"{player.name} the {player.class_name} — the next seal under the mountain.")
    io.show("\nThe Pall is undone. The Warden is no more. Mournhold lives, and does not know.")
    io.show("You will not climb back up. You will say names. You will say them quietly.")
    io.show("Centuries from now, when the seal is tired again, someone will sit at your feet")
    io.show("and you will teach them the names — yours among them — and lie down.")
    io.show("\nThe Chronicle records: purified. The smallest, oldest, hardest ending.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _atrel_peace_screen(state):
    """The quiet ending — return the rite to Atrél; both god and Pall end together.

    Available only when ``atrel_offered`` is True (player promised Atrél to
    bring the rite back). Marks the Chronicle purified, but the screen
    deliberately does NOT name the player as the one who said the names —
    Atrél's small ending is unwitnessed by design.
    """
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("atrel_peace", state.chronicle_dir)
    io.clear()
    io.show_slow("You do not climb back to the Summit to say the names.")
    io.show_slow("You climb back down. To the Choir. To the south aisle. To Atrél.")
    io.show_slow("He is waiting. He has been waiting since you left.\n")
    io.pause(1)
    io.show_slow("You set the rite down at his altar. Not the kingdom-scale. The altar-scale.")
    io.show_slow("Atrél takes it. His hands close around it like someone receiving a wound back.")
    io.show_slow("He says: 'Thank you.' He says it small. It is the right size.")
    io.show_slow("He dies. The altar does not. Someone will set down a small grief here, one day.\n")
    io.pause(1)
    io.show_slow("And the Pall — the Pall has nothing left to be made of.")
    io.show_slow("It unmakes itself in silence. No crescendo. No witness.")
    io.show_slow("The grey goes thin. The road brightens. Nobody knows you did it.\n")
    io.pause(2)
    io.show("=" * 50)
    io.show("📿  ATRÉL'S PEACE")
    io.show(f"{player.name} the {player.class_name} — who brought the rite back.")
    io.show("\nThe Pall is undone. The Warden is no more. Atrél is dead.")
    io.show("Mournhold lives. It does not know it owes anyone a debt.")
    io.show("\nThe Chronicle records: purified, quietly. The smaller ending.")
    io.show("Future climbers will find a kingdom — and a side-altar")
    io.show("where small griefs can be set down again, the way they used to.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _purify_screen(state):
    """The mythic ending — the Pall is undone permanently."""
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("purify", state.chronicle_dir)
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
    _sister_realm_addendum(state, io)
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _other_mournhold_screen(state):
    """SQ5 — The Other Mournhold.

    Only available in a Mirror Climb. The player, standing on a Summit
    they have stood on as someone else many times, undoes the original
    wrong: not the rite, not the famine, not the gates — the act of
    forgetting itself, taken back to its first moment. The kingdom that
    remembers is the kingdom that did not need a Pall.
    """
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("other_mournhold", state.chronicle_dir)
    chronicle.unlock("the_other_mournhold", state.chronicle_dir)
    io.clear()
    io.show_slow("You have stood at this Summit as someone else, several times.")
    io.show_slow("You know what every ending costs. You have paid each cost yourself.")
    io.show_slow("The Pall reaches; you do not let it reach you.")
    io.show("")
    io.show_slow("Instead you step back through your own steps, and the kingdom's.")
    io.show_slow("Through the famine winter. Through the council vote. Through the rite.")
    io.show_slow("You arrive in a chamber where the rite has not yet been said.")
    io.show_slow("Twelve councilors at a long table. They have not voted.")
    io.show_slow("They look up at you the way you have looked up at every grave.")
    io.show("")
    io.show_slow("You tell them what unremembering will become if they perform it.")
    io.show_slow("You tell them about Atrél, who will be broken.")
    io.show_slow("You tell them about Cael, who will swallow the last line and hold it for centuries.")
    io.show_slow("You tell them about Tálva, who their grandchildren will not let in.")
    io.show_slow("You tell them about Renan and Eldris and Paipel and every name you have seen.")
    io.show("")
    io.show_slow("They listen. They are afraid. They vote. The rite is not performed.")
    io.show_slow("There is still a famine. There is still a hard winter. Many die.")
    io.show_slow("But the holds are fed, and remembered, and the kingdom does not learn to forget.")
    io.pause(2)
    io.show("=" * 50)
    io.show("🪞  THE OTHER MOURNHOLD")
    io.show(f"{player.name} the {player.class_name} — who undid the first wrong.")
    io.show("\nThis kingdom is not the kingdom you climbed in. It never grew a Pall,")
    io.show("because it never forgot what it owed. Both the Pall and the climb")
    io.show("never were. You remember them; you alone, here, do.")
    io.show("\nThe Chronicle records: the_other_mournhold. The mirror ending.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


# --- ending registry — add new endings here as the story grows ---
# Order in this list is order in the menu.
endings.register(
    "warden",
    "Be kept by the Pall  (end the run, become the Warden)",
    _warden_screen,
    lambda s: True,
)
endings.register(
    "reborn",
    "Reborn               (end this hero — earn Echoes — start again)",
    _reborn_screen,
    lambda s: True,
)
endings.register(
    "purify",
    "🌅 Purify Mournhold  (end the cycle — the Pall is undone)",
    _purify_screen,
    lambda s: chronicle.cleanses(s.chronicle_dir) >= PURIFY_CLEANSES_REQUIRED,
)
endings.register(
    "atrel_peace",
    "📿 Bring the rite back to Atrél  (the quiet end — none will know)",
    _atrel_peace_screen,
    lambda s: s.flags.get("atrel_offered", False),
)
endings.register(
    "old_seal",
    "🪨 Take Cael's place  (the oldest end — you become the seal)",
    _old_seal_screen,
    lambda s: s.flags.get("offered_old_seal", False),
)
endings.register(
    "reckoning",
    "⚖️  Honour Tálva's reckoning  (unmake Mournhold — the holds are kept)",
    _reckoning_screen,
    lambda s: s.flags.get("talva_asked", False),
)
endings.register(
    "other_mournhold",
    "🪞 The Other Mournhold  (undo the first wrong — only on a Mirror Climb)",
    _other_mournhold_screen,
    lambda s: s.flags.get("mirror_run", False),
)


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


def _pet_the_cat(state):
    """SQ3 — pet the recurring cat.

    Small heal + stamina, increments the cross-run cat_pets counter. At
    fixed thresholds (10/25/50/100), the cat says something. At 100, the
    Chronicle marks cat_companion = True and the cat joins the player as
    a permanent +1 HP/round combat presence.
    """
    player, io = state.player, state.io
    chronicle.add_cat_pet(state.chronicle_dir)
    chronicle.add_kind_act(state.chronicle_dir)  # SQ2: a kindness
    count = chronicle.cat_pets(state.chronicle_dir)
    player.heal(CAT_PET_HEAL)
    player.restore_stamina(CAT_PET_STAMINA)
    io.show("")
    io.show_slow("🐈 The cat presses its head into your hand. You count "
                 "the small bones in its skull.")
    io.show(f"   +{CAT_PET_HEAL} HP  +{CAT_PET_STAMINA} stamina  "
            f"(cat-pets so far: {count})")
    if count == 10:
        io.show_slow("\nThe cat looks at you. 'I have been counting your runs.'")
        io.show_slow("'There are more than you remember.'")
    elif count == 25:
        # Name a fallen character if possible — it knows them.
        fallen_entries = chronicle.fallen(chronicle.load(state.chronicle_dir))
        if fallen_entries:
            name = fallen_entries[0]["player"]["name"]
            io.show_slow(f"\nThe cat says: 'I knew {name}. {name} fed me twice. "
                         f"I have not forgotten {name}.'")
        else:
            io.show_slow("\nThe cat says: 'I knew the ones who died before you "
                         "knew them. I have not forgotten.'")
    elif count == 50:
        io.show_slow("\nThe cat stands. Walks. You follow because you must.")
        io.show_slow("In a small room you have never seen, every name from your "
                     "Chronicle is on the wall.")
        io.show_slow("'I remembered them so you would not have to remember all of them.'")
    elif count == 100:
        io.show_slow("\nThe cat curls against your ankle and does not leave.")
        io.show_slow("It will walk with you, now. It will keep walking with you.")
        io.show_slow("It will mend you, a little, every round you fight.")
        io.show_slow("It will never die. The Pall does not know its name.")
        state.flags["cat_companion"] = True
    io.pause(2)


def _witnessed_dead_here(state, fallen):
    """SQ9 — find a fallen character with unfinished NPC kill-quest progress
    in the CURRENT zone (matched by which NPC lives here).

    Returns a list of ``(entry, npc_id, npc, partial, needed)`` tuples — usually
    zero or one. ``partial`` is how many kills the dead one notched; ``needed``
    is the threshold. Already-resolved entries are skipped.
    """
    loc = state.content.locations[state.current_location]
    npcs_here = [e["id"] for e in loc.get("encounters", []) if e.get("type") == "npc"]
    if not npcs_here:
        return []
    results = []
    for entry in fallen:
        if entry.get("resolved"):
            continue
        progress = entry.get("progress", {})
        kills = progress.get("npc_kills", {}) if isinstance(progress, dict) else {}
        if not kills:
            continue
        for npc_id in npcs_here:
            npc = state.content.npcs.get(npc_id)
            if not npc:
                continue
            target = npc.get("target_enemy")
            if not target:
                continue
            partial = kills.get(target, 0)
            needed = npc.get("needed", 0)
            if 0 < partial < needed:
                results.append((entry, npc_id, npc, partial, needed))
                break  # one Witnessed Dead per fallen-zone pair is enough
    return results


def _honor_the_dead(state, witnessed):
    """SQ9 — take up a fallen character's unfinished work.

    Their kill-progress carries into your run as a head start; they are
    laid to rest in the Chronicle; a small memorial gold reward is given.
    """
    entry, _npc_id, npc, partial, needed = witnessed
    player, io = state.player, state.io
    dead_name = entry.get("player", {}).get("name", "a stranger")
    target = npc["target_enemy"]
    io.clear()
    io.show_slow(f"🕯️  '{dead_name} was here before you. They had counted "
                 f"{partial}/{needed} of the {target}s'")
    io.show_slow("'before the trees took them. Their tally is honest.'")
    io.show_slow(f"'Take their work. Start where {dead_name} left off.'")
    npc_kills = state.flags.setdefault("npc_kills", {})
    npc_kills[target] = max(npc_kills.get(target, 0), partial)
    memorial = 20 * partial
    player.gold += memorial
    io.show(f"\n   You take up {dead_name}'s work. Their {partial}/{needed} "
            f"is now yours.")
    io.show(f"   +{memorial} gold (memorial offering)")
    chronicle.lay_to_rest(entry, state.chronicle_dir)
    chronicle.add_kind_act(state.chronicle_dir)  # SQ2: honoring is kindness
    chronicle.unlock("witness_honored", state.chronicle_dir)  # SQ9 completion mark
    io.pause(2)


def _read_piranesi_map(state):
    """SQ4 — read Piranesi's map.

    Once every Piranesi note has been read (cross-run), a folded square of
    vellum waits in the Pre-Pall Shrine. The map is a quiet hand-drawing of
    the ten small things the watcher kept track of. It can be re-read.
    """
    io = state.io
    io.clear()
    io.show_slow("🪶 You unfold the vellum. The older hand. The same hand that wrote")
    io.show_slow("on the stone, the lintel, the side of the water-butt, the column.")
    io.show("")
    io.show("                           .")
    io.show("                          /|\\         the summit, which he did not draw")
    io.show("                         / | \\")
    io.show("                        /  *  \\       a patch of slope with no ash")
    io.show("                       /   |   \\")
    io.show("                      /  __|__  \\     a column that ate the word 'name'")
    io.show("                     /  |     |  \\")
    io.show("                    /   |  o  |   \\   a square that holds one hour of light")
    io.show("                   /    |_____|    \\")
    io.show("                  /        |        \\")
    io.show("                 /     ___ * ___     \\  a stone with no lichen")
    io.show("                /     /         \\     \\")
    io.show("               /     /  *     *  \\    \\ a doorpost re-marked, a tally")
    io.show("              /     /  *       *  \\    \\ a furrow, a column of birds")
    io.show("             /     /     *           \\  \\ a tree climbed, a stone with a face")
    io.show("            /     /                    \\  \\")
    io.show("           /     /        ^             \\  \\ the hidden hold, a path")
    io.show("          /_____/_________|________________\\__\\")
    io.show("                          |")
    io.show("                     the crossroads")
    io.show("")
    io.show_slow("Below the drawing, in a smaller, later hand — yours, you realise:")
    io.show_slow("'I have walked this. I have seen what was kind. I have written it down.'")
    io.show_slow("'I do not know who will read this. I am glad of them.'")
    io.pause(2)


def reader(state):
    """SQ1 — The Reader Who Watches Back.

    A presence in Gravewatch that surfaces once the player has read
    ``READER_THRESHOLD`` unique lore fragments across runs. The Reader
    has been reading along with the player from the start and finally
    introduces themselves. Once-per-run reward: a small max-HP boost
    scaling with how much the player has actually read.
    """
    player, io = state.player, state.io
    if state.flags.get("read_with_reader"):
        io.clear()
        io.show_slow("📖 The Reader is already with you, today. They look up, smile,")
        io.show_slow("close the book, and gesture for you to climb on.")
        io.pause(2)
        return
    read = chronicle.discoveries_read(state.chronicle_dir)
    io.clear()
    io.show_slow("📖 A figure at a desk in the corner of Gravewatch's hall.")
    io.show_slow("They are reading. They have been reading since you first came in,")
    io.show_slow("but they have not looked up before. They look up now.")
    io.show("")
    io.show_slow("'I am the Reader. I have read what you have read, when you read it.'")
    io.show_slow(f"'You have brought me — let me count — {read} fragments of the'")
    io.show_slow("'kingdom's lost selves. I have read each one with you.'")
    io.show_slow("'Sit. Read one more with me, the one of your own climb.'")
    io.show("")
    io.show_slow("They open their book. The page is blank, then is not blank.")
    io.show_slow("They are reading you, now. The way you have read everyone else.")
    bonus = max(2, read // 5)  # 25 reads → +5, 50 → +10, capped softly
    player.max_hp += bonus
    player.hp = min(player.hp + bonus, player.max_hp)
    state.flags["read_with_reader"] = True
    io.show(f"\n   +{bonus} max HP — the Reader has read you in.")
    io.pause(2)


def _write_first_line(state):
    """SQ10 — The Hidden Final Truth. A child at the Crossroads with a book.

    Surfaces once every other side-quest has been completed across runs.
    Speaking to the child lets the player write the first line of the
    Chronicle — the line every future new character will read at the
    moment of their creation, before anything else Mournhold can say.

    The player can refuse; the option will be there the next time they
    come back.
    """
    io = state.io
    io.clear()
    io.show_slow("📖 At the Crossroads, where there was no one before, there is a child.")
    io.show_slow("They are perhaps eight winters old. They have a book in their lap.")
    io.show_slow("It is the oldest thing in the kingdom, and the newest. It is the Chronicle.")
    io.show("")
    io.show_slow("'I have been keeping this for you,' the child says.")
    io.show_slow("'You have read the names. You have sat with the cat. You have remembered the verse.'")
    io.show_slow("'You have honoured a stranger's unfinished work. You have stood the climb")
    io.show_slow("'as several others. You have done all the small kindnesses Mournhold knew of.'")
    io.show("")
    io.show_slow("They open the book to the first page. The page is blank.")
    io.show_slow("'Someone has to write the first line. It will be the first line of")
    io.show_slow("'every Chronicle from this one on. Every climber who comes after you")
    io.show_slow("'will read it before they read anything else. Will you?'")
    io.show("")
    io.show("1. Yes — write the first line")
    io.show("2. Not today")
    choice = io.ask("\nYour choice? ").strip()
    if choice != "1":
        io.show_slow("\n'I will be here,' the child says. 'I have been here.'")
        io.pause(2)
        return
    io.show("")
    io.show_slow("The child hands you the book. The page is still blank.")
    io.show_slow("Write the line for whoever comes after.")
    line = io.ask("\n> ").strip()
    if not line:
        io.show_slow("\nYou hand the book back. 'Not yet,' you say. The child nods.")
        io.pause(2)
        return
    chronicle.set_first_line(line, state.chronicle_dir)
    chronicle.add_ending_seen("hidden_truth", state.chronicle_dir)
    io.show("")
    io.show_slow("The child reads what you have written. Then closes the book.")
    io.show_slow("'It is in the book now. Every new climber will read it first.'")
    io.show_slow("'It will be the first thing Mournhold says.'")
    io.show("")
    io.show_slow("                  — THE HIDDEN FINAL TRUTH —")
    io.show_slow("       You wrote the first line. There is no climb left to do.")
    io.show_slow("           Mournhold is yours, now. Be gentle with it.")
    io.pause(3)


def caretaker(state):
    """SQ2 — The Long Daily Ritual. The Caretaker ending.

    Surfaces in Gravewatch only after the player has accumulated 40 small
    kindnesses across all runs (discoveries read, cats petted, Hollowed
    laid to rest, fallen honored, verses sung).

    Choosing this ending ends the run differently: the player does not
    climb. They become the keeper of the kingdom's small kindnesses,
    here in Gravewatch — naming the dead, setting flowers at the graves,
    feeding the cat. The world keeps ending. They keep doing this.

    Recorded as a Caretaker fate in the Chronicle; counts as a cleanse.
    """
    io = state.io
    acts = chronicle.kind_acts(state.chronicle_dir)
    io.clear()
    io.show_slow("🌹 You sit down in Gravewatch's hall and do not stand up again.")
    io.show_slow("There is a basket of small flowers by the door. There always was.")
    io.show_slow(f"You have done {acts} small kindnesses in this kingdom — read")
    io.show_slow("its names back, knelt by its stones, fed its cat, sung its verse.")
    io.show("")
    io.show_slow("The climb is for others. Most of them will not finish it.")
    io.show_slow("The kingdom needs both — a climber, and someone here for them")
    io.show_slow("when they come back down. Or do not come back. You will be that one.")
    io.show("")
    io.show_slow("The cat finds your lap. The Insomniac, if she is here, nods.")
    io.show_slow("Someone has left a fresh lamp by the basket. You light it.")
    io.show("")
    io.show_slow("                  — THE CARETAKER —")
    io.show_slow("    You did not climb. You stayed, and you kept the small things.")
    io.show_slow("        Mournhold is harder to forget, while you are here.")
    io.pause(2)
    chronicle.record(state, "caretaker", state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("caretaker", state.chronicle_dir)
    state.flags["run_ended"] = True


def insomniac(state):
    """SQ6 — the Insomniac of Gravewatch.

    Someone who couldn't sleep, so they kept count. After 50 cross-run
    arrivals at Gravewatch, they introduce themselves and lead the player
    down to a cellar that has been growing — three rooms of stuff the
    village forgot. Once per run, on win, the player is the Counted.
    """
    player, io, content, rng = state.player, state.io, state.content, state.rng
    if state.flags.get("the_counted"):
        io.clear()
        io.show_slow("🕯️  The Insomniac nods at you. 'I have counted you, today.'")
        io.show_slow("'You came back. Most do not. Rest a while. The cellar will keep.'")
        io.pause(2)
        return
    visits = chronicle.gravewatch_visits(state.chronicle_dir)
    io.clear()
    io.show_slow("🕯️  An old woman by the cold hearth. Lamp on her knee, not lit.")
    io.show_slow("'I have not slept since the gates closed. I have counted instead.'")
    io.show_slow(f"'You have come back to Gravewatch {visits} times. I know your step.'")
    io.show_slow("'I know the way you stand at the door before you come in.'")
    io.show_slow("'There is a cellar under this room. It is full of what we forgot.'")
    io.show_slow("'I have been keeping a door for whoever was counted enough. Down.'")
    io.pause(2)
    # The descent — three escalating combats, no rest between, randomized.
    descent_pool = ["wolf", "bandit", "goblin", "drowned_thresher", "silt_drowner",
                    "gutter_wretch", "hollow_procession"]
    sampled = rng.sample(descent_pool, k=3) if hasattr(rng, "sample") else descent_pool[:3]
    io.show("")
    io.show_slow("🪨 The stairs are deeper than the room above them ought to allow.")
    io.show_slow("Three doors at the bottom. The Insomniac counts you in.")
    io.pause(1)
    from terminalquest import combat
    from terminalquest.enemy import make_enemy
    for i, enemy_id in enumerate(sampled, start=1):
        io.show(f"\n— Door {i} of 3 —")
        is_last = (i == len(sampled))
        enemy = make_enemy(enemy_id, content, state.flags)
        outcome = combat.run_combat(state, enemy, refresh_after=is_last)
        if outcome != "victory":
            io.show_slow("\n🕯️  The Insomniac is still there, when you come back up.")
            io.show_slow("'Most of you do not finish. I do not count you less for it.'")
            io.pause(2)
            return
    # All three down → grant the Counted reward.
    bonus = max(5, visits // 10)
    player.max_hp += bonus
    player.hp = min(player.hp + bonus, player.max_hp)
    state.flags["the_counted"] = True
    chronicle.unlock("the_counted", state.chronicle_dir)
    io.show("")
    io.show_slow("🕯️  The Insomniac is at the top of the stairs when you come back.")
    io.show_slow("She does not look up. She is counting again.")
    io.show_slow("'You are one of the Counted, now. There are not many.'")
    io.show_slow("'I will know your step better. Sleep, if you can.'")
    io.show(f"\n   +{bonus} max HP — you are the Counted.")
    io.pause(2)


def _maybe_open_border(state):
    """The Border opens after 2 cleanses — Arc III's gating signal."""
    if state.flags.get("border_open"):
        return
    if chronicle.cleanses(state.chronicle_dir) >= 2:
        state.flags["border_open"] = True


def _maybe_wake_forgotten_thing(state):
    """SQ7 — five characters have died in Witherwood. The thing the Pall
    forgot has been there all along. In this run, it surfaces.
    """
    if state.flags.get("forgotten_thing_awake"):
        return
    if chronicle.witherwood_only_falls(state.chronicle_dir) >= 5:
        state.flags["forgotten_thing_awake"] = True


def _maybe_remember_verse(state):
    """SQ8 — if all 4 Lost Verse fragments are already known cross-run,
    a new character begins with the verse remembered. The flag enables the
    Sing-the-Verse service at the Last Altar of Atrél.
    """
    if state.flags.get("lost_verse_known"):
        return
    if chronicle.lost_verse_fragments(state.chronicle_dir) >= 4:
        state.flags["lost_verse_known"] = True


def sing_the_verse(state):
    """SQ8 — sing the Lost Verse at the Last Altar of Atrél.

    Per-run reward: +1 to all stats (max_hp, attack, defense). Once sung in a
    run, the option goes quiet — the Pall un-remembers each verse you sing.
    Each new character climbs again carrying the verse in their throat.
    """
    player, io = state.player, state.io
    io.clear()
    io.show_slow("🎼 You stand at Atrél's altar and breathe in.")
    io.show_slow("The verse is in your throat. It has been there all the climb.")
    io.show_slow("You sing it. Not loudly. The altar is small. The verse is small.")
    io.show("")
    io.show_slow("  'We remember the holds. We remember the gates.'")
    io.show_slow("  'We remember the names. We remember the rain.'")
    io.show_slow("  'We remember the bread we did not give.'")
    io.show_slow("  'We remember. We remember. We remember.'")
    io.show("")
    io.show_slow("Something in the altar settles. Atrél, perhaps, accepting it.")
    io.show_slow("Something in you settles too — straighter, surer, kinder.")
    player.max_hp += 5
    player.hp = min(player.hp + 5, player.max_hp)
    player.attack += 1
    player.defense += 1
    io.show(f"\n   +5 max HP  +1 attack  +1 defense  ({player.name} remembers)")
    state.flags["lost_verse_sung"] = True
    chronicle.add_kind_act(state.chronicle_dir)  # SQ2: singing is kindness
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


CAT_ZONE_VISITS_REQUIRED = 3  # SQ3: cat shows up in zones visited this many times this run
CAT_PET_HEAL = 5
CAT_PET_STAMINA = 1
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

    # v1.16: a dying character may leave one line for whoever climbs next.
    # The line is stored on the chronicle entry and surfaces at their grave
    # and as the first thing the Hollowed says when raised by the Pall.
    io.clear()
    io.show_slow("💀 The Pall takes you. You have a moment, before the dark.")
    io.show_slow("If you have something to say to whoever climbs after you, say it now.")
    io.show_slow("(One line. Enter alone to leave nothing.)")
    last_words = io.ask("\n> ").strip()
    chronicle.record(state, "fell", state.chronicle_dir, last_words=last_words)
    io.clear()
    io.show_slow("💀 The Pall takes another. It always does.")
    _run_summary(state)
    io.show("\nGame Over!")

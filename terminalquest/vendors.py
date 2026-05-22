"""Settlement vendors, combat services, and the service dispatcher.

Extracted from ``locations.py`` during the v2.3 quality audit. Every
function here is a service the player invokes from a settlement (shop,
inn, smith, etc.) or a per-run gold sink (night_hunt). ``_run_service``
is the dispatcher: most of the routed callables are vendors defined
here, but a handful — quest_board, reader, insomniac, caretaker,
hearth_line — call into ``quests`` and ``sq_services``.

Pricing / tuning constants for the vendors live here too — they're
re-exported from ``locations.py`` so existing callers and content
references keep working.
"""
from . import chronicle
from .accessory import make_accessory
from .armor import make_armor
from .combat import _consumable_label, run_combat
from .companion import make_companion
from .enemy import make_enemy
from .hireling import make_hireling
from .pet import make_pet
# The dispatcher routes a few service ids back into the modules that
# OWN them (reader/insomniac/caretaker/hearth_line in sq_services,
# quest_board in quests). Imported by name here so _run_service can
# call them directly without going through locations.py.
from .quests import quest_board
from .sq_services import caretaker, insomniac, reader, write_hearth_line
from .ui import hud
from .weapon import WEAPON_UPGRADES


# ── Pricing & tuning constants ─────────────────────────────────────

INN_COST = 20
POTION_COST = 30
GREATER_POTION_COST = 70
SOVEREIGN_POTION_COST = 200
PALL_DRINKER_COST = 500
SOVEREIGN_UNLOCK_CHAMPIONS = 1
PALL_DRINKER_UNLOCK_CHAMPIONS = 3
ATTACK_UPGRADE_GOLD_PER_POINT = 8
DEFENSE_UPGRADE_GOLD_PER_POINT = 14
NIGHT_HUNT_COST = 40
NIGHT_HUNT_STAT_BOOST = 1.5  # enemy hp/atk multiplied by this for night hunts
NIGHT_HUNT_REWARD_MULT = 2.5  # XP and gold rewards scale up the same way
SURVIVOR_CLEANSES_REQUIRED = 3  # the Survivor NPC appears after this many cleanses
SURVIVOR_STOCK = [
    ("Saint's Reliquary",     800),
    ("Bonesinger's Salt",     600),
    ("Pall-Banishing Tonic", 1000),
]
SCHOLAR_PAYOUT = 75  # gold per unique lore discovery she records


# ── Vendor functions ──────────────────────────────────────────────


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
    elif service == "hearth_line":
        write_hearth_line(state)


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
        state.flags["has_hireling"] = True
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
        state.flags["has_pet"] = True
        state.flags[f"has_pet_{pet_id}"] = True
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


# (Quest helpers + quest_board moved to terminalquest/quests.py — re-exported at top.)


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
        state.flags["has_companion"] = True
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
        state.flags["armor_bought"] = True
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
        state.flags["smith_upgraded"] = True
        io.show_slow(f"\n⚒  The smith works the {weapon.name} into the "
                     f"{upgrade['name']}.")
        io.show(f"   {weapon.summary()}")
        io.pause(1)



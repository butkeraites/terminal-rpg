"""Explorable locations and the main game loop.

The world is a graph of locations loaded from ``data/locations.json``.
``location_loop`` is the central loop: it renders the player's current
location, offers its services, encounters and travel routes, and runs
until the player dies, wins, or quits.
"""
from . import banners as _banners
from . import boss_music_synth as _boss_music
from . import chronicle, marks, saves
from . import dialogue as _dialogue
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
from .accessory import make_accessory
from .armor import make_armor
from .combat import _consumable_label, run_combat
from .companion import make_companion
from .enemy import make_enemy, make_hollowed, make_warden
from .hireling import make_hireling
from .pet import make_pet
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

SCHOLAR_PAYOUT = 75  # gold per unique lore discovery she records

# Reborn / Purify tuning constants live in endings_screens.py and are
# re-exported above for backwards compat.


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

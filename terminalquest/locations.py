"""Explorable locations and the main game loop.

The world is a graph of locations loaded from ``data/locations.json``.
``location_loop`` is the central loop: it renders the player's current
location, offers its services, encounters and travel routes, and runs
until the player dies, wins, or quits.
"""
from . import chronicle, saves
from .accessory import make_accessory
from .armor import make_armor
from .combat import run_combat
from .companion import make_companion
from .enemy import make_enemy, make_hollowed, make_warden
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

_SERVICE_LABELS = {
    "shop": "🏪 Visit the Shop",
    "inn": f"😴 Rest at the Inn ({INN_COST} gold)",
    "smith": "⚒  Visit the Smith",
    "quartermaster": "🛡️  Visit the Quartermaster",
    "pact_broker": "🐺 Visit the Pact-Broker",
    "echo_trader": "🕯️  Visit the Echo Trader",
}

REBORN_ECHO_BASE = 30  # baseline Echo for a Reborn — boosted by what was done
REBORN_ECHO_PER_LEVEL = 3
REBORN_ECHO_PER_UNLOCK = 5


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

    The default ending is to be kept by the Pall (chronicled as Warden, the
    next Summit boss). Reborn is the prestige alternative: you refuse to be
    kept, the Pall takes its toll (you lose this run's hero entirely), but
    you carry away Echoes — the only coin that buys back what the Pall takes.
    """
    player, io = state.player, state.io
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
    io.show("\n1. Be kept by the Pall  (end the run, become the Warden)")
    io.show("2. Reborn               (end this hero — earn Echoes — start again)")
    choice = io.ask("\nYour choice? ")
    if choice == "2":
        _reborn_screen(state)
        return
    chronicle.record(state, "warden", state.chronicle_dir)
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


def _build_options(state, loc, fallen):
    """Build the ordered list of ``(label, (kind, arg))`` menu entries."""
    player, content = state.player, state.content
    options = []
    for service in loc.get("services", []):
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

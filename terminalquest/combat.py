"""Turn-based combat.

Turn economy: every player action (attack, ability, potion, defend, or a
failed flee) consumes the player's turn and is followed by the enemy's
turn. Using a potion is no longer a free action.

``run_combat`` drives the loop through a ``GameIO`` so it is fully
testable with ``ScriptedIO``. Damage/AI helpers are pure functions of
their arguments and an injected ``random.Random`` for determinism.
"""

from __future__ import annotations
from . import marks, status
from .player import LEVEL_BOONS

ATTACK_VARIANCE = (-2, 4)
CRIT_CHANCE = 0.15
CRIT_MULTIPLIER = 1.8
STAMINA_PER_TURN = 2
FLEE_CHANCE = 0.5
# Consumables carry an effects dict — heal, status, full restores. Class
# consumables (Warrior's Breath etc.) reuse the same machinery as the
# basic potions, so the in-combat menu treats them uniformly.
CONSUMABLE_EFFECTS = {
    "Health Potion":    {"heal": 40},
    "Greater Potion":   {"heal": 80},
    "Sovereign Potion": {"heal": 160},
    "Pall-Drinker":     {"heal": 250, "stamina_full": True},
    "Warrior's Breath": {"status": "braced", "status_turns": 3},
    "Rogue's Vial":     {"status": "evasive", "status_turns": 3},
    "Mage's Crystal":   {"stamina_full": True},
    "Ranger's Tonic":   {"heal": 60},
    "Cleric's Wafer":   {"heal_full": True},
    # The Survivor's stock at Gravewatch (gated by cleanse count).
    "Saint's Reliquary":     {"heal_full": True, "stamina_full": True},
    "Bonesinger's Salt":     {"status": "braced", "status_turns": 5},
    "Pall-Banishing Tonic":  {"heal": 200, "status": "evasive", "status_turns": 3},
    # The Last Bread — gifted by Kerris in the Hidden Hold. Heal full + stamina full,
    # AND wraps that effect in a small narrative: bread the gates couldn't stop.
    "the Last Bread":        {"heal_full": True, "stamina_full": True},
}

# Legacy alias kept so the existing shop and tests can still read potion heals.
POTION_HEAL = {name: CONSUMABLE_EFFECTS[name]["heal"]
               for name in CONSUMABLE_EFFECTS
               if "heal" in CONSUMABLE_EFFECTS[name]}
POTION_RESTORES_STAMINA = {name for name, e in CONSUMABLE_EFFECTS.items()
                           if e.get("stamina_full")}

CLASS_CONSUMABLE = {
    "warrior": "Warrior's Breath",
    "rogue":   "Rogue's Vial",
    "mage":    "Mage's Crystal",
    "ranger":  "Ranger's Tonic",
    "cleric":  "Cleric's Wafer",
}

# Quest catalog — picked up at the Gravewatch Quest Board, completed by kills,
# claimed back at the board for gold + a class-themed consumable.
#
# Lives in ``terminalquest/data/quests.json`` and is loaded into
# ``state.content.quests`` alongside the rest of the content. ``_track_quest_kill``
# reads from that dict, not from a Python constant — designers can add or tune
# quests by editing the JSON.


def _maybe_drop_trophy(state, enemy):
    """Roll the trophy-drop chance and append the named trophy to player.trophies.

    If the drop lands, also tick any active trophy-target quest whose
    ``target_trophy`` matches — Phase-1 Batch-2 of the quest engine.
    """
    trophy = state.content.enemies.get(getattr(enemy, "enemy_id", ""), {}).get("trophy")
    if trophy is None:
        return
    if state.rng.random() >= TROPHY_DROP_CHANCE:
        return
    player = state.player
    player.trophies[trophy] = player.trophies.get(trophy, 0) + 1
    state.io.show(f"🪶 You take a {trophy.replace('_', ' ')} from the dead. "
                  f"({player.trophies[trophy]} carried)")
    _track_quest_trophy(state, trophy)


def _track_quest_trophy(state, trophy):
    """Tick every active quest whose ``target_trophy`` matches the given trophy.

    Trophy-target quests are a Phase-1 Batch-2 quest type (see docs/QUESTS.md).
    The progress counter lives in the same ``state.flags['quest_progress']``
    dict as kill-target quests, keyed by quest_id, and counts monotonic
    drops — Beastmaster spending of trophies does not reduce quest progress.
    """
    active = state.flags.get("active_quests", [])
    progress = state.flags.setdefault("quest_progress", {})
    quests = state.content.quests
    for quest_id in active:
        quest = quests.get(quest_id)
        if quest and quest.get("target_trophy") == trophy:
            progress[quest_id] = progress.get(quest_id, 0) + 1
            if progress[quest_id] == quest["needed"]:
                state.io.show(f"\n📜 {quest['name']} — complete. "
                              f"Return to the Quest Board to claim your reward.")


def _track_quest_kill(state, enemy):
    """If the slain enemy matches an active quest or NPC target, increment tallies.

    Two parallel counters: the Quest Board's per-bounty progress, and the
    NPC's per-target kill count (state.flags['npc_kills']). The latter is
    a single dict keyed by enemy_id so any NPC asking for kills of that
    enemy reads the same total.

    Quests with ``target_trophy`` instead of ``target_enemy`` are handled
    by ``_track_quest_trophy`` from inside ``_maybe_drop_trophy`` — see
    Phase-1 Batch-2 in docs/QUESTS.md.

    Quests with ``completion_condition`` (Phase-1 Batch-6) are handled by
    ``_track_quest_condition``, which is called from _grant_rewards after
    this function.
    """
    target = getattr(enemy, "enemy_id", None)
    if target is None:
        return
    npc_kills = state.flags.setdefault("npc_kills", {})
    npc_kills[target] = npc_kills.get(target, 0) + 1
    active = state.flags.get("active_quests", [])
    progress = state.flags.setdefault("quest_progress", {})
    quests = state.content.quests
    for quest_id in active:
        quest = quests.get(quest_id)
        if not quest:
            continue
        # A quest with a completion_condition is handled by
        # _track_quest_condition; skip here so we don't double-tick.
        if quest.get("completion_condition"):
            continue
        if quest.get("target_enemy") == target:
            progress[quest_id] = progress.get(quest_id, 0) + 1
            if progress[quest_id] == quest["needed"]:
                state.io.show(f"\n📜 {quest['name']} — complete. "
                              f"Return to the Quest Board to claim your reward.")


def _init_combat_conditions(state):
    """Reset the per-fight condition tracker before run_combat starts.

    Phase-1 Batch-6: Conditional Combat quests (docs/QUESTS.md) declare a
    ``completion_condition`` keyed by one of the entries in
    ``content.VALID_COMPLETION_CONDITIONS``. Each condition's truth at
    the *end of combat* is the gate. The infrastructure starts every
    known condition at True and the in-combat hooks flip them to False
    when violated. Conditions not yet implemented stay False so quests
    using them remain unfillable (the design intent: ship predicates as
    we ship the conditions they describe).
    """
    # IMPLEMENTED in Batch-6: these three start at True and can be flipped.
    # Future batches will add more predicates. Conditions absent from this
    # dict default to False from .get() — quests gated on unimplemented
    # conditions are uncompletable, which is correct.
    state.flags["combat_conditions"] = {
        "no_stun_during_fight": True,
        "no_hireling_death": True,
        "killed_in_one_round": True,
    }
    state.flags["_combat_round"] = 1


def _track_quest_condition(state, enemy):
    """Tick conditional-combat quests whose ``completion_condition`` held this fight.

    Pairs with ``_track_quest_kill``: a quest with both ``target_enemy``
    AND ``completion_condition`` requires both to be satisfied; a quest
    with only ``completion_condition`` ticks on any victory where the
    condition is true. ``target_trophy`` + ``completion_condition`` is
    not yet supported — only enemy-kill conditional quests in this batch.
    """
    target = getattr(enemy, "enemy_id", None)
    active = state.flags.get("active_quests", [])
    progress = state.flags.setdefault("quest_progress", {})
    conditions = state.flags.get("combat_conditions") or {}
    quests = state.content.quests
    for quest_id in active:
        quest = quests.get(quest_id)
        if not quest:
            continue
        cc = quest.get("completion_condition")
        if not cc:
            continue
        if not conditions.get(cc):
            continue
        te = quest.get("target_enemy")
        if te is not None and te != target:
            continue
        progress[quest_id] = progress.get(quest_id, 0) + 1
        if progress[quest_id] == quest["needed"]:
            state.io.show(f"\n📜 {quest['name']} — complete. "
                          f"Return to the Quest Board to claim your reward.")


def _consumable_label(name):
    """A short bracketed description of a consumable's effects."""
    effects = CONSUMABLE_EFFECTS.get(name, {})
    parts = []
    if "heal" in effects:
        parts.append(f"+{effects['heal']} HP")
    if effects.get("heal_full"):
        parts.append("full HP")
    if effects.get("stamina_full"):
        parts.append("full stamina")
    if "status" in effects:
        parts.append(f"{effects['status']} {effects['status_turns']}t")
    return ", ".join(parts) or "—"
DEFEND_TURNS = 1
HEAVY_BLOW_POWER = 2.0
ENRAGE_THRESHOLD = 0.5
ENRAGE_ATTACK_GAIN = 2
RELENTLESS_PERIOD = 3
XP_OVERLEVEL_THRESHOLD = 2
TROPHY_DROP_CHANCE = 0.25  # chance a defeated enemy yields its named trophy


def _perform_attack(attacker, target, power, rng):
    """Resolve one attack. Returns ``(damage_dealt, dodged, crit)``.

    The attacker's ``crit_bonus`` (set by weapon upgrades like Sharpened) is
    added to the base crit chance. The target's ``dodge_chance`` (set by
    armor pieces) lets them avoid a hit entirely — bypassing the min-1 floor.
    """
    if status.has_status(target, "evasive") and rng.random() < 0.5:
        return 0, True, False
    # Armor-granted dodge: a clean miss with no damage at all.
    dodge_chance = getattr(target, "dodge_chance", 0.0)
    if dodge_chance > 0 and rng.random() < dodge_chance:
        return 0, True, False
    raw = max(1, round(attacker.attack * power) + rng.randint(*ATTACK_VARIANCE))
    crit_chance = CRIT_CHANCE + getattr(attacker, "crit_bonus", 0.0)
    crit = rng.random() < crit_chance
    if crit:
        raw = round(raw * CRIT_MULTIPLIER)
    dealt = target.take_damage(raw, status.attack_multiplier(attacker))
    return dealt, False, crit


def _apply_lifesteal(player, damage, io):
    """If the equipped weapon is Lifedrinker, heal a fraction of the damage dealt."""
    weapon = player.equipment.get("weapon")
    if not weapon or weapon.upgrade != "lifesteal" or damage <= 0:
        return
    heal = max(1, int(damage * 0.15))
    before = player.hp
    player.heal(heal)
    if player.hp > before:
        io.show(f"💉 {weapon.name} drinks deep — +{player.hp - before} HP "
                f"({player.hp}/{player.max_hp}).")


def _hireling_act(state, enemy):
    """Run the hireling's once-per-round mend on the player (if hurt)."""
    player, io = state.player, state.io
    hire = player.hireling
    if hire is None or not hire.is_alive():
        return
    if player.hp >= player.max_hp:
        return
    before = player.hp
    player.heal(hire.heal_per_round)
    io.show(f"\n🩹 {hire.name} mends you — +{player.hp - before} HP "
            f"({player.hp}/{player.max_hp}).")


def _companion_act(state, enemy):
    """Run the companion's once-per-round action (if any). Spirit-aid, invulnerable.

    Damage companions hit the enemy directly (no defense, no crits). Heal
    companions mend the player. Companion power scales with the Chronicle's
    cleanse count — every cleansed run lends the spirits a bit more strength.
    """
    from . import chronicle as _chronicle
    player, io = state.player, state.io
    comp = player.companion
    if comp is None:
        return
    bonus = _chronicle.cleanses(state.chronicle_dir)
    power = comp.power + bonus
    if comp.kind == "damage":
        dealt = min(power, enemy.hp)
        enemy.hp -= dealt
        scaling = f" (+{bonus} from the cleansed road)" if bonus > 0 else ""
        io.show(f"\n🌀 {comp.name} strikes — {dealt} damage to {enemy.name}{scaling}.")
    elif comp.kind == "heal":
        if player.hp >= player.max_hp:
            return
        before = player.hp
        player.heal(power)
        scaling = f" (+{bonus} from the cleansed road)" if bonus > 0 else ""
        io.show(f"\n💚 {comp.name} mends you — +{player.hp - before} HP "
                f"({player.hp}/{player.max_hp}){scaling}.")


def _fire_procs(player, enemy, dodged, crit, io):
    """Fire the equipped weapon's procs after a player attack."""
    if not enemy.is_alive():
        return
    weapon = player.equipment.get("weapon")
    if weapon is None:
        return
    for proc in weapon.procs:
        trigger = proc["trigger"]
        if (trigger == "on_hit" and not dodged) or (trigger == "on_crit" and crit):
            status.apply_status(enemy, proc["status"], proc["turns"])
            io.show(f"   ⟡ {weapon.name}: {enemy.name} is gripped by {proc['status']}!")


def _resolve_start_of_turn(combatant, io):
    """Tick damage-over-time and timers. Returns True if the combatant survives."""
    dot, messages = status.tick_statuses(combatant)
    for message in messages:
        io.show(message)
    if dot:
        combatant.hp -= dot
    return combatant.is_alive()


def _tick_pet_regen(player, io):
    """Apply the equipped pet's per-round regen (Hearth Cat). No-op otherwise."""
    pet = player.equipment.get("pet") if hasattr(player, "equipment") else None
    if pet is None or not getattr(pet, "regen_per_round", 0):
        return
    if player.hp >= player.max_hp:
        return
    before = player.hp
    player.heal(pet.regen_per_round)
    io.show(f"❤️  {pet.name} mends you — +{player.hp - before} HP "
            f"({player.hp}/{player.max_hp}).")


def _tick_cat_companion(state):
    """SQ3 endgame — the recurring cat, once bonded at 100 pets, heals +1 HP
    every round of combat. Invisible, persistent, unkillable.
    """
    if not state.flags.get("cat_companion"):
        return
    player, io = state.player, state.io
    if player.hp >= player.max_hp:
        return
    before = player.hp
    player.heal(1)
    if player.hp > before:
        io.show(f"🐈 The cat purrs against your ankle. +{player.hp - before} HP.")


def _use_ability(player, enemy, ability, io, rng):
    """Apply a class ability's effect. Stamina is charged by the caller."""
    kind = ability["kind"]
    if kind == "attack":
        damage, dodged, crit = _perform_attack(player, enemy, ability["power"], rng)
        if dodged:
            io.show(f"💨 {enemy.name} dodges your {ability['name']}!")
        elif crit:
            io.show(f"💥 CRITICAL! {ability['name']} smashes {enemy.name} "
                    f"for {damage} damage!")
        else:
            io.show(f"✨ {ability['name']} hits {enemy.name} for {damage} damage!")
        if not dodged and "status" in ability:
            status.apply_status(enemy, ability["status"], ability["status_turns"])
            io.show(f"   {enemy.name} is afflicted with {ability['status']}!")
        _fire_procs(player, enemy, dodged, crit, io)
        _apply_lifesteal(player, damage, io)
    elif kind == "defend":
        status.apply_status(player, "braced", DEFEND_TURNS)
        io.show(f"🛡️  {ability['name']}! You brace against the next blow.")
    elif kind == "buff":
        status.apply_status(player, ability["status"], ability["status_turns"])
        io.show(f"✨ {ability['name']}! You gain {ability['status']}.")
    elif kind == "debuff":
        status.apply_status(enemy, ability["status"], ability["status_turns"])
        io.show(f"🎯 {ability['name']}! {enemy.name} is now {ability['status']}.")
    elif kind == "heal":
        player.heal(ability["power"])
        io.show(f"💚 {ability['name']}! You restore {ability['power']} HP "
                f"({player.hp}/{player.max_hp}).")


def _choose_ability(player, content, io):
    """Prompt for an ability. Returns an ability dict, or None to cancel."""
    while True:
        io.show(f"\n⚡ Stamina: {player.stamina}/{player.max_stamina}")
        usable = [content.abilities[a] for a in player.abilities]
        for index, ability in enumerate(usable, start=1):
            io.show(f"{index}. {ability['name']} ({ability['stamina']} stamina) "
                    f"- {ability['description']}")
        io.show(f"{len(usable) + 1}. Cancel")
        choice = io.ask("\nWhich ability? ")
        if choice == str(len(usable) + 1):
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(usable):
            ability = usable[int(choice) - 1]
            if ability["stamina"] > player.stamina:
                io.show("\n❌ Not enough stamina!")
                continue
            return ability
        io.show("\n❌ Invalid choice!")


def _player_turn(player, enemy, content, io, rng):
    """Run one player action. Returns 'acted' or 'fled'."""
    while True:
        io.show("\n1. Attack")
        io.show("2. Use Ability")
        io.show("3. Use Potion")
        io.show("4. Defend")
        io.show("5. Flee")
        io.show("(? — what do status effects do)")
        choice = io.ask("\nWhat do you do? ")

        if choice == "?":
            io.show("")
            for line in status.glossary():
                io.show(line)
            continue

        if choice == "1":
            damage, dodged, crit = _perform_attack(player, enemy, 1.0, rng)
            if dodged:
                io.show(f"\n💨 {enemy.name} dodges your attack!")
            elif crit:
                io.show(f"\n💥 CRITICAL HIT! You deal {damage} damage to {enemy.name}!")
            else:
                io.show(f"\n💥 You deal {damage} damage to {enemy.name}!")
            _fire_procs(player, enemy, dodged, crit, io)
            _apply_lifesteal(player, damage, io)
            return "acted"

        if choice == "2":
            ability = _choose_ability(player, content, io)
            if ability is None:
                continue
            player.stamina -= ability["stamina"]
            io.show("")
            _use_ability(player, enemy, ability, io, rng)
            return "acted"

        if choice == "3":
            owned = [name for name in CONSUMABLE_EFFECTS if name in player.consumables]
            if not owned:
                io.show("\n❌ You have no consumables!")
                continue
            if len(owned) == 1:
                potion = owned[0]
            else:
                for index, name in enumerate(owned, start=1):
                    io.show(f"{index}. {name} ({_consumable_label(name)})")
                io.show(f"{len(owned) + 1}. Cancel")
                pick = io.ask("\nWhich item? ")
                if pick == str(len(owned) + 1):
                    continue
                if not (pick.isdigit() and 1 <= int(pick) <= len(owned)):
                    io.show("\n❌ Invalid choice!")
                    continue
                potion = owned[int(pick) - 1]
            effects = CONSUMABLE_EFFECTS[potion]
            player.consumables.remove(potion)
            io.show(f"\n💚 You use a {potion}.")
            if "heal" in effects:
                player.heal(effects["heal"])
                io.show(f"   +{effects['heal']} HP ({player.hp}/{player.max_hp}).")
            if effects.get("heal_full"):
                player.hp = player.max_hp
                io.show(f"   HP restored to full ({player.hp}/{player.max_hp}).")
            if effects.get("stamina_full"):
                player.stamina = player.max_stamina
                io.show(f"⚡ Stamina surges back to {player.stamina}/"
                        f"{player.max_stamina}.")
            if "status" in effects:
                status.apply_status(player, effects["status"],
                                    effects["status_turns"])
                io.show(f"   You gain {effects['status']} for "
                        f"{effects['status_turns']} turns.")
            return "acted"

        if choice == "4":
            status.apply_status(player, "braced", DEFEND_TURNS)
            io.show("\n🛡️  You brace yourself, ready to halve the next hit.")
            return "acted"

        if choice == "5":
            if rng.random() < FLEE_CHANCE:
                io.show("\n🏃 You successfully flee!")
                return "fled"
            io.show("\n❌ You couldn't escape!")
            return "acted"

        io.show("\n❌ Invalid choice!")


def _enemy_cast(enemy, player, io, rng):
    """Resolve the enemy's special ability (used by the 'caster' AI)."""
    spell = enemy.ability
    damage, dodged, crit = _perform_attack(enemy, player, spell["power"], rng)
    if dodged:
        io.show(f"\n💨 You dodge {enemy.name}'s {spell['name']}!")
        return
    if crit:
        io.show(f"\n💥 CRITICAL! {enemy.name}'s {spell['name']} blasts you "
                f"for {damage} damage!")
    else:
        io.show(f"\n🌑 {enemy.name} uses {spell['name']} for {damage} damage!")
    if "status" in spell:
        status.apply_status(player, spell["status"], spell["status_turns"])
        io.show(f"   You are afflicted with {spell['status']}!")


def _enemy_strike(enemy, player, power, io, rng):
    """Resolve a basic or heavy enemy attack.

    If the player has a living hireling, the hireling intercepts the blow —
    they take damage instead of the player. If the hireling dies as a result,
    a state flag is set so the realm later spawns them as a Forsaken Sworn.
    """
    hireling = getattr(player, "hireling", None)
    if hireling is not None and hireling.is_alive():
        damage, dodged, crit = _perform_attack(enemy, hireling, power, rng)
        if dodged:
            io.show(f"\n💨 {hireling.name} ducks under {enemy.name}'s strike!")
        elif crit:
            io.show(f"\n💥 {enemy.name} crashes through {hireling.name}'s guard for "
                    f"{damage} damage! ({hireling.hp}/{hireling.max_hp})")
        else:
            io.show(f"\n🛡️  {hireling.name} takes the blow — {damage} damage. "
                    f"({hireling.hp}/{hireling.max_hp})")
        if not hireling.is_alive():
            io.show_slow(f"\n💀 {hireling.name} falls. They will not rise back up at your side.")
        return
    damage, dodged, crit = _perform_attack(enemy, player, power, rng)
    if dodged:
        io.show(f"\n💨 You dodge {enemy.name}'s attack!")
    elif crit:
        io.show(f"\n💥 {enemy.name} lands a CRITICAL blow for {damage} damage!")
    elif power > 1.0:
        io.show(f"\n💢 {enemy.name} lands a crushing blow for {damage} damage!")
    else:
        io.show(f"\n💢 {enemy.name} deals {damage} damage to you!")


def _enemy_turn(enemy, player, io, rng):
    """Run the enemy's action according to its AI. Returns 'acted' or 'fled'.

    An aggressive enemy telegraphs its heavy blow — it spends a turn winding
    up, then delivers the blow next turn, giving the player a chance to Defend.
    Casters strike without warning, so their signature spell stays a threat.
    A relentless enemy surges every third turn, telegraphing and striking in
    the same beat — too fast to react to, so the player must count. An enrager
    grows stronger every turn once wounded past half HP — a race to finish it.
    """
    # A telegraphed heavy blow announced last turn lands now.
    if enemy.winding_up == "heavy":
        enemy.winding_up = None
        _enemy_strike(enemy, player, HEAVY_BLOW_POWER, io, rng)
        return "acted"

    if enemy.ai == "relentless":
        enemy.turns_taken += 1
        if enemy.turns_taken % RELENTLESS_PERIOD == 0:
            io.show(f"\n🌀 {enemy.name} surges forward — no wind-up, no mercy!")
            _enemy_strike(enemy, player, HEAVY_BLOW_POWER, io, rng)
        else:
            _enemy_strike(enemy, player, 1.0, io, rng)
        return "acted"

    if enemy.ai == "enrager":
        if enemy.hp <= enemy.max_hp * ENRAGE_THRESHOLD:
            if not enemy.enraged:
                enemy.enraged = True
                io.show(f"\n😡 {enemy.name} is wounded into a frenzy — "
                        f"its blows grow heavier with every turn!")
            enemy.attack += ENRAGE_ATTACK_GAIN
        _enemy_strike(enemy, player, 1.0, io, rng)
        return "acted"

    low_hp = enemy.hp <= enemy.max_hp * 0.35

    if enemy.ai == "fleer" and enemy.hp <= enemy.max_hp * 0.30 and rng.random() < 0.5:
        io.show(f"\n🏃 {enemy.name} flees from the fight!")
        return "fled"

    if enemy.ai == "defensive" and low_hp and not status.has_status(enemy, "braced"):
        status.apply_status(enemy, "braced", DEFEND_TURNS)
        io.show(f"\n🛡️  {enemy.name} braces defensively.")
        return "acted"

    if enemy.ai == "caster" and enemy.ability and rng.random() < 0.5:
        _enemy_cast(enemy, player, io, rng)
        return "acted"

    if enemy.ai == "aggressive" and rng.random() < 0.3:
        enemy.winding_up = "heavy"
        io.show(f"\n🌀 {enemy.name} rears back for a crushing blow!")
        return "acted"

    _enemy_strike(enemy, player, 1.0, io, rng)
    return "acted"


def _choose_skill(player, learnable, content, io):
    """Sub-menu for the 'Learn a new skill' boon. Returns an ability id or None."""
    while True:
        io.show("\n🎓 Skills you can learn:")
        for index, ability_id in enumerate(learnable, start=1):
            ability = content.abilities[ability_id]
            io.show(f"{index}. {ability['name']} ({ability['stamina']} stamina) "
                    f"- {ability['description']}")
        io.show(f"{len(learnable) + 1}. Back")
        choice = io.ask("\nWhich skill? ")
        if choice == str(len(learnable) + 1):
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(learnable):
            return learnable[int(choice) - 1]
        io.show("\n❌ Invalid choice!")


def _next_progression_level(player, content):
    """The lowest unlock-level of an unlearned progression ability, or None."""
    progression = content.classes[player.class_id].get("progression", [])
    unlearned = [entry for entry in progression
                 if entry["ability"] not in player.abilities]
    if not unlearned:
        return None
    return min(entry["level"] for entry in unlearned)


def _choose_boon(player, content, io):
    """Prompt the player to pick a level-up reward.

    Returns ``('boon', boon_id)`` for a stat boon, or ``('learn', ability_id)``
    for a newly-learned skill. The 4th option always renders: when no skill
    is yet unlocked, it shows a "(unlocks at level X)" hint so the player
    knows the system exists and waits for it.
    """
    boons = list(LEVEL_BOONS.items())
    while True:
        learnable = player.learnable_abilities(content)
        next_unlock = _next_progression_level(player, content)
        io.show("\nChoose a boon:")
        for index, (_boon_id, boon) in enumerate(boons, start=1):
            io.show(f"{index}. {boon['name']} — {boon['blurb']}")
        learn_idx = len(boons) + 1
        if learnable:
            io.show(f"{learn_idx}. 🎓 Learn a new skill")
        elif next_unlock is not None:
            io.show(f"{learn_idx}. 🔒 Learn a new skill  "
                    f"(next unlocks at level {next_unlock})")
        choice = io.ask("\nYour choice? ")
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(boons):
                return ("boon", boons[idx - 1][0])
            if idx == learn_idx:
                if learnable:
                    ability_id = _choose_skill(player, learnable, content, io)
                    if ability_id is not None:
                        return ("learn", ability_id)
                    continue  # cancelled — re-show the boon menu
                if next_unlock is not None:
                    io.show(f"\n🔒 No skill is unlocked yet — "
                            f"reach level {next_unlock} to learn one.")
                    continue
        io.show("\n❌ Invalid choice!")


def _is_overleveled(state):
    """True if the player has out-grown the current zone's XP table.

    A soft cap, not a gate: over-leveled fights still award gold, but the
    player can no longer XP-farm a low-tier zone into demigod status.
    """
    zone = state.content.locations.get(state.current_location, {})
    rec = zone.get("recommended_level")
    return rec is not None and state.player.level > rec + XP_OVERLEVEL_THRESHOLD


def _grant_rewards(state, enemy):
    """Award XP and gold for a defeated enemy, with a boon per level gained.

    Over-leveled fights award gold only — no XP, no boon menu, with a clear
    message so the player understands the soft cap.
    """
    player, content, io = state.player, state.content, state.io
    io.show_slow(f"\n🎉 You defeated {enemy.name}!")
    # Quest counters and trophy drops happen regardless of XP soft-cap.
    # The soft cap suppresses XP/boons in over-leveled zones; it should NOT
    # invalidate kills the player legitimately did for an NPC's tally.
    _maybe_drop_trophy(state, enemy)
    _track_quest_kill(state, enemy)
    if _is_overleveled(state):
        io.show(f"This place has nothing left to teach you. "
                f"Gained {enemy.gold_reward} gold (no XP).")
        player.gold += enemy.gold_reward
        return
    io.show(f"Gained {enemy.xp_reward} XP and {enemy.gold_reward} gold!")
    player.gold += enemy.gold_reward
    for _ in range(player.gain_xp(enemy.xp_reward)):
        io.show_slow(f"\n🎉 LEVEL UP! You are now level {player.level}!")
        player.apply_baseline()
        kind, value = _choose_boon(player, content, io)
        if kind == "boon":
            player.apply_boon(value)
        else:  # 'learn'
            player.learn_ability(value)
            io.show(f"🎓 You have learned {content.abilities[value]['name']}!")
        io.show(f"HP: {player.max_hp} | Attack: {player.attack} | "
                f"Defense: {player.defense} | Stamina: {player.max_stamina}")
        # Marks fire at level-up — what you became when you grew.
        marks.roll_at(state, "level_up")


def _print_combat_status(player, enemy, io):
    """Print the per-round HUD for both combatants and the enemy's statuses."""
    io.show(f"\n{player.name}: {player.hp}/{player.max_hp} HP | "
            f"⚡{player.stamina}/{player.max_stamina} | "
            f"⚔️{player.attack} 🛡️{player.defense}")
    io.show(f"{enemy.name}: {enemy.hp}/{enemy.max_hp} HP | "
            f"⚔️{enemy.attack} 🛡️{enemy.defense}")
    enemy_effects = status.describe(enemy)
    if enemy_effects:
        io.show(f"{enemy.name} status: {enemy_effects}")


def _player_round(state, enemy):
    """Run the player's half-turn.

    Returns an outcome string when the round short-circuits the fight
    ('defeat' from DoT, 'fled' from the menu), or ``None`` to continue.
    """
    player, content, io, rng = state.player, state.content, state.io, state.rng
    stunned = status.has_status(player, "stun")
    if stunned:
        # Phase-1 Batch-6: player got stunned at any point — condition fails.
        state.flags["combat_conditions"]["no_stun_during_fight"] = False
    if not _resolve_start_of_turn(player, io):
        return "defeat"
    stamina_before = player.stamina
    player.restore_stamina(STAMINA_PER_TURN)
    gained = player.stamina - stamina_before
    if gained > 0:
        io.show(f"⚡ You catch your breath. (+{gained} stamina, "
                f"{player.stamina}/{player.max_stamina})")
    _tick_pet_regen(player, io)
    _tick_cat_companion(state)
    if stunned:
        io.show("\n💫 You are stunned and lose your turn!")
    else:
        if _player_turn(player, enemy, content, io, rng) == "fled":
            return "fled"
    return None


def _enemy_round(state, enemy):
    """Run the enemy's half-turn.

    Returns 'victory' if start-of-turn DoT finished the enemy, 'enemy_fled'
    if the enemy chose to bolt, or ``None`` to continue the loop.
    """
    player, io, rng = state.player, state.io, state.rng
    enemy_stunned = status.has_status(enemy, "stun")
    if not _resolve_start_of_turn(enemy, io):
        return "victory"
    if enemy_stunned:
        io.show(f"\n💫 {enemy.name} is stunned and loses its turn!")
    elif _enemy_turn(enemy, player, io, rng) == "fled":
        return "enemy_fled"
    return None


def _post_combat(state, enemy, outcome, refresh_after):
    """Post-fight bookkeeping: hireling death, victory rewards, marks rolls,
    status clear, stamina restore.

    Mutates ``state`` in place. Returns nothing; ``run_combat`` returns the
    outcome it already has.
    """
    player = state.player
    # Phase-1 Batch-6: detect hireling death BEFORE the quest engine reads
    # conditions. A hireling that fell this fight violates no_hireling_death,
    # so a quest gated on that condition must NOT tick.
    hireling_died = (player.hireling is not None
                     and not player.hireling.is_alive())
    if hireling_died:
        state.flags.setdefault("combat_conditions", {})[
            "no_hireling_death"] = False

    if outcome == "victory":
        _grant_rewards(state, enemy)
        # Phase-1 Batch-6: tick conditional-combat quests after the kill is
        # recorded. _track_quest_kill (inside _grant_rewards) skips quests
        # with completion_condition so we don't double-tick here.
        _track_quest_condition(state, enemy)
        # v1.51 — clean wins are a fire site. The kingdom marks survivors.
        marks.roll_at(state, "combat_victory")
        # v1.51 — survived a close call (limped through under 30% HP).
        # This is the high-stakes site: reckless play is more likely to mark you.
        if player.hp > 0 and player.hp < (player.max_hp * 0.30):
            marks.roll_at(state, "combat_low_hp")

    # Hireling cleanup: if they died this fight, drop them from the player
    # and flag the state so future random encounters can spawn the Forsaken.
    if hireling_died:
        state.flags["fallen_hireling"] = player.hireling.to_dict()
        player.hireling = None

    player.statuses.clear()
    if refresh_after:
        player.stamina = player.max_stamina


def run_combat(state, enemy, *, refresh_after=True):
    """Fight ``enemy`` to a conclusion.

    Returns one of: 'victory', 'defeat', 'fled', 'enemy_fled'.
    Combat-only status effects are cleared on exit. Stamina is restored to
    full unless ``refresh_after=False`` — used by chained encounters where
    the player has no rest between sub-fights.

    Phase-1 Batch-6: at the start of the fight, ``_init_combat_conditions``
    resets the per-fight tracker; conditional-combat quests read it after
    ``_grant_rewards`` via ``_track_quest_condition``.

    The loop is a thin orchestrator over four helpers that each own one
    phase: ``_print_combat_status`` (HUD), ``_player_round`` (player's
    half-turn), companion/hireling acts, ``_enemy_round`` (enemy's
    half-turn), and ``_post_combat`` (rewards + cleanup).
    """
    player, io = state.player, state.io
    article = "" if enemy.unique else "A "
    io.show_slow(f"\n⚔️  {article}{enemy.name} comes for you.")
    if enemy.flavor:
        io.show_slow(enemy.flavor)

    _init_combat_conditions(state)
    outcome = None
    while outcome is None:
        # Round counter for the 'killed_in_one_round' condition. Round 2
        # means we've already had a full round 1 without finishing the enemy.
        if state.flags.get("_combat_round", 1) >= 2:
            state.flags["combat_conditions"]["killed_in_one_round"] = False
        _print_combat_status(player, enemy, io)

        outcome = _player_round(state, enemy)
        if outcome is not None:
            break
        if not enemy.is_alive():
            outcome = "victory"
            break

        # Companion + hireling act between player and enemy
        _companion_act(state, enemy)
        if not enemy.is_alive():
            outcome = "victory"
            break
        _hireling_act(state, enemy)

        outcome = _enemy_round(state, enemy)
        if outcome is not None:
            break
        if not player.is_alive():
            outcome = "defeat"
            break

        # Round complete — increment for the killed_in_one_round condition.
        state.flags["_combat_round"] = state.flags.get("_combat_round", 1) + 1

    _post_combat(state, enemy, outcome, refresh_after)
    return outcome

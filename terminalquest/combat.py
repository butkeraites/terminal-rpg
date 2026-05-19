"""Turn-based combat.

Turn economy: every player action (attack, ability, potion, defend, or a
failed flee) consumes the player's turn and is followed by the enemy's
turn. Using a potion is no longer a free action.

``run_combat`` drives the loop through a ``GameIO`` so it is fully
testable with ``ScriptedIO``. Damage/AI helpers are pure functions of
their arguments and an injected ``random.Random`` for determinism.
"""
from . import status

ATTACK_VARIANCE = (-2, 4)
CRIT_CHANCE = 0.15
CRIT_MULTIPLIER = 1.8
STAMINA_PER_TURN = 2
FLEE_CHANCE = 0.5
POTION_HEAL = {"Health Potion": 40, "Greater Potion": 80}
DEFEND_TURNS = 1


def _perform_attack(attacker, target, power, rng):
    """Resolve one attack. Returns ``(damage_dealt, dodged, crit)``."""
    if status.has_status(target, "evasive") and rng.random() < 0.5:
        return 0, True, False
    base = attacker.attack * status.attack_multiplier(attacker)
    raw = max(1, round(base * power) + rng.randint(*ATTACK_VARIANCE))
    crit = rng.random() < CRIT_CHANCE
    if crit:
        raw = round(raw * CRIT_MULTIPLIER)
    return target.take_damage(raw), False, crit


def _resolve_start_of_turn(combatant, io):
    """Tick damage-over-time and timers. Returns True if the combatant survives."""
    dot, messages = status.tick_statuses(combatant)
    for message in messages:
        io.show(message)
    if dot:
        combatant.hp -= dot
    return combatant.is_alive()


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
        io.show("3. Use Health Potion")
        io.show("4. Defend")
        io.show("5. Flee")
        choice = io.ask("\nWhat do you do? ")

        if choice == "1":
            damage, dodged, crit = _perform_attack(player, enemy, 1.0, rng)
            if dodged:
                io.show(f"\n💨 {enemy.name} dodges your attack!")
            elif crit:
                io.show(f"\n💥 CRITICAL HIT! You deal {damage} damage to {enemy.name}!")
            else:
                io.show(f"\n💥 You deal {damage} damage to {enemy.name}!")
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
            owned = [name for name in POTION_HEAL if name in player.inventory]
            if not owned:
                io.show("\n❌ You have no potions!")
                continue
            if len(owned) == 1:
                potion = owned[0]
            else:
                for index, name in enumerate(owned, start=1):
                    io.show(f"{index}. {name} (+{POTION_HEAL[name]} HP)")
                io.show(f"{len(owned) + 1}. Cancel")
                pick = io.ask("\nWhich potion? ")
                if pick == str(len(owned) + 1):
                    continue
                if not (pick.isdigit() and 1 <= int(pick) <= len(owned)):
                    io.show("\n❌ Invalid choice!")
                    continue
                potion = owned[int(pick) - 1]
            player.inventory.remove(potion)
            heal = POTION_HEAL[potion]
            player.heal(heal)
            io.show(f"\n💚 You drink a {potion} and restore {heal} HP "
                    f"({player.hp}/{player.max_hp}).")
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


def _enemy_turn(enemy, player, io, rng):
    """Run the enemy's action according to its AI. Returns 'acted' or 'fled'."""
    low_hp = enemy.hp <= enemy.max_hp * 0.35

    if enemy.ai == "fleer" and enemy.hp <= enemy.max_hp * 0.30 and rng.random() < 0.5:
        io.show(f"\n🏃 {enemy.name} flees from the fight!")
        return "fled"

    if enemy.ai == "defensive" and low_hp and not status.has_status(enemy, "braced"):
        status.apply_status(enemy, "braced", DEFEND_TURNS)
        io.show(f"\n🛡️  {enemy.name} braces defensively.")
        return "acted"

    if enemy.ai == "caster" and enemy.ability and rng.random() < 0.5:
        spell = enemy.ability
        damage, dodged, crit = _perform_attack(enemy, player, spell["power"], rng)
        if dodged:
            io.show(f"\n💨 You dodge {enemy.name}'s {spell['name']}!")
        else:
            if crit:
                io.show(f"\n💥 CRITICAL! {enemy.name}'s {spell['name']} blasts you "
                        f"for {damage} damage!")
            else:
                io.show(f"\n🌑 {enemy.name} uses {spell['name']} for {damage} damage!")
            if "status" in spell:
                status.apply_status(player, spell["status"], spell["status_turns"])
                io.show(f"   You are afflicted with {spell['status']}!")
        return "acted"

    power = 1.5 if (enemy.ai == "aggressive" and rng.random() < 0.3) else 1.0
    damage, dodged, crit = _perform_attack(enemy, player, power, rng)
    if dodged:
        io.show(f"\n💨 You dodge {enemy.name}'s attack!")
    elif crit:
        io.show(f"\n💥 {enemy.name} lands a CRITICAL blow for {damage} damage!")
    elif power > 1.0:
        io.show(f"\n💢 {enemy.name} lands a heavy blow for {damage} damage!")
    else:
        io.show(f"\n💢 {enemy.name} deals {damage} damage to you!")
    return "acted"


def _grant_rewards(player, enemy, io):
    """Award XP and gold for a defeated enemy, reporting any level-ups."""
    io.show_slow(f"\n🎉 You defeated {enemy.name}!")
    io.show(f"Gained {enemy.xp_reward} XP and {enemy.gold_reward} gold!")
    player.gold += enemy.gold_reward
    if player.gain_xp(enemy.xp_reward):
        io.show(f"\n🎉 LEVEL UP! You are now level {player.level}!")
        io.show(f"HP: {player.max_hp} | Attack: {player.attack} | "
                f"Defense: {player.defense} | Stamina: {player.max_stamina}")


def run_combat(state, enemy):
    """Fight ``enemy`` to a conclusion.

    Returns one of: 'victory', 'defeat', 'fled', 'enemy_fled'.
    Combat-only status effects are cleared and stamina restored on exit.
    """
    player, content, io, rng = state.player, state.content, state.io, state.rng
    io.show_slow(f"\n⚔️  A wild {enemy.name} appears!")

    outcome = None
    while outcome is None:
        io.show(f"\n{player.name}: {player.hp}/{player.max_hp} HP | "
                f"⚡{player.stamina}/{player.max_stamina}")
        io.show(f"{enemy.name}: {enemy.hp}/{enemy.max_hp} HP")
        enemy_effects = status.describe(enemy)
        if enemy_effects:
            io.show(f"{enemy.name} status: {enemy_effects}")

        # --- player turn ---
        stunned = status.has_status(player, "stun")
        if not _resolve_start_of_turn(player, io):
            outcome = "defeat"
            break
        player.restore_stamina(STAMINA_PER_TURN)
        if stunned:
            io.show("\n💫 You are stunned and lose your turn!")
        else:
            if _player_turn(player, enemy, content, io, rng) == "fled":
                outcome = "fled"
                break
        if not enemy.is_alive():
            outcome = "victory"
            break

        # --- enemy turn ---
        enemy_stunned = status.has_status(enemy, "stun")
        if not _resolve_start_of_turn(enemy, io):
            outcome = "victory"
            break
        if enemy_stunned:
            io.show(f"\n💫 {enemy.name} is stunned and loses its turn!")
        elif _enemy_turn(enemy, player, io, rng) == "fled":
            outcome = "enemy_fled"
            break
        if not player.is_alive():
            outcome = "defeat"
            break

    if outcome == "victory":
        _grant_rewards(player, enemy, io)

    player.statuses.clear()
    player.stamina = player.max_stamina
    return outcome

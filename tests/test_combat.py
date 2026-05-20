"""Combat: damage resolution, abilities, AI and the turn economy."""
from conftest import StubRandom, make_state

from terminalquest import combat, status
from terminalquest.enemy import make_enemy
from terminalquest.player import Player
from terminalquest.ui import ScriptedIO
from terminalquest.weapon import make_weapon


def _player(content, class_id="warrior"):
    return Player("Hero", class_id, content.classes[class_id], content)


def test_perform_attack_applies_defense(content):
    attacker = _player(content)
    goblin = make_enemy("goblin", content)
    damage, dodged, crit = combat._perform_attack(attacker, goblin, 1.0, StubRandom())
    assert not dodged
    assert not crit  # StubRandom default rnd=0.9 never crits
    # warrior attack 12, goblin defense 2, zero variance
    assert damage == 10
    assert goblin.hp == goblin.max_hp - 10


def test_evasive_target_can_dodge(content):
    attacker = _player(content)
    goblin = make_enemy("goblin", content)
    status.apply_status(goblin, "evasive", 2)
    damage, dodged, crit = combat._perform_attack(attacker, goblin, 1.0, StubRandom(rnd=0.0))
    assert dodged
    assert damage == 0
    assert not crit


def test_critical_hit_multiplies_damage(content):
    """A low crit roll triggers a crit; damage exceeds the normal hit."""
    goblin = make_enemy("goblin", content)
    damage, dodged, crit = combat._perform_attack(
        _player(content), goblin, 1.0, StubRandom(rnd=0.0))
    assert crit
    assert not dodged
    # warrior 12 atk ×1.8 crit = 22 raw, −2 defense = 20 (a normal hit is 10)
    assert damage == 20


def test_ability_applies_status_effect(content):
    rogue = _player(content, "rogue")
    goblin = make_enemy("goblin", content)
    combat._use_ability(rogue, goblin, content.abilities["backstab"], ScriptedIO(), StubRandom())
    assert status.has_status(goblin, "bleed")


def test_heal_ability_restores_hp(content):
    cleric = _player(content, "cleric")
    cleric.hp = 10
    combat._use_ability(cleric, make_enemy("goblin", content),
                        content.abilities["mend"], ScriptedIO(), StubRandom())
    assert cleric.hp == 45


def test_potion_consumes_a_turn_so_enemy_retaliates(content):
    """Regression: drinking a potion is an action; the enemy gets its turn."""
    warrior = _player(content)
    warrior.hp = 30
    goblin = make_enemy("goblin", content)
    io = ScriptedIO(["3", "1", "1", "1"])
    state = make_state(warrior, content, io, StubRandom())
    outcome = combat.run_combat(state, goblin)
    assert outcome == "victory"
    # The potion healed to 70; retaliation on later turns leaves HP below that.
    assert warrior.hp < 70


def test_greater_potion_heals_more(content):
    """A Greater Potion restores 80 HP; one potion type needs no picker prompt."""
    warrior = _player(content)
    warrior.hp = 30
    warrior.consumables = ["Greater Potion"]
    result = combat._player_turn(warrior, make_enemy("goblin", content), content,
                                 ScriptedIO(["3"]), StubRandom())
    assert result == "acted"
    assert warrior.hp == 110  # 30 + 80
    assert "Greater Potion" not in warrior.consumables


def test_potion_picker_chooses_among_types(content):
    """With multiple potion types the player picks which to drink."""
    warrior = _player(content)
    warrior.hp = 30
    warrior.consumables = ["Health Potion", "Greater Potion"]
    io = ScriptedIO(["3", "2"])  # use potion -> pick option 2, the Greater Potion
    result = combat._player_turn(warrior, make_enemy("goblin", content), content,
                                 io, StubRandom())
    assert result == "acted"
    assert warrior.hp == 110  # Greater Potion = +80
    assert "Greater Potion" not in warrior.consumables
    assert "Health Potion" in warrior.consumables


def test_status_help_is_available_in_combat(content):
    """'?' in the combat menu prints the status glossary without using a turn."""
    warrior = _player(content)
    io = ScriptedIO(["?", "1"])
    result = combat._player_turn(warrior, make_enemy("goblin", content), content,
                                 io, StubRandom())
    assert result == "acted"
    assert "vulnerable" in io.text()


def test_weak_attacker_deals_reduced_damage(content):
    """weak applies after defense — 0.6x a normal post-defense hit, no flooring."""
    normal, _, _ = combat._perform_attack(
        _player(content), make_enemy("goblin", content), 1.0, StubRandom())
    weak_attacker = _player(content)
    status.apply_status(weak_attacker, "weak", 2)
    weak_dmg, _, _ = combat._perform_attack(
        weak_attacker, make_enemy("goblin", content), 1.0, StubRandom())
    assert weak_dmg == max(1, round(normal * 0.6))


def test_aggressive_enemy_telegraphs_a_heavy_blow(content):
    """An aggressive enemy winds up (no damage), then lands the blow next turn."""
    player = _player(content)
    goblin = make_enemy("goblin", content)  # the goblin's AI is aggressive
    io = ScriptedIO()
    rng = StubRandom(rnd=0.0)  # low roll -> the wind-up triggers
    full_hp = player.hp

    combat._enemy_turn(goblin, player, io, rng)
    assert goblin.winding_up == "heavy"
    assert player.hp == full_hp  # winding up deals no damage
    assert "rears back" in io.text()

    combat._enemy_turn(goblin, player, io, rng)
    assert goblin.winding_up is None
    assert player.hp < full_hp  # the telegraphed blow lands


def test_level_up_offers_a_boon_choice(content):
    """Winning a fight that grants a level prompts for a boon and applies it."""
    warrior = _player(content)
    warrior.xp = 95  # a goblin kill (30 XP) crosses the level-100 threshold
    base_attack = warrior.attack
    io = ScriptedIO(["1", "1", "1", "2"])  # 3 attacks to win, then boon 2 (Might)
    state = make_state(warrior, content, io, StubRandom())
    assert combat.run_combat(state, make_enemy("goblin", content)) == "victory"
    assert warrior.level == 2
    assert warrior.attack == base_attack + 9  # +2 baseline, +7 Might boon


def test_victory_grants_xp_and_gold(content):
    warrior = _player(content)
    goblin = make_enemy("goblin", content)
    starting_gold = warrior.gold
    state = make_state(warrior, content, ScriptedIO(["1", "1", "1"]), StubRandom())
    outcome = combat.run_combat(state, goblin)
    assert outcome == "victory"
    assert warrior.gold == starting_gold + goblin.gold_reward


def test_defeat_when_player_dies(content):
    mage = _player(content, "mage")
    mage.hp = 5
    golem = make_enemy("stone_golem", content)
    state = make_state(mage, content, ScriptedIO(["1", "1"]), StubRandom())
    outcome = combat.run_combat(state, golem)
    assert outcome == "defeat"


def test_flee_succeeds_on_a_winning_roll(content):
    warrior = _player(content)
    goblin = make_enemy("goblin", content)
    state = make_state(warrior, content, ScriptedIO(["5"]), StubRandom(rnd=0.0))
    outcome = combat.run_combat(state, goblin)
    assert outcome == "fled"


def test_relentless_enemy_surges_every_third_turn(content):
    """A relentless enemy strikes normally twice, then surges on the third turn."""
    player = _player(content)
    lurcher = make_enemy("bog_lurcher", content)  # ai: relentless
    io = ScriptedIO()
    rng = StubRandom()  # no crits, no dodges, zero variance — deterministic

    hp = player.hp
    combat._enemy_turn(lurcher, player, io, rng)
    first = hp - player.hp
    hp = player.hp
    combat._enemy_turn(lurcher, player, io, rng)
    second = hp - player.hp
    hp = player.hp
    combat._enemy_turn(lurcher, player, io, rng)
    surge = hp - player.hp

    assert first == second  # turns one and two are ordinary blows
    assert surge > second   # the third turn is the heavy surge
    assert "surges forward" in io.text()


def test_enrager_grows_stronger_once_wounded(content):
    """An enrager below half HP latches into a frenzy and gains attack each turn."""
    player = _player(content)
    procession = make_enemy("hollow_procession", content)  # ai: enrager
    procession.hp = procession.max_hp // 3  # wounded past the enrage threshold
    base_attack = procession.attack

    io = ScriptedIO()
    combat._enemy_turn(procession, player, io, StubRandom())

    assert procession.enraged
    assert procession.attack > base_attack
    assert "frenzy" in io.text()


def _bleed_weapon(content):
    return make_weapon(content, {"head": "bog_iron_head", "haft": "withe_haft",
                                 "core": "bleeding_core",
                                 "inscription": "mourners_mark"}, "Bleeder")


def test_weapon_proc_applies_a_status_on_crit(content):
    """D2: a Bleeding-Edge Core leaves the enemy bleeding when the player crits."""
    player = _player(content)
    player.equip_weapon(_bleed_weapon(content))
    goblin = make_enemy("goblin", content)
    combat._fire_procs(player, goblin, dodged=False, crit=True, io=ScriptedIO())
    assert status.has_status(goblin, "bleed")


def test_weapon_proc_holds_until_its_trigger(content):
    player = _player(content)
    player.equip_weapon(_bleed_weapon(content))
    goblin = make_enemy("goblin", content)
    combat._fire_procs(player, goblin, dodged=False, crit=False, io=ScriptedIO())
    assert not status.has_status(goblin, "bleed")  # on_crit needs a crit


def test_a_crit_in_a_turn_fires_the_weapon_proc(content):
    player = _player(content)
    player.equip_weapon(_bleed_weapon(content))
    troll = make_enemy("cave_troll", content)  # tanky enough to survive the hit
    combat._player_turn(player, troll, content, ScriptedIO(["1"]), StubRandom(rnd=0.0))
    assert status.has_status(troll, "bleed")


def test_run_combat_skips_stamina_restore_when_refresh_after_false(content):
    """Chained sub-fights persist stamina: run_combat does not refill on exit."""
    warrior = _player(content)
    warrior.attack = 1000  # one-shot the goblin so the fight ends in one turn
    warrior.stamina = 3
    io = ScriptedIO(["2", "1"])  # use Power Strike (3 stamina)
    state = make_state(warrior, content, io, StubRandom())
    outcome = combat.run_combat(state, make_enemy("goblin", content), refresh_after=False)
    assert outcome == "victory"
    # +2 regen at start of turn brings stamina to 5, Power Strike spends 3 -> 2.
    # With refresh_after=False, that drained state is preserved.
    assert warrior.stamina == 2


def test_run_combat_restores_stamina_by_default(content):
    """The normal single-fight case still refills stamina at the end."""
    warrior = _player(content)
    warrior.attack = 1000
    warrior.stamina = 0
    io = ScriptedIO(["1"])  # basic attack
    state = make_state(warrior, content, io, StubRandom())
    combat.run_combat(state, make_enemy("goblin", content))
    assert warrior.stamina == warrior.max_stamina


def test_stamina_regen_is_announced_each_turn(content):
    """Bug A fix: the +2/turn regen prints a message so the math is no longer hidden."""
    warrior = _player(content)
    warrior.stamina = 0  # drained, so regen has room to tick
    goblin = make_enemy("goblin", content)
    io = ScriptedIO(["1", "1", "1", "1"])  # attack until the goblin dies
    state = make_state(warrior, content, io, StubRandom())
    combat.run_combat(state, goblin)
    assert "catch your breath" in io.text()


def test_boon_menu_shows_locked_skill_option_when_nothing_unlocked_yet(content):
    """Below the first progression gate, option 4 still appears with a hint.

    Brother's v0.5.0 feedback: at level 2 the boon menu only showed 3 options
    and he thought the class was missing the system entirely. Now option 4
    always renders — locked with '(next unlocks at level X)' before any
    skill is reachable.
    """
    warrior = _player(content)
    warrior.xp = warrior.xp_to_level - 1  # one XP shy of level 2
    io = ScriptedIO(["1", "1", "1", "2"])  # 3 attacks, then boon 2 (Might)
    state = make_state(warrior, content, io, StubRandom())
    combat.run_combat(state, make_enemy("goblin", content))
    assert warrior.level == 2  # below the lv-3 progression gate
    text = io.text()
    assert "🔒 Learn a new skill" in text
    assert "unlocks at level 3" in text


def test_boon_menu_offers_skill_when_progression_unlocks(content):
    """Crossing into level 3 surfaces the 4th boon — a skill unlock."""
    warrior = _player(content)
    warrior.level = 2
    warrior.xp = 0
    warrior.xp_to_level = 30  # a goblin kill (30 XP) tips us to level 3
    # 3 attacks to win, then boon 4 (Learn), then sub-menu pick 1
    io = ScriptedIO(["1", "1", "1", "4", "1"])
    state = make_state(warrior, content, io, StubRandom())
    combat.run_combat(state, make_enemy("goblin", content))
    assert warrior.level == 3
    assert "sundering_strike" in warrior.abilities
    assert "Learn a new skill" in io.text()


def test_learning_a_skill_still_applies_baseline(content):
    """Picking the 'Learn' boon grants baseline stats but skips the boon's bonus."""
    warrior = _player(content)
    warrior.level = 2
    warrior.xp = 0
    warrior.xp_to_level = 30
    base_attack = warrior.attack
    io = ScriptedIO(["1", "1", "1", "4", "1"])
    state = make_state(warrior, content, io, StubRandom())
    combat.run_combat(state, make_enemy("goblin", content))
    # Baseline only: +2 attack, no Might/Vigor/Bulwark gain.
    assert warrior.attack == base_attack + 2


def test_overleveled_kill_awards_gold_only(content):
    """A player far above a zone's recommended level no longer gets XP from it."""
    warrior = _player(content)
    warrior.level = 20  # the Witherwood (recommended 1) has nothing left to teach
    warrior.attack = 1000  # one-shot
    xp_before = warrior.xp
    gold_before = warrior.gold
    io = ScriptedIO(["1"])  # one attack ends it
    state = make_state(warrior, content, io, StubRandom(), current_location="forest")
    combat.run_combat(state, make_enemy("goblin", content))
    assert warrior.xp == xp_before  # no XP
    assert warrior.gold > gold_before  # gold still drops
    assert "nothing left to teach you" in io.text()


def test_at_level_kill_grants_xp_normally(content):
    """Within the over-level threshold, XP flows as before."""
    warrior = _player(content)
    warrior.level = 1  # bang on the Witherwood's recommended level
    warrior.attack = 1000
    xp_before = warrior.xp
    io = ScriptedIO(["1"])
    state = make_state(warrior, content, io, StubRandom(), current_location="forest")
    combat.run_combat(state, make_enemy("goblin", content))
    assert warrior.xp > xp_before  # XP awarded


def test_pall_drinker_restores_full_stamina(content):
    """The Pall-Drinker tops HP and stamina back to full in one drink."""
    warrior = _player(content)
    warrior.hp = 10
    warrior.stamina = 0
    warrior.consumables = ["Pall-Drinker"]
    result = combat._player_turn(warrior, make_enemy("goblin", content), content,
                                 ScriptedIO(["3"]), StubRandom())
    assert result == "acted"
    assert warrior.hp == warrior.max_hp  # huge heal caps at max
    assert warrior.stamina == warrior.max_stamina
    assert "Pall-Drinker" not in warrior.consumables

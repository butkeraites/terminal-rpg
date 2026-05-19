"""Combat: damage resolution, abilities, AI and the turn economy."""
from conftest import StubRandom, make_state

from terminalquest import combat, status
from terminalquest.enemy import make_enemy
from terminalquest.player import Player
from terminalquest.ui import ScriptedIO


def _player(content, class_id="warrior"):
    return Player("Hero", class_id, content.classes[class_id])


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

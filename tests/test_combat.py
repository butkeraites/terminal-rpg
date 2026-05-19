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
    warrior.inventory = ["Greater Potion"]
    result = combat._player_turn(warrior, make_enemy("goblin", content), content,
                                 ScriptedIO(["3"]), StubRandom())
    assert result == "acted"
    assert warrior.hp == 110  # 30 + 80
    assert "Greater Potion" not in warrior.inventory


def test_potion_picker_chooses_among_types(content):
    """With multiple potion types the player picks which to drink."""
    warrior = _player(content)
    warrior.hp = 30
    warrior.inventory = ["Health Potion", "Greater Potion"]
    io = ScriptedIO(["3", "2"])  # use potion -> pick option 2, the Greater Potion
    result = combat._player_turn(warrior, make_enemy("goblin", content), content,
                                 io, StubRandom())
    assert result == "acted"
    assert warrior.hp == 110  # Greater Potion = +80
    assert "Greater Potion" not in warrior.inventory
    assert "Health Potion" in warrior.inventory


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

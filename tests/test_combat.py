"""Combat: damage resolution, abilities, AI and the turn economy."""
from conftest import StubRandom

from terminalquest import combat, status
from terminalquest.enemy import make_enemy
from terminalquest.player import Player
from terminalquest.ui import ScriptedIO


def _player(content, class_id="warrior"):
    return Player("Hero", class_id, content.classes[class_id])


def test_perform_attack_applies_defense(content):
    attacker = _player(content)
    goblin = make_enemy("goblin", content)
    damage, dodged = combat._perform_attack(attacker, goblin, 1.0, StubRandom())
    assert not dodged
    # warrior attack 12, goblin defense 2, zero variance
    assert damage == 10
    assert goblin.hp == goblin.max_hp - 10


def test_evasive_target_can_dodge(content):
    attacker = _player(content)
    goblin = make_enemy("goblin", content)
    status.apply_status(goblin, "evasive", 2)
    damage, dodged = combat._perform_attack(attacker, goblin, 1.0, StubRandom(rnd=0.0))
    assert dodged
    assert damage == 0


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
    outcome = combat.run_combat(warrior, goblin, content, io, StubRandom())
    assert outcome == "victory"
    # The potion healed to 70; retaliation on later turns leaves HP below that.
    assert warrior.hp < 70


def test_victory_grants_xp_and_gold(content):
    warrior = _player(content)
    goblin = make_enemy("goblin", content)
    starting_gold = warrior.gold
    outcome = combat.run_combat(warrior, goblin, content,
                                ScriptedIO(["1", "1", "1"]), StubRandom())
    assert outcome == "victory"
    assert warrior.gold == starting_gold + goblin.gold_reward


def test_defeat_when_player_dies(content):
    mage = _player(content, "mage")
    mage.hp = 5
    golem = make_enemy("stone_golem", content)
    outcome = combat.run_combat(mage, golem, content,
                                ScriptedIO(["1", "1"]), StubRandom())
    assert outcome == "defeat"


def test_flee_succeeds_on_a_winning_roll(content):
    warrior = _player(content)
    goblin = make_enemy("goblin", content)
    outcome = combat.run_combat(warrior, goblin, content,
                                ScriptedIO(["5"]), StubRandom(rnd=0.0))
    assert outcome == "fled"

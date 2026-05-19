"""Player stats, progression and serialization."""
from terminalquest.player import Player


def test_take_damage_subtracts_defense(warrior):
    warrior.defense = 5
    starting_hp = warrior.hp
    dealt = warrior.take_damage(20)
    assert dealt == 15
    assert warrior.hp == starting_hp - 15


def test_take_damage_minimum_one(warrior):
    warrior.defense = 1000
    assert warrior.take_damage(5) == 1


def test_heal_caps_at_max(warrior):
    warrior.hp = 10
    warrior.heal(99999)
    assert warrior.hp == warrior.max_hp


def test_level_up_applies_stat_gains(warrior):
    attack, defense = warrior.attack, warrior.defense
    warrior.level_up()
    assert warrior.level == 2
    assert warrior.attack == attack + 5
    assert warrior.defense == defense + 2
    assert warrior.hp == warrior.max_hp


def test_gain_xp_handles_multiple_level_ups(warrior):
    leveled = warrior.gain_xp(100_000)
    assert leveled
    assert warrior.level > 2


def test_serialization_round_trip(warrior):
    warrior.gain_xp(50)
    warrior.inventory.append("Health Potion")
    warrior.position = "world"
    clone = Player.from_dict(warrior.to_dict())
    assert clone.to_dict() == warrior.to_dict()

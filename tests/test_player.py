"""Player stats, progression and serialization."""
from terminalquest.player import LEVEL_BASELINE, LEVEL_BOONS, Player


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


def test_apply_level_up_grants_baseline_plus_boon(warrior):
    attack = warrior.attack
    warrior.apply_level_up("might")
    boon = LEVEL_BOONS["might"]["gains"]["attack"]
    assert warrior.attack == attack + LEVEL_BASELINE["attack"] + boon
    assert warrior.hp == warrior.max_hp  # a level-up restores HP


def test_gain_xp_handles_multiple_level_ups(warrior):
    leveled = warrior.gain_xp(100_000)
    assert leveled
    assert warrior.level > 2


def test_serialization_round_trip(warrior):
    warrior.gain_xp(50)
    warrior.consumables.append("Health Potion")
    clone = Player.from_dict(warrior.to_dict())
    assert clone.to_dict() == warrior.to_dict()


def test_new_player_has_consumables_and_empty_equipment(warrior):
    """C1: belongings split into a consumables bag and a (still empty) gear loadout."""
    assert warrior.consumables  # the class's starting kit
    assert warrior.equipment == {}

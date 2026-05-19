"""Combinatorial weapons: assembly from components and serialization."""
from terminalquest.weapon import Weapon, make_weapon


def test_make_weapon_sums_component_stats(content):
    ids = {"head": "bog_iron_head", "haft": "withe_haft",
           "core": "grave_iron_core", "inscription": "mourners_mark"}
    weapon = make_weapon(content, ids, "Probe Blade")
    expected = {}
    for slot, cid in ids.items():
        for stat, amount in content.components[slot][cid]["stats"].items():
            expected[stat] = expected.get(stat, 0) + amount
    assert weapon.name == "Probe Blade"
    assert weapon.components == ids
    assert weapon.stats == expected


def test_components_in_different_slots_stack_their_stats(content):
    """A weapon's stats are the summed bonuses of all four of its components."""
    ids = {"head": "ashen_greathead", "haft": "bellrope_grip",
           "core": "warden_seal_core", "inscription": "hold_fast_rune"}
    weapon = make_weapon(content, ids, "Reliquary")
    assert weapon.stats["attack"] == 11   # greathead 10 + bell-rope grip 1
    assert weapon.stats["max_hp"] == 17   # warden's seal 5 + hold-fast rune 12


def test_weapon_round_trips_through_a_dict(content):
    ids = {"head": "reliquary_edge", "haft": "weir_pole",
           "core": "pall_glass_core", "inscription": "last_breath_verse"}
    weapon = make_weapon(content, ids, "Keening")
    clone = Weapon.from_dict(weapon.to_dict())
    assert clone.to_dict() == weapon.to_dict()

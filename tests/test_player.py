"""Player stats, progression and serialization."""
from terminalquest.player import LEVEL_BASELINE, LEVEL_BOONS, Player
from terminalquest.weapon import make_weapon


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


def test_new_player_starts_with_consumables_and_a_weapon(warrior):
    """C1/C3: belongings are a consumables bag plus a loadout with a starting weapon."""
    assert warrior.consumables  # the class's starting kit
    assert "weapon" in warrior.equipment


def _weapon(content, head="reliquary_edge"):
    return make_weapon(content, {"head": head, "haft": "withe_haft",
                                 "core": "grave_iron_core",
                                 "inscription": "mourners_mark"}, "Probe")


def test_equipping_a_weapon_applies_its_stats(warrior, content):
    warrior.unequip_weapon()  # set the class starting weapon aside
    base_attack, base_hp = warrior.attack, warrior.max_hp
    weapon = _weapon(content)
    warrior.equip_weapon(weapon)
    assert warrior.attack == base_attack + weapon.stats.get("attack", 0)
    assert warrior.max_hp == base_hp + weapon.stats.get("max_hp", 0)
    assert warrior.equipment["weapon"] is weapon


def test_unequipping_a_weapon_restores_stats(warrior, content):
    warrior.unequip_weapon()  # start from the bare class base
    before = (warrior.attack, warrior.defense, warrior.max_hp, warrior.max_stamina)
    weapon = _weapon(content)
    warrior.equip_weapon(weapon)
    assert warrior.unequip_weapon() is weapon
    after = (warrior.attack, warrior.defense, warrior.max_hp, warrior.max_stamina)
    assert after == before
    assert "weapon" not in warrior.equipment


def test_equipping_replaces_the_previous_weapon(warrior, content):
    warrior.unequip_weapon()  # set the class starting weapon aside
    base_attack = warrior.attack
    warrior.equip_weapon(_weapon(content, head="bog_iron_head"))
    strong = _weapon(content, head="ashen_greathead")
    warrior.equip_weapon(strong)
    assert warrior.attack == base_attack + strong.stats["attack"]

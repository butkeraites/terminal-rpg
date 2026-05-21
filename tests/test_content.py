"""Content files load and are internally consistent."""
import pytest

from terminalquest.content import ContentError, _load, load_content


def test_load_content_succeeds():
    content = load_content()
    assert len(content.classes) == 5
    assert content.abilities and content.enemies and content.locations


def test_class_abilities_exist():
    content = load_content()
    for cls in content.classes.values():
        for ability_id in cls["abilities"]:
            assert ability_id in content.abilities


def test_location_encounters_reference_real_enemies():
    content = load_content()
    for loc in content.locations.values():
        for encounter in loc.get("encounters", []):
            for enemy_id in encounter.get("enemies", []):
                assert enemy_id in content.enemies


def test_location_connections_resolve():
    content = load_content()
    for loc in content.locations.values():
        for dest in loc.get("connections", []):
            assert dest in content.locations


def test_validate_rejects_unknown_enemy_reference():
    content = load_content()
    content.locations["forest"]["encounters"][0]["enemies"].append("dragon")
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_unknown_ai():
    content = load_content()
    content.enemies["goblin"]["ai"] = "berserk"
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_dangling_connection():
    content = load_content()
    content.locations["forest"]["connections"].append("atlantis")
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_unreachable_location():
    content = load_content()
    content.locations["crossroads"]["connections"].remove("forest")
    with pytest.raises(ValueError):
        content.validate()


def test_boss_location_has_single_valid_enemy():
    content = load_content()
    boss_locs = [loc for loc in content.locations.values() if loc.get("boss")]
    assert boss_locs, "expected at least one boss location"
    for loc in boss_locs:
        encounters = loc["encounters"]
        assert len(encounters) == 1
        assert len(encounters[0]["enemies"]) == 1
        assert encounters[0]["enemies"][0] in content.enemies


def test_zones_have_a_recommended_level():
    content = load_content()
    for loc in content.locations.values():
        if loc.get("kind") == "zone" and not loc.get("boss"):
            assert isinstance(loc["recommended_level"], int)


def test_load_rejects_a_missing_data_file():
    """A missing data file fails with a clear ContentError, not a raw crash."""
    with pytest.raises(ContentError):
        _load("does_not_exist.json")


def test_every_zone_declares_an_act():
    content = load_content()
    for loc_id, loc in content.locations.items():
        if loc.get("kind") == "zone":
            assert loc["act"] in (1, 2, 3), loc_id


def test_discovery_encounters_carry_an_id_and_lines():
    content = load_content()
    discoveries = [enc for loc in content.locations.values()
                   for enc in loc.get("encounters", []) if enc["type"] == "discovery"]
    assert discoveries, "the expanded world should add discovery fragments"
    for discovery in discoveries:
        assert discovery["id"]
        assert discovery["lines"]


def test_validate_rejects_a_discovery_without_lines():
    content = load_content()
    content.locations["forest"]["encounters"].append(
        {"type": "discovery", "id": "phantom"})
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_a_zone_without_an_act():
    content = load_content()
    del content.locations["forest"]["act"]
    with pytest.raises(ValueError):
        content.validate()


def test_components_load_with_four_slots():
    content = load_content()
    for slot in ("head", "haft", "core", "inscription"):
        assert content.components[slot], slot


def test_validate_rejects_an_unknown_component_stat():
    content = load_content()
    some_head = next(iter(content.components["head"].values()))
    some_head["stats"]["wisdom"] = 5
    with pytest.raises(ValueError):
        content.validate()


def test_component_pool_has_breadth():
    """D3: each weapon slot offers a substantial pool of components."""
    content = load_content()
    for slot in ("head", "haft", "core", "inscription"):
        assert len(content.components[slot]) >= 12, slot


def test_validate_rejects_an_unknown_proc_status():
    content = load_content()
    some_core = next(iter(content.components["core"].values()))
    some_core["proc"] = {"trigger": "on_hit", "status": "enlightenment", "turns": 1}
    with pytest.raises(ValueError):
        content.validate()


def test_every_class_has_a_three_step_progression():
    """Each class unlocks three new abilities across the climb (levels 3/5/7)."""
    content = load_content()
    for class_id, cls in content.classes.items():
        progression = cls.get("progression")
        assert progression and len(progression) == 3, class_id
        for entry in progression:
            assert entry["ability"] in content.abilities, (class_id, entry)
            assert isinstance(entry["level"], int) and entry["level"] > 0


def test_validate_rejects_unknown_progression_ability():
    content = load_content()
    content.classes["warrior"]["progression"].append(
        {"ability": "wisdom_of_the_pall", "level": 4})
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_a_non_positive_progression_level():
    content = load_content()
    content.classes["warrior"]["progression"][0]["level"] = 0
    with pytest.raises(ValueError):
        content.validate()


def test_quests_load_and_target_real_enemies():
    """quests.json is loaded as Content.quests and every target_enemy exists."""
    content = load_content()
    assert content.quests, "quests.json should ship with the game"
    for qid, quest in content.quests.items():
        assert quest["target_enemy"] in content.enemies, (
            f"quest {qid!r} targets unknown enemy {quest['target_enemy']!r}")
        assert isinstance(quest["needed"], int) and quest["needed"] > 0
        assert isinstance(quest["reward_gold"], int) and quest["reward_gold"] >= 0
        assert isinstance(quest["cleanse_required"], int)
        assert quest["cleanse_required"] >= 0


def test_validate_rejects_quest_targeting_unknown_enemy():
    """A quest with a typo in target_enemy must fail content validation."""
    content = load_content()
    content.quests["bogus_quest"] = {
        "name": "Hunt the Imaginary",
        "target_enemy": "this_enemy_does_not_exist",
        "needed": 1,
        "reward_gold": 1,
        "cleanse_required": 0,
    }
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_quest_missing_required_field():
    """A quest missing 'needed' (or any required field) fails validation."""
    content = load_content()
    content.quests["incomplete"] = {
        "name": "Half a Quest",
        "target_enemy": "wolf",
        # 'needed' deliberately omitted
        "reward_gold": 50,
        "cleanse_required": 0,
    }
    with pytest.raises(ValueError):
        content.validate()

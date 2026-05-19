"""Content files load and are internally consistent."""
import pytest

from terminalquest.content import load_content


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
            for enemy_id in encounter["enemies"]:
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

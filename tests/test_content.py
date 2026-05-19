"""Content files load and are internally consistent."""
import pytest

from terminalquest.content import load_content


def test_load_content_succeeds():
    content = load_content()
    assert len(content.classes) == 5
    assert content.abilities and content.enemies and content.zones


def test_class_abilities_exist():
    content = load_content()
    for cls in content.classes.values():
        for ability_id in cls["abilities"]:
            assert ability_id in content.abilities


def test_zone_enemies_exist():
    content = load_content()
    for zone in content.zones.values():
        for enemy_id in zone["enemies"]:
            assert enemy_id in content.enemies


def test_validate_rejects_unknown_enemy_reference():
    content = load_content()
    content.zones["forest"]["enemies"].append("dragon")
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_unknown_ai():
    content = load_content()
    content.enemies["goblin"]["ai"] = "berserk"
    with pytest.raises(ValueError):
        content.validate()

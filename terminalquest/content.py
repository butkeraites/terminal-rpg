"""Loads game content from the bundled JSON data files.

All gameplay content (classes, abilities, enemies, zones) lives in
``terminalquest/data/*.json`` so designers can extend the game without
touching Python. This module is the only place that reads those files.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

_VALID_AI = {"aggressive", "defensive", "caster", "fleer"}


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


class Content:
    """An immutable bundle of all loaded game content."""

    def __init__(self, classes, abilities, enemies, zones):
        self.classes = classes
        self.abilities = abilities
        self.enemies = enemies
        self.zones = zones

    def validate(self):
        """Raise ValueError if the data files are internally inconsistent."""
        for class_id, cls in self.classes.items():
            for ability_id in cls["abilities"]:
                if ability_id not in self.abilities:
                    raise ValueError(
                        f"class '{class_id}' references unknown ability '{ability_id}'"
                    )
        for enemy_id, enemy in self.enemies.items():
            if enemy["ai"] not in _VALID_AI:
                raise ValueError(
                    f"enemy '{enemy_id}' has invalid ai '{enemy['ai']}'"
                )
        for zone_id, zone in self.zones.items():
            for enemy_id in zone["enemies"]:
                if enemy_id not in self.enemies:
                    raise ValueError(
                        f"zone '{zone_id}' references unknown enemy '{enemy_id}'"
                    )


def load_content():
    """Load and validate every content file, returning a Content bundle."""
    content = Content(
        classes=_load("classes.json"),
        abilities=_load("abilities.json"),
        enemies=_load("enemies.json"),
        zones=_load("zones.json"),
    )
    content.validate()
    return content

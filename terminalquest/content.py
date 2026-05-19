"""Loads game content from the bundled JSON data files.

All gameplay content (classes, abilities, enemies, locations) lives in
``terminalquest/data/*.json`` so designers can extend the game without
touching Python. This module is the only place that reads those files.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

_VALID_AI = {"aggressive", "defensive", "caster", "fleer"}
_VALID_ENCOUNTER_TYPES = {"combat"}


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


class Content:
    """An immutable bundle of all loaded game content."""

    def __init__(self, classes, abilities, enemies, locations):
        self.classes = classes
        self.abilities = abilities
        self.enemies = enemies
        self.locations = locations

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
        self._validate_locations()

    def _validate_locations(self):
        """Check the location graph: connections, encounters, reachability."""
        if "crossroads" not in self.locations:
            raise ValueError("no 'crossroads' location — the graph needs a hub")
        for loc_id, loc in self.locations.items():
            for dest in loc.get("connections", []):
                if dest not in self.locations:
                    raise ValueError(
                        f"location '{loc_id}' connects to unknown location '{dest}'"
                    )
            for encounter in loc.get("encounters", []):
                kind = encounter["type"]
                if kind not in _VALID_ENCOUNTER_TYPES:
                    raise ValueError(
                        f"location '{loc_id}' has unknown encounter type '{kind}'"
                    )
                if kind == "combat":
                    for enemy_id in encounter["enemies"]:
                        if enemy_id not in self.enemies:
                            raise ValueError(
                                f"location '{loc_id}' references unknown enemy "
                                f"'{enemy_id}'"
                            )
        self._check_reachable()

    def _check_reachable(self):
        """Every location must be reachable from the crossroads."""
        seen = set()
        frontier = ["crossroads"]
        while frontier:
            loc_id = frontier.pop()
            if loc_id in seen:
                continue
            seen.add(loc_id)
            frontier.extend(self.locations[loc_id].get("connections", []))
        unreachable = set(self.locations) - seen
        if unreachable:
            raise ValueError(
                f"locations unreachable from the crossroads: {sorted(unreachable)}"
            )


def load_content():
    """Load and validate every content file, returning a Content bundle."""
    content = Content(
        classes=_load("classes.json"),
        abilities=_load("abilities.json"),
        enemies=_load("enemies.json"),
        locations=_load("locations.json"),
    )
    content.validate()
    return content

"""Loads game content from the bundled JSON data files.

All gameplay content (classes, abilities, enemies, locations) lives in
``terminalquest/data/*.json`` so designers can extend the game without
touching Python. This module is the only place that reads those files.
"""
import json
from pathlib import Path

from . import dialogue, status
from .weapon import WEAPON_SLOTS

DATA_DIR = Path(__file__).parent / "data"

_VALID_AI = {"aggressive", "defensive", "caster", "fleer", "relentless", "enrager"}
_VALID_ENCOUNTER_TYPES = {"combat", "discovery", "npc", "dialogue"}
_VALID_ACTS = {1, 2, 3}
_VALID_STATS = {"attack", "defense", "max_hp", "max_stamina"}
_VALID_PROC_TRIGGERS = {"on_hit", "on_crit"}
_VALID_TIERS = {1, 2, 3}


class ContentError(ValueError):
    """Raised when a data file is missing or malformed."""


def _load(name):
    path = DATA_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContentError(f"missing data file: {name}") from exc
    except json.JSONDecodeError as exc:
        raise ContentError(f"{name} is not valid JSON: {exc}") from exc


class Content:
    """An immutable bundle of all loaded game content."""

    def __init__(self, classes, abilities, enemies, locations, components, armor,
                 companions, accessories, pets, hirelings, npcs, dialogues,
                 marks=None):
        self.classes = classes
        self.abilities = abilities
        self.enemies = enemies
        self.locations = locations
        self.components = components
        self.armor = armor
        self.companions = companions
        self.accessories = accessories
        self.pets = pets
        self.hirelings = hirelings
        self.npcs = npcs
        self.dialogues = dialogues
        # v1.51 — irreversible per-character events (the Marks system).
        # An empty dict is valid; the engine no-ops when the pool is empty.
        self.marks = marks or {}

    def validate(self):
        """Raise ValueError if the data files are internally inconsistent."""
        for class_id, cls in self.classes.items():
            for ability_id in cls["abilities"]:
                if ability_id not in self.abilities:
                    raise ValueError(
                        f"class '{class_id}' references unknown ability '{ability_id}'"
                    )
            for slot in WEAPON_SLOTS:
                cid = cls["weapon"]["components"][slot]
                if cid not in self.components[slot]:
                    raise ValueError(
                        f"class '{class_id}' starting weapon references "
                        f"unknown {slot} component '{cid}'"
                    )
            for entry in cls.get("progression", []):
                ability_id = entry.get("ability")
                level = entry.get("level")
                if ability_id not in self.abilities:
                    raise ValueError(
                        f"class '{class_id}' progression references unknown "
                        f"ability '{ability_id}'"
                    )
                if not (isinstance(level, int) and level > 0):
                    raise ValueError(
                        f"class '{class_id}' progression entry for '{ability_id}' "
                        f"has invalid level {level!r}"
                    )
        for enemy_id, enemy in self.enemies.items():
            if enemy["ai"] not in _VALID_AI:
                raise ValueError(
                    f"enemy '{enemy_id}' has invalid ai '{enemy['ai']}'"
                )
        self._validate_locations()
        self._validate_components()
        for dialogue_id, tree in self.dialogues.items():
            dialogue.validate_tree(tree, dialogue_id)

    def _validate_locations(self):
        """Check the location graph: connections, encounters, acts, reachability."""
        if "crossroads" not in self.locations:
            raise ValueError("no 'crossroads' location — the graph needs a hub")
        for loc_id, loc in self.locations.items():
            if loc.get("kind") == "zone" and loc.get("act") not in _VALID_ACTS:
                raise ValueError(
                    f"zone '{loc_id}' has invalid act {loc.get('act')!r}"
                )
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
                elif kind == "discovery":
                    if not encounter.get("id"):
                        raise ValueError(
                            f"location '{loc_id}' has a discovery with no id"
                        )
                    if not encounter.get("lines"):
                        raise ValueError(
                            f"location '{loc_id}' discovery '{encounter['id']}' "
                            f"has no lines"
                        )
                elif kind == "npc":
                    if not encounter.get("id"):
                        raise ValueError(
                            f"location '{loc_id}' has an npc with no id"
                        )
                elif kind == "dialogue":
                    did = encounter.get("dialogue_id")
                    if did is None or did not in self.dialogues:
                        raise ValueError(
                            f"location '{loc_id}' dialogue encounter references "
                            f"unknown dialogue '{did}'"
                        )
        self._check_reachable()

    def _check_reachable(self):
        """Every location must be reachable from the crossroads.

        Sub-zones that gate behind an NPC quest are listed in
        ``conditional_connections`` on their parent — the reachability check
        traverses both kinds of edges, since a v0.9 NPC unlock makes the
        sub-zone reachable in-game.
        """
        seen = set()
        frontier = ["crossroads"]
        while frontier:
            loc_id = frontier.pop()
            if loc_id in seen:
                continue
            seen.add(loc_id)
            loc = self.locations[loc_id]
            frontier.extend(loc.get("connections", []))
            frontier.extend(loc.get("conditional_connections", []))
        unreachable = set(self.locations) - seen
        if unreachable:
            raise ValueError(
                f"locations unreachable from the crossroads: {sorted(unreachable)}"
            )

    def _validate_components(self):
        """Check every weapon slot exists and components grant only real stats."""
        for slot in WEAPON_SLOTS:
            if slot not in self.components:
                raise ValueError(f"components.json is missing the '{slot}' slot")
            for cid, comp in self.components[slot].items():
                if comp.get("tier") not in _VALID_TIERS:
                    raise ValueError(
                        f"component '{cid}' has invalid tier {comp.get('tier')!r}"
                    )
                for stat in comp.get("stats", {}):
                    if stat not in _VALID_STATS:
                        raise ValueError(
                            f"component '{cid}' grants unknown stat '{stat}'"
                        )
                proc = comp.get("proc")
                if proc is not None:
                    if proc.get("trigger") not in _VALID_PROC_TRIGGERS:
                        raise ValueError(
                            f"component '{cid}' has invalid proc trigger "
                            f"'{proc.get('trigger')}'"
                        )
                    if proc.get("status") not in status.ALL_EFFECTS:
                        raise ValueError(
                            f"component '{cid}' proc applies unknown status "
                            f"'{proc.get('status')}'"
                        )


def load_content():
    """Load and validate every content file, returning a Content bundle."""
    try:
        marks_raw = _load("marks.json")
    except ContentError:
        # marks.json is optional — v1.51 ships with it, but the engine
        # handles its absence as an empty pool.
        marks_raw = {}
    # Inject each mark's dict key as its 'id' so the engine can refer to
    # it without re-walking the parent dict.
    for mark_id, mark in marks_raw.items():
        mark["id"] = mark_id
    content = Content(
        classes=_load("classes.json"),
        abilities=_load("abilities.json"),
        enemies=_load("enemies.json"),
        locations=_load("locations.json"),
        components=_load("components.json"),
        armor=_load("armor.json"),
        companions=_load("companions.json"),
        accessories=_load("accessories.json"),
        pets=_load("pets.json"),
        hirelings=_load("hirelings.json"),
        npcs=_load("npcs.json"),
        dialogues=_load("dialogues.json"),
        marks=marks_raw,
    )
    content.validate()
    return content

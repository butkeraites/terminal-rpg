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

# The vocabulary of in-fight / in-run conditions that a Conditional Combat
# quest can ask for. Each is implemented (or to be implemented) as a small
# predicate in combat.py. The set is intentionally fixed; quests refer to
# keys, the engine knows what each key means. See docs/QUESTS.md.
VALID_COMPLETION_CONDITIONS = {
    "no_stun_during_fight",
    "no_potions_in_zone",
    "no_hireling_death",
    "companion_landed_kill",
    "first_strike_yours",
    "killed_in_one_round",
    "fled_then_returned",
    "no_damage_taken",
    "status_cleared",
    "critical_killing_blow",
    "kept_full_stamina",
    "used_no_abilities",
    "killed_with_thrown",
    "pet_assisted",
    "killed_while_low_hp",
    "killed_after_dodging",
    "killed_during_stun",
    "no_healing_received",
    "unarmed_kill",
    "named_them_at_death",
}


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
                 marks=None, quests=None):
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
        # Post-1000: the Gravewatch Quest Board's cleanse-gated bounties,
        # previously a Python constant in combat.py, moved to data/quests.json
        # for parity with the rest of the content-driven design. An empty dict
        # is valid; quest_board() shows an empty menu and is otherwise inert.
        self.quests = quests or {}

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
        self._validate_quests()

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

    def _validate_quests(self):
        """Validate every Quest Board entry against the schema in docs/QUESTS.md.

        Required fields: ``name``, ``needed`` (>0), ``reward_gold`` (>=0),
        ``cleanse_required`` (>=0), AND one of ``target_enemy`` or
        ``target_trophy`` (or a ``completion_condition`` for non-kill quests).

        Optional gates: ``min_level``, ``requires_flag(s)``, ``requires_mark(s)``,
        ``requires_class``, ``requires_ending``, ``requires_quest``,
        ``requires_discovery``, ``requires_chronicle_entry``, ``denies_quest``.

        Optional chain / reward / hidden fields per docs/QUESTS.md.

        Every referenced id (enemy, trophy, class, mark, quest, ending,
        discovery, consumable, completion_condition) is checked against
        the actual content. Typos fail at load time.
        """
        required = ("name", "needed", "reward_gold", "cleanse_required")
        # Collect trophy ids from enemies — any string used as `trophy` on
        # an enemy is a valid `target_trophy`.
        trophies_available = {e["trophy"] for e in self.enemies.values()
                              if e.get("trophy")}
        # Collect mark ids if marks are loaded.
        mark_ids = set(self.marks.keys())
        # Collect class ids.
        class_ids = set(self.classes.keys())
        # Collect quest ids (for chain / denies / requires references).
        quest_ids = set(self.quests.keys())

        def _check_int(field, value, qid, minimum=0, allow_none=False):
            if value is None and allow_none:
                return
            if not (isinstance(value, int) and not isinstance(value, bool)
                    and value >= minimum):
                raise ValueError(
                    f"quest '{qid}' has invalid {field!r} value {value!r} "
                    f"(want int >= {minimum})"
                )

        def _check_list_of_str(field, value, qid):
            if not isinstance(value, list) or not all(
                    isinstance(x, str) for x in value):
                raise ValueError(
                    f"quest '{qid}' field {field!r} must be a list of strings, "
                    f"got {value!r}"
                )

        def _check_known_ids(field, ids, valid_set, qid, kind):
            for vid in ids:
                if vid not in valid_set:
                    raise ValueError(
                        f"quest '{qid}' field {field!r} references unknown "
                        f"{kind} '{vid}'"
                    )

        for qid, quest in self.quests.items():
            for field in required:
                if field not in quest:
                    raise ValueError(
                        f"quest '{qid}' is missing required field {field!r}"
                    )
            # Numeric fields
            _check_int("needed", quest["needed"], qid, minimum=1)
            _check_int("reward_gold", quest["reward_gold"], qid, minimum=0)
            _check_int("cleanse_required", quest["cleanse_required"], qid,
                       minimum=0)
            _check_int("min_level", quest.get("min_level"), qid,
                       minimum=1, allow_none=True)

            # Completion target: need at least one of target_enemy /
            # target_trophy / completion_condition / target_composition.
            # Constraints:
            #   - te and tt are mutually exclusive (legacy)
            #   - cc may coexist with te (some quests gate kills behind
            #     a condition — existing pattern, kept intact)
            #   - tcomp is mutually exclusive with EVERYTHING — melody
            #     quests are completed by composition alone
            te = quest.get("target_enemy")
            tt = quest.get("target_trophy")
            cc = quest.get("completion_condition")
            tcomp = quest.get("target_composition")
            if not any((te, tt, cc, tcomp)):
                raise ValueError(
                    f"quest '{qid}' must specify one of 'target_enemy', "
                    f"'target_trophy', 'target_composition', or "
                    f"'completion_condition'"
                )
            if te is not None and tt is not None:
                raise ValueError(
                    f"quest '{qid}' must specify only one of 'target_enemy' "
                    f"or 'target_trophy', not both"
                )
            if tcomp is not None and any((te, tt, cc)):
                raise ValueError(
                    f"quest '{qid}' uses 'target_composition' — cannot "
                    f"combine with 'target_enemy', 'target_trophy', or "
                    f"'completion_condition'"
                )
            if te is not None and te not in self.enemies:
                raise ValueError(
                    f"quest '{qid}' targets unknown enemy '{te}'"
                )
            if tt is not None and tt not in trophies_available:
                raise ValueError(
                    f"quest '{qid}' targets unknown trophy '{tt}' "
                    f"(no enemy drops it)"
                )
            if cc is not None and cc not in VALID_COMPLETION_CONDITIONS:
                raise ValueError(
                    f"quest '{qid}' has unknown completion_condition '{cc}'"
                )
            if tcomp is not None:
                self._validate_target_composition(qid, tcomp)

            # Gate references
            if "requires_flag" in quest:
                if not isinstance(quest["requires_flag"], str):
                    raise ValueError(
                        f"quest '{qid}' field 'requires_flag' must be a string"
                    )
            if "requires_flags" in quest:
                _check_list_of_str("requires_flags",
                                   quest["requires_flags"], qid)
            if "requires_mark" in quest:
                mid = quest["requires_mark"]
                if not isinstance(mid, str):
                    raise ValueError(
                        f"quest '{qid}' field 'requires_mark' must be a string"
                    )
                if mark_ids and mid not in mark_ids:
                    raise ValueError(
                        f"quest '{qid}' requires unknown mark '{mid}'"
                    )
            if "requires_marks" in quest:
                _check_list_of_str("requires_marks",
                                   quest["requires_marks"], qid)
                if mark_ids:
                    _check_known_ids("requires_marks",
                                     quest["requires_marks"],
                                     mark_ids, qid, "mark")
            if "requires_class" in quest:
                _check_list_of_str("requires_class",
                                   quest["requires_class"], qid)
                _check_known_ids("requires_class",
                                 quest["requires_class"],
                                 class_ids, qid, "class")
            if "requires_ending" in quest:
                _check_list_of_str("requires_ending",
                                   quest["requires_ending"], qid)
            if "requires_quest" in quest:
                _check_list_of_str("requires_quest",
                                   quest["requires_quest"], qid)
                _check_known_ids("requires_quest",
                                 quest["requires_quest"],
                                 quest_ids, qid, "quest")
            if "denies_quest" in quest:
                _check_list_of_str("denies_quest",
                                   quest["denies_quest"], qid)
                _check_known_ids("denies_quest",
                                 quest["denies_quest"],
                                 quest_ids, qid, "quest")
            if "requires_discovery" in quest:
                _check_list_of_str("requires_discovery",
                                   quest["requires_discovery"], qid)
            if "requires_chronicle_entry" in quest:
                if not isinstance(quest["requires_chronicle_entry"], dict):
                    raise ValueError(
                        f"quest '{qid}' field 'requires_chronicle_entry' "
                        f"must be a dict"
                    )

            # Chain
            if "chain_next" in quest:
                nxt = quest["chain_next"]
                if not isinstance(nxt, str):
                    raise ValueError(
                        f"quest '{qid}' field 'chain_next' must be a string"
                    )
                if nxt not in quest_ids:
                    raise ValueError(
                        f"quest '{qid}' chains to unknown quest '{nxt}'"
                    )

            # Rewards
            if "reward_consumables" in quest:
                _check_list_of_str("reward_consumables",
                                   quest["reward_consumables"], qid)
            if "reward_marks" in quest:
                _check_list_of_str("reward_marks",
                                   quest["reward_marks"], qid)
                if mark_ids:
                    _check_known_ids("reward_marks",
                                     quest["reward_marks"],
                                     mark_ids, qid, "mark")
            if "reward_chronicle_line" in quest:
                if not isinstance(quest["reward_chronicle_line"], str):
                    raise ValueError(
                        f"quest '{qid}' field 'reward_chronicle_line' "
                        f"must be a string"
                    )
            if "reward_ending_unlock" in quest:
                if not isinstance(quest["reward_ending_unlock"], str):
                    raise ValueError(
                        f"quest '{qid}' field 'reward_ending_unlock' "
                        f"must be a string"
                    )

            # Hidden / trigger
            if "hidden" in quest:
                if not isinstance(quest["hidden"], bool):
                    raise ValueError(
                        f"quest '{qid}' field 'hidden' must be a bool"
                    )
            if "trigger_action" in quest:
                ta = quest["trigger_action"]
                if not isinstance(ta, dict) or "type" not in ta:
                    raise ValueError(
                        f"quest '{qid}' field 'trigger_action' must be a "
                        f"dict with a 'type' key"
                    )

    def _validate_target_composition(self, qid, tcomp):
        """Validate a quest's target_composition field shape.

        Modes:
          exact   — needs a `notes` list, every note parseable
          by_mode — needs a `mode` string ('ROOT_NAME'), min_notes/max_notes,
                    optional octave_range pair of parseable notes
        Both modes share: `voice` in the synth's VOICES, `altar` is a real
        location id, `hints` is a list of strings.
        """
        # Lazy imports so content.py stays light when boss music isn't used
        from . import boss_music_synth as _synth
        from . import composer as _composer

        if not isinstance(tcomp, dict):
            raise ValueError(
                f"quest '{qid}' field 'target_composition' must be a dict"
            )

        tolerance = tcomp.get("tolerance", "exact")
        if tolerance not in ("exact", "by_mode"):
            raise ValueError(
                f"quest '{qid}' target_composition.tolerance must be "
                f"'exact' or 'by_mode', got {tolerance!r}"
            )

        voice = tcomp.get("voice", "voice")
        if voice not in _synth.VOICES:
            raise ValueError(
                f"quest '{qid}' target_composition.voice {voice!r} "
                f"not in synth VOICES"
            )

        altar = tcomp.get("altar")
        if altar is None:
            raise ValueError(
                f"quest '{qid}' target_composition.altar is required"
            )
        if altar not in self.locations:
            raise ValueError(
                f"quest '{qid}' target_composition.altar {altar!r} "
                f"is not a known location id"
            )

        hints = tcomp.get("hints", [])
        if not isinstance(hints, list) or not all(isinstance(h, str)
                                                   for h in hints):
            raise ValueError(
                f"quest '{qid}' target_composition.hints must be a list "
                f"of strings"
            )

        if tolerance == "exact":
            notes = tcomp.get("notes")
            if not isinstance(notes, list) or not notes:
                raise ValueError(
                    f"quest '{qid}' target_composition.notes must be a "
                    f"non-empty list for tolerance='exact'"
                )
            for note in notes:
                try:
                    _synth.note_freq(note)
                except (KeyError, ValueError, IndexError):
                    raise ValueError(
                        f"quest '{qid}' target_composition.notes contains "
                        f"unparseable note {note!r}"
                    ) from None
        else:  # by_mode
            mode = tcomp.get("mode")
            if not isinstance(mode, str):
                raise ValueError(
                    f"quest '{qid}' target_composition.mode is required "
                    f"for tolerance='by_mode'"
                )
            try:
                _composer.parse_mode(mode)
            except ValueError as e:
                raise ValueError(
                    f"quest '{qid}' target_composition.mode invalid: {e}"
                ) from None
            min_n = tcomp.get("min_notes", 1)
            max_n = tcomp.get("max_notes", 8)
            if not isinstance(min_n, int) or not isinstance(max_n, int):
                raise ValueError(
                    f"quest '{qid}' target_composition.min_notes/max_notes "
                    f"must be ints"
                )
            if min_n < 1 or max_n < min_n:
                raise ValueError(
                    f"quest '{qid}' target_composition note count range "
                    f"invalid: min={min_n}, max={max_n}"
                )
            octave_range = tcomp.get("octave_range")
            if octave_range is not None:
                if (not isinstance(octave_range, list)
                        or len(octave_range) != 2):
                    raise ValueError(
                        f"quest '{qid}' target_composition.octave_range "
                        f"must be a 2-element list"
                    )
                for note in octave_range:
                    try:
                        _synth.note_freq(note)
                    except (KeyError, ValueError, IndexError):
                        raise ValueError(
                            f"quest '{qid}' target_composition.octave_range "
                            f"contains unparseable note {note!r}"
                        ) from None

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
    try:
        quests_raw = _load("quests.json")
    except ContentError:
        # quests.json is optional — post-1000 the file ships, but the engine
        # handles its absence as an empty pool (the Quest Board shows
        # *no bounties posted*).
        quests_raw = {}
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
        quests=quests_raw,
    )
    content.validate()
    return content

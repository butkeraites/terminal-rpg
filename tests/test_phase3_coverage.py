"""Phase 3 — content schema, boss_music CLI, player equip paths,
marks edges, chronicle helpers, composer by_mode flow."""
import sys
from unittest.mock import patch

import pytest

from terminalquest import (
    boss_music_synth,
    chronicle,
    composer,
    content as content_module,
    marks,
)
from terminalquest.accessory import Accessory
from terminalquest.armor import Armor
from terminalquest.pet import Pet
from terminalquest.player import Player
from terminalquest.ui import ScriptedIO
from terminalquest.weapon import Weapon


# ── content.py — target_composition schema validation ─────────────────


class _StubContent:
    """Minimal Content-like for validating one quest in isolation."""

    def __init__(self, locations=None):
        self.locations = locations or {"village": {}, "mourncross": {}}


def _validate(stub_content, qid, quest):
    """Run just _validate_target_composition through real Content."""
    # Subclass real Content for the method but inject a small location map
    c = content_module.Content.__new__(content_module.Content)
    c.locations = stub_content.locations
    c._validate_target_composition(qid, quest.get("target_composition"))


class TestTargetCompositionSchema:
    def test_minimal_exact_is_valid(self):
        _validate(_StubContent(), "q", {
            "target_composition": {
                "tolerance": "exact",
                "notes": ["C4"],
                "voice": "bell",
                "altar": "village",
            },
        })

    def test_not_a_dict_rejected(self):
        with pytest.raises(ValueError, match="must be a dict"):
            _validate(_StubContent(), "q", {"target_composition": "no"})

    def test_unknown_tolerance_rejected(self):
        with pytest.raises(ValueError, match="tolerance"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "fanciful",
                "voice": "bell", "altar": "village"}})

    def test_unknown_voice_rejected(self):
        with pytest.raises(ValueError, match="VOICES"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "exact",
                "notes": ["C4"],
                "voice": "nonsense",
                "altar": "village"}})

    def test_missing_altar_rejected(self):
        with pytest.raises(ValueError, match="altar is required"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "exact",
                "notes": ["C4"],
                "voice": "bell"}})

    def test_unknown_altar_rejected(self):
        with pytest.raises(ValueError, match="not a known location"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "exact", "notes": ["C4"],
                "voice": "bell", "altar": "atlantis"}})

    def test_hints_must_be_list_of_str(self):
        with pytest.raises(ValueError, match="hints"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "exact", "notes": ["C4"],
                "voice": "bell", "altar": "village",
                "hints": "not a list"}})

    def test_exact_notes_must_be_non_empty_list(self):
        with pytest.raises(ValueError, match="non-empty list"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "exact", "notes": [],
                "voice": "bell", "altar": "village"}})

    def test_exact_notes_must_be_parseable(self):
        with pytest.raises(ValueError, match="unparseable note"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "exact", "notes": ["C4", "bogus"],
                "voice": "bell", "altar": "village"}})

    def test_by_mode_requires_mode_string(self):
        with pytest.raises(ValueError, match="mode is required"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "by_mode",
                "voice": "bell", "altar": "village"}})

    def test_by_mode_unparseable_mode(self):
        with pytest.raises(ValueError, match="mode invalid"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "by_mode",
                "mode": "X_bogus",
                "voice": "bell", "altar": "village"}})

    def test_by_mode_min_max_must_be_ints(self):
        with pytest.raises(ValueError, match="min_notes/max_notes"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "by_mode",
                "mode": "F_phrygian",
                "min_notes": "two",
                "max_notes": 5,
                "voice": "bell", "altar": "village"}})

    def test_by_mode_inverted_range(self):
        with pytest.raises(ValueError, match="invalid: min"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "by_mode",
                "mode": "F_phrygian",
                "min_notes": 10,
                "max_notes": 4,
                "voice": "bell", "altar": "village"}})

    def test_by_mode_octave_range_must_be_pair(self):
        with pytest.raises(ValueError, match="octave_range"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "by_mode",
                "mode": "F_phrygian",
                "octave_range": ["F3"],   # only one note
                "voice": "bell", "altar": "village"}})

    def test_by_mode_octave_range_notes_parseable(self):
        with pytest.raises(ValueError, match="octave_range.*unparseable"):
            _validate(_StubContent(), "q", {"target_composition": {
                "tolerance": "by_mode",
                "mode": "F_phrygian",
                "octave_range": ["F3", "bogus"],
                "voice": "bell", "altar": "village"}})


# ── content.py — mutual exclusivity of completion paths ───────────────


def test_target_composition_mutually_exclusive_with_target_enemy(content):
    """When a quest sets both target_enemy and target_composition,
    Content.validate() should reject it."""
    content.quests["bogus_double"] = {
        "name": "Bad",
        "needed": 1,
        "reward_gold": 0,
        "cleanse_required": 0,
        "target_enemy": "wolf",
        "target_composition": {
            "tolerance": "exact",
            "notes": ["C4"],
            "voice": "bell",
            "altar": "village",
        },
    }
    with pytest.raises(ValueError, match="cannot combine"):
        content._validate_quests()
    # Clean up so other tests aren't poisoned
    content.quests.pop("bogus_double", None)


# ── boss_music_synth main() CLI ──────────────────────────────────────


class TestBossMusicMain:
    def test_main_renders_missing_to_out(self, tmp_path, capsys):
        with patch.object(sys, "argv",
                          ["boss_music_synth", "--out", str(tmp_path)]), \
             patch.object(boss_music_synth, "render_boss",
                          return_value=[0] * 10):
            boss_music_synth.main()
        out = capsys.readouterr().out
        assert "rendered" in out.lower() or "already cached" in out.lower()

    def test_main_skips_existing(self, tmp_path, capsys):
        # Pre-populate everything except dynamic themes
        for boss_id in boss_music_synth.THEMES:
            if boss_id in boss_music_synth.DYNAMIC_THEMES:
                continue
            (tmp_path / f"{boss_id}.wav").write_bytes(b"x")
        with patch.object(sys, "argv",
                          ["boss_music_synth", "--out", str(tmp_path)]):
            boss_music_synth.main()
        out = capsys.readouterr().out
        assert "already cached" in out

    def test_main_one_boss(self, tmp_path, capsys):
        with patch.object(sys, "argv",
                          ["boss_music_synth", "pallid_stag",
                           "--out", str(tmp_path)]), \
             patch.object(boss_music_synth, "render_boss",
                          return_value=[0] * 10):
            boss_music_synth.main()
        out = capsys.readouterr().out
        assert "rendering pallid_stag" in out

    def test_main_unknown_boss(self, capsys):
        with patch.object(sys, "argv",
                          ["boss_music_synth", "nope_boss"]):
            boss_music_synth.main()
        out = capsys.readouterr().out
        assert "unknown boss" in out


# ── player.py — equip/unequip paths ───────────────────────────────────


class TestPlayerEquipment:
    @pytest.fixture
    def warrior_p(self, content):
        return Player("Hero", "warrior", content.classes["warrior"], content)

    def test_unequip_weapon_when_none(self, warrior_p):
        # Start with no weapon equipped
        warrior_p.equipment.pop("weapon", None)
        assert warrior_p.unequip_weapon() is None

    def test_unequip_armor_returns_previous(self, warrior_p):
        a = Armor("ar", "Coat", {"defense": 2}, dodge_chance=0.05)
        warrior_p.equip_armor(a)
        returned = warrior_p.unequip_armor()
        assert returned is a

    def test_unequip_armor_when_none(self, warrior_p):
        warrior_p.equipment.pop("armor", None)
        assert warrior_p.unequip_armor() is None

    def test_equip_accessory_replaces_in_same_slot(self, warrior_p):
        a1 = Accessory("a1", "Ring1", "ring", {"attack": 1})
        a2 = Accessory("a2", "Ring2", "ring", {"attack": 2})
        warrior_p.equip_accessory(a1)
        warrior_p.equip_accessory(a2)
        assert warrior_p.equipment["ring"] is a2

    def test_unequip_accessory_when_none(self, warrior_p):
        warrior_p.equipment.pop("trinket", None)
        assert warrior_p.unequip_accessory("trinket") is None

    def test_equip_pet_and_unequip(self, warrior_p):
        p = Pet("pp", "Hearth Cat", {"max_hp": 5}, regen_per_round=1)
        warrior_p.equip_pet(p)
        assert warrior_p.equipment["pet"] is p
        returned = warrior_p.unequip_pet()
        assert returned is p

    def test_unequip_pet_when_none(self, warrior_p):
        warrior_p.equipment.pop("pet", None)
        assert warrior_p.unequip_pet() is None

    def test_to_dict_roundtrip_with_full_equipment(self, warrior_p, content):
        weapon = Weapon("Sword", components={}, stats={"attack": 2})
        armor_p = Armor("ar", "Coat", {"defense": 2}, dodge_chance=0.05)
        trinket = Accessory("t", "T", "trinket", {"attack": 1})
        ring = Accessory("r", "R", "ring", {"defense": 1})
        peet = Pet("p", "P", {"max_hp": 5}, regen_per_round=1)
        warrior_p.equipment["weapon"] = weapon
        warrior_p.equip_armor(armor_p)
        warrior_p.equip_accessory(trinket)
        warrior_p.equip_accessory(ring)
        warrior_p.equip_pet(peet)
        d = warrior_p.to_dict()
        assert "weapon" in d["equipment"]
        assert "armor" in d["equipment"]
        assert "trinket" in d["equipment"]
        assert "ring" in d["equipment"]
        assert "pet" in d["equipment"]


# ── marks.py — sidecar edge paths ──────────────────────────────────────


class TestMarksEdges:
    def test_load_sidecar_oserror_returns_empty(self, tmp_path):
        result = marks.load_sidecar(tmp_path, "missing_run_id")
        assert result == []

    def test_load_sidecar_handles_bad_json(self, tmp_path):
        path = marks._sidecar_path(tmp_path, "run1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not valid json")
        assert marks.load_sidecar(tmp_path, "run1") == []

    def test_write_sidecar_swallows_oserror(self, tmp_path):
        with patch("os.replace", side_effect=OSError("disk")):
            marks.write_sidecar(tmp_path, "run1", ["mark_a"])  # must not raise

    def test_describe_with_unknown_mark_falls_back(self):
        player = type("P", (), {"marks": ["totally_not_a_real_mark"]})()
        out = marks.describe(player, {"some_other_mark": {"id": "x",
                                                           "lines": ["x"]}})
        assert any("unknown mark" in line for line in out)

    def test_describe_empty_pool_returns_empty(self):
        player = type("P", (), {"marks": ["x"]})()
        assert marks.describe(player, {}) == []

    def test_roll_at_no_pool_returns_none(self, content):
        state = type("S", (), {
            "content": type("C", (), {"marks": None})(),
            "rng": type("R", (), {"random": lambda self: 0.5})(),
        })()
        assert marks.roll_at(state, "zone_arrival") is None


# ── chronicle.py — small edge paths ────────────────────────────────────


class TestChronicleEdges:
    def test_load_handles_missing_file(self, tmp_path):
        assert chronicle.load(tmp_path) == []

    def test_load_handles_corrupt_json(self, tmp_path):
        chronicle._path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        chronicle._path(tmp_path).write_text("{not json")
        assert chronicle.load(tmp_path) == []

    def test_purified_after_mark_purified(self, tmp_path):
        chronicle.mark_purified(tmp_path)
        assert chronicle.purified(tmp_path) is True

    def test_purified_false_by_default(self, tmp_path):
        assert chronicle.purified(tmp_path) is False


# ── composer.py — the two missing branches in compose() ───────────────


class TestComposerByMode:
    def test_by_mode_compose_success(self):
        """Cover composer.py lines 115 (check_by_mode) and 137 (max_notes)."""
        io = ScriptedIO(["F3 Gb3 Ab3 Bb3", "commit"])
        state = type("S", (), {"io": io,
                               "audio": type("A", (), {
                                   "play_composition": lambda *_a, **_k: None})()})()
        quest = {
            "target_composition": {
                "tolerance": "by_mode",
                "mode": "F_phrygian",
                "min_notes": 3,
                "max_notes": 6,
                "voice": "voice",
                "hints": [],
            },
        }
        assert composer.compose(state, quest) is True

    def test_by_mode_compose_failure_then_quit(self):
        io = ScriptedIO(["E4 F4 G4 A4", "commit", "quit"])  # all wrong for F Phrygian
        state = type("S", (), {"io": io,
                               "audio": type("A", (), {
                                   "play_composition": lambda *_a, **_k: None})()})()
        quest = {"target_composition": {
            "tolerance": "by_mode",
            "mode": "F_phrygian",
            "min_notes": 3,
            "max_notes": 4,
            "voice": "voice", "hints": []}}
        assert composer.compose(state, quest) is False

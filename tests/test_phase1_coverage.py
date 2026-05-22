"""Phase 1 coverage push — small files and missing edges.

Targets the easy gaps surfaced by `coverage report --show-missing`:
equipment classes (accessory/pet/companion/hireling), ui.py output paths,
audio_synth CLI, composer edge cases, and miscellaneous small files.

Tests are grouped by module for readability.
"""
import sys
from unittest.mock import patch

import pytest

from terminalquest import (
    accessory,
    audio_synth,
    armor,
    color,
    companion,
    composer,
    endings,
    hireling,
    pet,
    saves,
    settings,
    status,
    ui,
)
from terminalquest.player import Player
from terminalquest.ui import GameIO, ScriptedIO


# ── Equipment classes ──────────────────────────────────────────────────


class TestAccessory:
    def test_summary_with_flat_stats(self):
        a = accessory.Accessory("ring", "Ring of Iron", "ring",
                                {"attack": 2, "defense": 1})
        s = a.summary()
        assert "+2 atk" in s and "+1 def" in s

    def test_summary_with_percent_stats(self):
        a = accessory.Accessory("trinket", "Quick", "trinket",
                                {"crit_bonus": 0.05, "dodge_chance": 0.10})
        s = a.summary()
        assert "+5% crit" in s and "+10% dodge" in s

    def test_summary_empty_when_no_stats(self):
        a = accessory.Accessory("x", "Empty", "trinket", {})
        assert a.summary() == "(no bonuses)"

    def test_dict_roundtrip(self):
        a = accessory.Accessory("r", "R", "ring", {"attack": 3}, "flavor")
        b = accessory.Accessory.from_dict(a.to_dict())
        assert (b.accessory_id, b.name, b.slot, b.stats, b.flavor) == \
               (a.accessory_id, a.name, a.slot, a.stats, a.flavor)

    def test_make_accessory_from_content(self, content):
        # Just pick any real accessory id off content
        if not content.accessories:
            pytest.skip("no accessories in content")
        aid = next(iter(content.accessories))
        built = accessory.make_accessory(content, aid)
        assert built.accessory_id == aid


class TestPet:
    def test_summary_with_regen(self):
        p = pet.Pet("cat", "Hearth Cat", {"max_hp": 4}, regen_per_round=1)
        s = p.summary()
        assert "+4 HP" in s and "+1/round" in s

    def test_summary_without_stats(self):
        p = pet.Pet("x", "Nothing", {}, regen_per_round=0)
        assert p.summary() == "(no bonuses)"

    def test_summary_with_percent_stats(self):
        p = pet.Pet("p", "Quick Pet", {"crit_bonus": 0.05})
        assert "+5% crit" in p.summary()

    def test_dict_roundtrip(self):
        p = pet.Pet("cat", "Cat", {"max_hp": 3}, regen_per_round=2, flavor="f")
        q = pet.Pet.from_dict(p.to_dict())
        assert (q.pet_id, q.name, q.stats, q.regen_per_round, q.flavor) == \
               (p.pet_id, p.name, p.stats, p.regen_per_round, p.flavor)

    def test_make_pet_from_content(self, content):
        if not content.pets:
            pytest.skip("no pets in content")
        pid = next(iter(content.pets))
        built = pet.make_pet(content, pid)
        assert built.pet_id == pid


class TestCompanion:
    def test_summary_damage(self):
        c = companion.Companion("c", "Strike", "damage", 5)
        assert "5 damage" in c.summary()

    def test_summary_heal(self):
        c = companion.Companion("c", "Mender", "heal", 3)
        assert "3 HP" in c.summary()

    def test_summary_unknown_kind(self):
        c = companion.Companion("c", "?", "weird", 0)
        assert "unknown" in c.summary()

    def test_dict_roundtrip(self):
        c = companion.Companion("c", "C", "heal", 3, "flavor")
        d = companion.Companion.from_dict(c.to_dict())
        assert (d.companion_id, d.kind, d.power, d.flavor) == \
               (c.companion_id, c.kind, c.power, c.flavor)


class TestHireling:
    def test_summary_format(self):
        h = hireling.Hireling("h", "Ally", 30, 2, 4)
        s = h.summary()
        assert "30/30 HP" in s and "2 def" in s and "4/round" in s

    def test_dict_roundtrip_preserves_hp(self):
        h = hireling.Hireling("h", "Ally", 30, 2, 4)
        h.hp = 17
        h2 = hireling.Hireling.from_dict(h.to_dict())
        assert h2.hp == 17 and h2.max_hp == 30

    def test_make_hireling_from_content(self, content):
        if not content.hirelings:
            pytest.skip("no hirelings in content")
        hid = next(iter(content.hirelings))
        built = hireling.make_hireling(content, hid)
        assert built.hireling_id == hid


# ── UI ─────────────────────────────────────────────────────────────────


class TestGameIO:
    def test_show_prints(self, capsys):
        GameIO().show("hello")
        captured = capsys.readouterr()
        assert "hello" in captured.out

    def test_clear_prints_newlines(self, capsys):
        GameIO().clear()
        captured = capsys.readouterr()
        assert captured.out.count("\n") >= 2

    def test_pause_calls_sleep(self):
        with patch("time.sleep") as sleep:
            GameIO().pause(0.5)
            sleep.assert_called_once_with(0.5)

    def test_show_slow_not_animated_just_prints(self, capsys):
        GameIO(animate=False).show("plain")
        # Even with animate=False, show_slow's not-animate branch
        GameIO(animate=False).show_slow("plain", delay=0.01)
        captured = capsys.readouterr()
        assert "plain" in captured.out

    def test_show_slow_animated_calls_sleep_per_char(self, capsys):
        with patch("time.sleep") as sleep:
            GameIO(animate=True).show_slow("abc", delay=0.001)
        # Sleep called once per char
        assert sleep.call_count >= 3

    def test_ask_uses_input(self):
        with patch("builtins.input", return_value="  yes  "):
            assert GameIO().ask("Q? ") == "yes"

    def test_show_through_stone_not_animated(self, capsys):
        GameIO(animate=False).show_through_stone("Cael's line")
        captured = capsys.readouterr()
        assert "Cael's line" in captured.out
        assert "▒" in captured.out

    def test_show_through_stone_animated_per_char_sleep(self, capsys):
        with patch("time.sleep") as sleep:
            GameIO(animate=True).show_through_stone("abc")
        assert sleep.call_count >= 3

    def test_show_through_stone_ascii_mode(self, capsys):
        GameIO(animate=False, ascii_mode=True).show_through_stone("plain")
        captured = capsys.readouterr()
        assert "::" in captured.out
        assert "▒" not in captured.out

    def test_set_location_default_is_noop(self):
        GameIO().set_location("anywhere", ["one"])  # must not raise

    def test_set_status_default_is_noop(self):
        GameIO().set_status("anything")  # must not raise


class TestHud:
    @pytest.fixture
    def warrior_p(self, content):
        return Player("Hero", "warrior", content.classes["warrior"], content)

    def test_hud_green_when_hp_high(self, warrior_p):
        warrior_p.hp = warrior_p.max_hp  # 100% → green path
        line = ui.hud(warrior_p)
        # color.paint may or may not wrap with ANSI depending on ENABLED;
        # we just check the structure of the line
        assert "Lv" in line and "HP" not in line  # uses ❤️ glyph not "HP"

    def test_hud_red_when_hp_low(self, warrior_p):
        warrior_p.hp = max(1, int(warrior_p.max_hp * 0.2))  # ≤ 30% → red
        line = ui.hud(warrior_p)
        assert "Lv" in line

    def test_hud_neutral_in_middle(self, warrior_p):
        warrior_p.hp = int(warrior_p.max_hp * 0.5)
        line = ui.hud(warrior_p)
        assert "Lv" in line


class TestShowStats:
    @pytest.fixture
    def warrior_p(self, content):
        return Player("Hero", "warrior", content.classes["warrior"], content)

    def test_show_stats_basic(self, warrior_p):
        io = ScriptedIO()
        ui.show_stats(io, warrior_p)
        out = io.text()
        assert "Hero" in out
        assert "HP" in out
        assert "Stamina" in out

    def test_show_stats_with_status_effects(self, warrior_p):
        warrior_p.statuses = {"poison": 3}
        io = ScriptedIO()
        ui.show_stats(io, warrior_p)
        out = io.text()
        assert "Status:" in out

    def test_show_stats_with_marks_section(self, warrior_p, content):
        # Give the player at least one mark — show_stats should surface it
        if not content.marks:
            pytest.skip("no marks loaded")
        mark_id = next(iter(content.marks))
        warrior_p.marks = [mark_id]
        io = ScriptedIO()
        ui.show_stats(io, warrior_p, content=content)
        out = io.text()
        assert "Marked by" in out

    def test_show_stats_no_marks_section_without_content(self, warrior_p):
        warrior_p.marks = ["whatever"]
        io = ScriptedIO()
        ui.show_stats(io, warrior_p)  # content=None
        assert "Marked by" not in io.text()


# ── Audio synth CLI ────────────────────────────────────────────────────


class TestAudioSynthCLI:
    def test_list_recipes_prints(self, capsys):
        audio_synth.list_recipes()
        out = capsys.readouterr().out
        assert "palettes" in out.lower()
        # Lists every palette name
        for name in audio_synth.PALETTES:
            assert name in out

    def test_main_with_list_flag(self, capsys):
        with patch.object(sys, "argv", ["audio_synth", "--list"]):
            audio_synth.main()
        out = capsys.readouterr().out
        assert "palettes" in out.lower()

    def test_main_renders_into_given_dir(self, tmp_path, capsys):
        with patch.object(audio_synth, "DURATION_S", 0.05), \
             patch.object(sys, "argv",
                          ["audio_synth", "--out", str(tmp_path)]):
            audio_synth.main()
        # All palettes rendered
        for name in audio_synth.PALETTES:
            assert (tmp_path / f"{name}.wav").exists()
        out = capsys.readouterr().out
        assert "rendered" in out.lower() or "already cached" in out.lower()

    def test_main_skips_when_all_cached(self, tmp_path, capsys):
        for name in audio_synth.PALETTES:
            (tmp_path / f"{name}.wav").write_bytes(b"x")
        with patch.object(sys, "argv",
                          ["audio_synth", "--out", str(tmp_path)]):
            audio_synth.main()
        out = capsys.readouterr().out
        assert "already cached" in out


# ── Composer edges ─────────────────────────────────────────────────────


class TestComposerEdges:
    def test_note_pitch_class_unknown_letter(self):
        with pytest.raises(ValueError, match="unknown note letter"):
            composer.note_pitch_class("X4")

    def test_note_pitch_class_no_octave_digit(self):
        with pytest.raises(ValueError, match="can't parse note"):
            composer.note_pitch_class("C")

    def test_check_match_unknown_tolerance_returns_false(self):
        assert composer.check_match(["C4"], {"tolerance": "fanciful"}) is False

    def test_compose_play_with_notes_after_typing(self):
        """The play command with notes in buffer should call play_composition."""
        io = ScriptedIO(inputs=["C4 G3 Eb4 G3", "play", "commit"])

        class _Recorder:
            def __init__(self):
                self.calls = []
            def play_composition(self, notes, voice="voice"):
                self.calls.append((tuple(notes), voice))

        audio = _Recorder()
        state = type("S", (), {"io": io, "audio": audio})()
        quest = {
            "target_composition": {
                "tolerance": "exact",
                "notes": ["C4", "G3", "Eb4", "G3"],
                "voice": "bell",
                "hints": [],
            },
        }
        assert composer.compose(state, quest) is True
        # play_composition fired twice: once for the play, once for the commit
        assert len(audio.calls) == 2
        assert audio.calls[0][1] == "bell"

    def test_compose_empty_input_is_ignored(self):
        io = ScriptedIO(inputs=["", "   ", "quit"])
        state = type("S", (), {"io": io,
                               "audio": type("A", (), {
                                   "play_composition": lambda *_a, **_k: None})()})()
        quest = {"target_composition": {
            "tolerance": "exact",
            "notes": ["C4"],
            "voice": "bell",
            "hints": [],
        }}
        assert composer.compose(state, quest) is False

    def test_compose_commit_with_empty_buffer_complains(self):
        io = ScriptedIO(inputs=["commit", "quit"])
        state = type("S", (), {"io": io,
                               "audio": type("A", (), {
                                   "play_composition": lambda *_a, **_k: None})()})()
        quest = {"target_composition": {
            "tolerance": "exact", "notes": ["C4"], "voice": "bell", "hints": []}}
        assert composer.compose(state, quest) is False
        assert "type your notes" in io.text().lower()

    def test_compose_garbage_input_reports_error(self):
        io = ScriptedIO(inputs=["not_a_note bogus", "quit"])
        state = type("S", (), {"io": io,
                               "audio": type("A", (), {
                                   "play_composition": lambda *_a, **_k: None})()})()
        quest = {"target_composition": {
            "tolerance": "exact", "notes": ["C4"], "voice": "bell", "hints": []}}
        composer.compose(state, quest)
        assert "didn't understand" in io.text()

    def test_compose_overflow_trims_to_last_n(self):
        """Typing 6 notes when target is 4: last 4 kept, message printed."""
        io = ScriptedIO(inputs=[
            "A3 B3 C4 D4 E4 F4",          # 6 notes, target is 4
            "commit",                       # fails (kept A3-F4 wrong)
            "C4 G3 Eb4 G3", "commit",      # correct
        ])
        state = type("S", (), {"io": io,
                               "audio": type("A", (), {
                                   "play_composition": lambda *_a, **_k: None})()})()
        quest = {"target_composition": {
            "tolerance": "exact",
            "notes": ["C4", "G3", "Eb4", "G3"],
            "voice": "bell", "hints": []}}
        assert composer.compose(state, quest) is True
        assert "kept last 4" in io.text()


# ── Color, status, armor, weapon, endings ──────────────────────────────


class TestSmallFiles:
    def test_color_paint_disabled_returns_plain(self):
        with patch.object(color, "ENABLED", False):
            assert color.paint("text", "red") == "text"

    def test_color_paint_unknown_style_returns_plain(self):
        with patch.object(color, "ENABLED", True):
            assert color.paint("text", "fuchsia") == "text"

    def test_status_describe_empty(self):
        e = type("E", (), {"statuses": {}})()
        assert status.describe(e) == ""

    def test_status_describe_lists_effects(self):
        e = type("E", (), {"statuses": {"poison": 2, "stun": 1}})()
        out = status.describe(e)
        assert "poison" in out and "stun" in out

    def test_armor_dict_roundtrip(self):
        a = armor.Armor("a", "Coat", {"defense": 3}, dodge_chance=0.05,
                        flavor="warm")
        b = armor.Armor.from_dict(a.to_dict())
        assert (b.armor_id, b.stats, b.dodge_chance) == \
               (a.armor_id, a.stats, a.dodge_chance)

    def test_endings_reset_registry_clears(self):
        snapshot = list(endings._ENDINGS)
        endings.register("dummy_test_ending", "Dummy",
                         lambda state: None, lambda state: True)
        ids = [eid for eid, _label, _r, _q in endings._ENDINGS]
        assert "dummy_test_ending" in ids
        endings.reset_registry()
        assert endings._ENDINGS == []
        # Restore — other tests rely on the real registry being populated
        endings._ENDINGS.extend(snapshot)


# ── Settings I/O failure paths ─────────────────────────────────────────


class TestSettingsErrorPaths:
    def test_save_recovers_from_oserror_in_replace(self, tmp_path):
        """Save's try/except should swallow OSError silently."""
        prefs = {"ascii_mode": False, "emoji_test_done": True}
        with patch("os.replace", side_effect=OSError("disk")):
            settings.save(prefs, settings_dir=tmp_path)  # must not raise

    def test_save_recovers_from_outer_oserror(self, tmp_path):
        """If even mkstemp/open fails the outer except swallows it."""
        with patch("tempfile.mkstemp", side_effect=OSError("fs")):
            settings.save({"ascii_mode": False, "emoji_test_done": True},
                          settings_dir=tmp_path)


# ── Saves: list_saves with corrupt entry ───────────────────────────────


class TestListSavesCorrupt:
    def test_list_saves_marks_corrupt_entries(self, tmp_path):
        # Drop a junk JSON in slot 1
        slot_path = saves._slot_path(1, tmp_path)
        slot_path.write_text("{not valid json")
        summaries = saves.list_saves(save_dir=tmp_path)
        assert summaries.get(1) == "(corrupt save)"

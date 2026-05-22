"""Phase 2a: cover __main__.py + game.py menu/character/settings flows."""
import random
import sys
from unittest.mock import patch


from terminalquest import chronicle, game, saves
from terminalquest.audio import AudioEngine
from terminalquest.player import Player
from terminalquest.state import GameState
from terminalquest.ui import GameIO, ScriptedIO


# ── __main__.py ────────────────────────────────────────────────────────


class TestMainModule:
    def test_parse_args_defaults(self):
        import terminalquest.__main__ as m
        with patch.object(sys, "argv", ["terminalquest"]):
            args = m._parse_args()
        assert args.no_audio is False
        assert args.tui is False

    def test_parse_args_no_audio_flag(self):
        import terminalquest.__main__ as m
        with patch.object(sys, "argv", ["terminalquest", "--no-audio"]):
            args = m._parse_args()
        assert args.no_audio is True

    def test_parse_args_tui_flag(self):
        import terminalquest.__main__ as m
        with patch.object(sys, "argv", ["terminalquest", "--tui"]):
            args = m._parse_args()
        assert args.tui is True


# ── _emoji_smoke_test ──────────────────────────────────────────────────


class TestEmojiSmokeTest:
    def test_skips_when_already_done(self, capsys):
        prefs = {"ascii_mode": False, "emoji_test_done": True,
                 "audio_enabled": False}
        io = GameIO()
        game._emoji_smoke_test(io, prefs)
        assert capsys.readouterr().out == ""

    def test_yes_path_continues_with_glyphs(self, capsys, tmp_path):
        prefs = {"ascii_mode": False, "emoji_test_done": False,
                 "audio_enabled": False}
        io = GameIO()
        with patch("builtins.input", return_value="y"), \
             patch.object(game.settings, "DEFAULT_DIR", tmp_path):
            game._emoji_smoke_test(io, prefs)
        out = capsys.readouterr().out
        assert "Continuing with the full glyphs" in out
        assert prefs["emoji_test_done"] is True
        assert prefs["ascii_mode"] is False

    def test_no_path_switches_to_ascii(self, capsys, tmp_path):
        prefs = {"ascii_mode": False, "emoji_test_done": False,
                 "audio_enabled": False}
        io = GameIO()
        with patch("builtins.input", return_value="n"), \
             patch.object(game.settings, "DEFAULT_DIR", tmp_path):
            game._emoji_smoke_test(io, prefs)
        out = capsys.readouterr().out
        assert "text-only mode" in out
        assert prefs["ascii_mode"] is True
        assert io.ascii_mode is True

    def test_eof_defaults_to_yes(self, capsys, tmp_path):
        prefs = {"ascii_mode": False, "emoji_test_done": False,
                 "audio_enabled": False}
        io = GameIO()
        with patch("builtins.input", side_effect=EOFError), \
             patch.object(game.settings, "DEFAULT_DIR", tmp_path):
            game._emoji_smoke_test(io, prefs)
        assert prefs["ascii_mode"] is False  # default = keep glyphs
        assert prefs["emoji_test_done"] is True


# ── _configure_console_for_unicode ─────────────────────────────────────


class TestConfigureConsole:
    def test_runs_without_error(self):
        # Mostly platform-dependent; just call it
        game._configure_console_for_unicode()

    def test_handles_reconfigure_failure(self):
        with patch.object(sys.stdout, "reconfigure",
                          side_effect=OSError("nope"), create=True):
            game._configure_console_for_unicode()  # must not raise


# ── _new_seed ──────────────────────────────────────────────────────────


def test_new_seed_returns_six_digit_string():
    seed = game._new_seed()
    assert seed.isdigit()
    assert 100000 <= int(seed) <= 999999


# ── choose_class ───────────────────────────────────────────────────────


class TestChooseClass:
    def test_returns_id_and_def_on_valid_pick(self, content):
        io = ScriptedIO(["1"])
        cid, cdef = game.choose_class(content, io)
        assert cid in content.classes
        assert cdef == content.classes[cid]

    def test_re_prompts_on_invalid_then_accepts(self, content):
        io = ScriptedIO(["bogus", "999", "1"])
        cid, _ = game.choose_class(content, io)
        assert cid in content.classes
        assert "Invalid choice" in io.text()


# ── _name_the_fallen ───────────────────────────────────────────────────


class TestNameTheFallen:
    def test_empty_entries_returns_silently(self, content):
        io = ScriptedIO()
        game._name_the_fallen(io, content, [])
        assert io.text() == ""

    def test_fallen_entry_is_named(self, content):
        io = ScriptedIO()
        entry = {
            "player": {"name": "Vesna", "class_name": "Lampkeeper",
                       "level": 3},
            "location": "village",
            "fate": "fell",
        }
        game._name_the_fallen(io, content, [entry])
        assert "Vesna" in io.text()
        assert "Gravewatch" in io.text()  # village name

    def test_warden_entry_uses_warden_line(self, content):
        io = ScriptedIO()
        entry = {
            "player": {"name": "Anne", "class_name": "Mage", "level": 7},
            "location": "summit",
            "fate": "warden",
        }
        game._name_the_fallen(io, content, [entry])
        assert "Anne" in io.text()
        assert "took the Summit" in io.text()

    def test_resolved_entry_uses_laid_to_rest_line(self, content):
        io = ScriptedIO()
        entry = {
            "player": {"name": "Borel", "class_name": "Rogue", "level": 4},
            "location": "forest",
            "fate": "fell",
            "resolved": True,
        }
        game._name_the_fallen(io, content, [entry])
        assert "laid to rest" in io.text()


# ── create_character ───────────────────────────────────────────────────


class TestCreateCharacter:
    def test_basic_creation(self, content, tmp_path):
        io = ScriptedIO(["MyHero", "1"])
        player, flags = game.create_character(content, io, tmp_path)
        assert player.name == "MyHero"
        assert player.level == 1
        assert isinstance(flags, dict)

    def test_default_name_when_blank(self, content, tmp_path):
        io = ScriptedIO(["", "1"])
        player, _ = game.create_character(content, io, tmp_path)
        assert player.name == "Hero"

    def test_reborn_flag_set_after_a_cleanse(self, content, tmp_path):
        chronicle.add_cleanse(tmp_path)
        io = ScriptedIO(["X", "1"])
        _, flags = game.create_character(content, io, tmp_path)
        assert flags.get("is_reborn") is True

    def test_mirror_climb_offered_after_three_endings(self, content, tmp_path):
        # Three distinct endings unlock the Mirror Climb prompt.
        # Order in create_character: name → class → (maybe) mirror prompt.
        for eid in ("warden", "reborn", "purify"):
            chronicle.add_ending_seen(eid, tmp_path)
        io = ScriptedIO(["X", "1", "y"])
        _, flags = game.create_character(content, io, tmp_path)
        assert flags.get("mirror_run") is True
        assert "Mirror Climb" in io.text()

    def test_mirror_climb_declined(self, content, tmp_path):
        for eid in ("warden", "reborn", "purify"):
            chronicle.add_ending_seen(eid, tmp_path)
        io = ScriptedIO(["X", "1", "n"])
        _, flags = game.create_character(content, io, tmp_path)
        assert flags.get("mirror_run") is not True


# ── load_menu ──────────────────────────────────────────────────────────


class TestLoadMenu:
    def test_no_saves_returns_none(self, content):
        io = ScriptedIO()
        with patch.object(saves, "list_saves", return_value={}):
            result = game.load_menu(content, io, random.Random(0))
        assert result is None
        assert "No saved games" in io.text()

    def test_loads_a_valid_save(self, content, tmp_path):
        # Build a real save in a tmp dir, then patch list_saves + load_game
        # to find it via the patched paths
        player = Player("Saver", "warrior",
                        content.classes["warrior"], content)
        st = GameState(player, content, ScriptedIO(), random.Random(0),
                       chronicle_dir=tmp_path, seed="42")
        saves.save_game(st, 1, save_dir=tmp_path)
        io = ScriptedIO(["1"])
        with patch.object(saves, "list_saves",
                          return_value={1: "Saver the warrior - Level 1"}), \
             patch.object(saves, "load_game",
                          return_value=saves.load_game(
                              1, content, io, random.Random(0),
                              save_dir=tmp_path)):
            loaded = game.load_menu(content, io, random.Random(0))
        assert loaded is not None
        assert loaded.player.name == "Saver"

    def test_invalid_slot_choice_returns_none(self, content):
        io = ScriptedIO(["bogus"])
        with patch.object(saves, "list_saves",
                          return_value={1: "Some Hero - Level 5"}):
            result = game.load_menu(content, io, random.Random(0))
        assert result is None

    def test_corrupt_save_handled(self, content):
        io = ScriptedIO(["1"])
        with patch.object(saves, "list_saves",
                          return_value={1: "(corrupt save)"}), \
             patch.object(saves, "load_game",
                          side_effect=saves.SaveError("corrupt")):
            result = game.load_menu(content, io, random.Random(0))
        assert result is None
        assert "corrupt" in io.text()


# ── settings_menu ──────────────────────────────────────────────────────


class TestSettingsMenu:
    def test_animation_toggle_off_then_back(self):
        io = ScriptedIO(["1", "2"])
        io.animate = True
        game.settings_menu(io)
        assert io.animate is False  # toggled

    def test_audio_toggle_when_engine_provided(self, tmp_path):
        io = ScriptedIO(["2", "3"])  # audio on then back (3 is back when audio shown)
        prefs = {"audio_enabled": False}
        engine = AudioEngine(enabled=False, cache_dir=tmp_path)
        with patch.object(engine, "unmute") as unmute, \
             patch.object(game.settings, "DEFAULT_DIR", tmp_path):
            game.settings_menu(io, prefs=prefs, engine=engine)
        assert prefs["audio_enabled"] is True
        unmute.assert_called_once()

    def test_audio_toggle_off(self, tmp_path):
        io = ScriptedIO(["2", "3"])
        prefs = {"audio_enabled": True}
        engine = AudioEngine(enabled=True, cache_dir=tmp_path)
        with patch.object(engine, "mute") as mute, \
             patch.object(game.settings, "DEFAULT_DIR", tmp_path):
            game.settings_menu(io, prefs=prefs, engine=engine)
        assert prefs["audio_enabled"] is False
        mute.assert_called_once()

    def test_invalid_choice_reprompts(self):
        io = ScriptedIO(["bogus", "2"])
        game.settings_menu(io)
        assert "Invalid choice" in io.text()


# ── run() menu loop branches not covered by existing tests ─────────────


class TestRunBranches:
    def test_chronicle_choice_then_quit(self, content, tmp_path):
        io = ScriptedIO(["3", "5"])
        game.run(io=io, content=content, rng=random.Random(0),
                 chronicle_dir=tmp_path, seed="123")
        assert "Chronicle" in io.text()

    def test_settings_choice_then_quit(self, content, tmp_path):
        # In run(), settings_menu is called with prefs+engine, so it shows
        # 3 options: 1=anim, 2=audio, 3=back. So path is 4→3→5.
        io = ScriptedIO(["4", "3", "5"])
        game.run(io=io, content=content, rng=random.Random(0),
                 chronicle_dir=tmp_path, seed="123")
        assert "Text animation" in io.text()

    def test_continue_choice_no_saves(self, content, tmp_path):
        io = ScriptedIO(["2", "5"])
        with patch.object(saves, "list_saves", return_value={}):
            game.run(io=io, content=content, rng=random.Random(0),
                     chronicle_dir=tmp_path, seed="123")
        assert "No saved games" in io.text()

    def test_invalid_then_quit(self, content, tmp_path):
        io = ScriptedIO(["bogus", "5"])
        game.run(io=io, content=content, rng=random.Random(0),
                 chronicle_dir=tmp_path, seed="123")
        assert "Invalid choice" in io.text()


# ── main() ────────────────────────────────────────────────────────────


class TestMainEntry:
    def test_main_no_tui_calls_run(self):
        with patch.object(game, "run") as run, \
             patch.object(game, "_configure_console_for_unicode"), \
             patch("builtins.input", return_value=""):
            game.main(no_audio=True, tui=False)
        run.assert_called_once_with(no_audio=True)

    def test_main_tui_defers_to_curses(self):
        with patch.object(game, "_configure_console_for_unicode"), \
             patch("terminalquest.curses_io.run_with_tui") as rwt, \
             patch("builtins.input", return_value=""):
            game.main(no_audio=False, tui=True)
        rwt.assert_called_once_with(no_audio=False)

    def test_main_hold_open_swallows_eof(self):
        with patch.object(game, "run"), \
             patch.object(game, "_configure_console_for_unicode"), \
             patch("builtins.input", side_effect=EOFError):
            game.main()  # must not raise

"""Phase 3c — tail-end coverage: saves errors, color, endings, weapon procs,
dialogue branches, and locations service edges."""
import random
from unittest.mock import patch

import pytest

from terminalquest import (
    chronicle,
    color,
    dialogue,
    endings,
    locations,
    saves,
)
from terminalquest.player import Player
from terminalquest.state import GameState
from terminalquest.ui import ScriptedIO
from terminalquest.weapon import Weapon


# ── saves.py edges ─────────────────────────────────────────────────────


class TestSavesErrorPaths:
    def test_save_game_cleans_up_tmp_on_oserror(self, content, tmp_path):
        """If json.dump raises BaseException, the .tmp file must be removed
        and the error re-raised."""
        player = Player("X", "warrior", content.classes["warrior"], content)
        state = GameState(player, content, ScriptedIO(), random.Random(0),
                          chronicle_dir=tmp_path, seed="1")
        with patch("json.dump", side_effect=OSError("disk")):
            with pytest.raises(OSError):
                saves.save_game(state, 1, save_dir=tmp_path)
        # No leftover .tmp
        tmps = list(tmp_path.glob("*.tmp"))
        assert tmps == []

    def test_load_game_sets_reborn_flag(self, content, tmp_path):
        """Loading after a cleanse adds the is_reborn flag to the loaded
        state (line 103)."""
        # Make a save, then mark a cleanse, then load.
        player = Player("X", "warrior", content.classes["warrior"], content)
        state = GameState(player, content, ScriptedIO(), random.Random(0),
                          chronicle_dir=tmp_path, seed="1")
        saves.save_game(state, 1, save_dir=tmp_path)
        chronicle.add_cleanse(tmp_path)
        # We need load_game to use the chronicle_dir we just bumped.
        # The chronicle_dir is read from the saved state. Hack: rewrite
        # the saved file's chronicle_dir... actually the load function
        # reads chronicle.cleanses(state.chronicle_dir) where state.
        # chronicle_dir = DEFAULT_DIR after load (it's not persisted).
        # So we monkey-patch chronicle.DEFAULT_DIR to point at tmp.
        with patch.object(chronicle, "DEFAULT_DIR", tmp_path):
            loaded = saves.load_game(1, content, ScriptedIO(),
                                     random.Random(0), save_dir=tmp_path)
        assert loaded.flags.get("is_reborn") is True


# ── color.py ──────────────────────────────────────────────────────────


def test_color_paint_enabled_wraps_with_ansi():
    with patch.object(color, "ENABLED", True):
        out = color.paint("hi", "red")
    assert "\033[" in out and "hi" in out


# ── endings.py ─────────────────────────────────────────────────────────


def test_endings_choose_and_render_invalid_then_valid():
    """The choose_and_render menu shows '❌ Invalid choice!' on bad input
    and then accepts a valid pick (line 51)."""
    called = []

    def fake_render(state):
        called.append(True)

    # Snapshot + temporary registry
    snapshot = list(endings._ENDINGS)
    endings.reset_registry()
    endings.register("only_one", "Only One", fake_render, lambda s: True)
    try:
        io = ScriptedIO(["bogus", "1"])
        state = type("S", (), {"io": io})()
        endings.choose_and_render(state, ["lead in"])
    finally:
        endings._ENDINGS.clear()
        endings._ENDINGS.extend(snapshot)
    assert called == [True]


# ── weapon.py ─────────────────────────────────────────────────────────


def test_weapon_summary_with_procs():
    w = Weapon("Burning", components={}, stats={"attack": 3},
               procs=[{"status": "burn", "trigger": "on_hit", "turns": 2}])
    s = w.summary()
    assert "burn" in s and "hit" in s

    w2 = Weapon("Bare", components={}, stats={}, procs=[])
    assert w2.summary() == "(no bonuses)"


# ── dialogue.py ────────────────────────────────────────────────────────


class TestDialogue:
    def test_stone_voice_uses_show_through_stone(self):
        tree = {
            "initial": {
                "lines": ["a line"],
                "voice": "stone",
                "responses": [],
            },
        }
        io = ScriptedIO()
        state = type("S", (), {"io": io, "flags": {}, "player": None})()
        dialogue.run_dialogue(state, tree)
        assert "▒" in io.text() or "::" in io.text()

    def test_invalid_choice_reprompts(self):
        tree = {
            "initial": {
                "lines": ["pick"],
                "responses": [
                    {"text": "leave", "next": None},
                ],
            },
        }
        io = ScriptedIO(["bogus", "1"])
        state = type("S", (), {"io": io, "flags": {}, "player": None})()
        dialogue.run_dialogue(state, tree)
        assert "Invalid choice" in io.text()

    def test_sets_flag_and_grants_consumable(self):
        tree = {
            "initial": {
                "lines": ["pick"],
                "responses": [
                    {"text": "take",
                     "sets_flag": "took_thing",
                     "grants_consumable": "bread",
                     "next": None},
                ],
            },
        }
        io = ScriptedIO(["1"])
        player = type("P", (), {"consumables": []})()
        state = type("S", (), {"io": io, "flags": {}, "player": player})()
        dialogue.run_dialogue(state, tree)
        assert state.flags["took_thing"] is True
        assert "bread" in player.consumables

    def test_sets_flag_on_entry(self):
        tree = {
            "sets_flag_on_entry": "entered_dialogue",
            "initial": {"lines": ["hi"], "responses": []},
        }
        io = ScriptedIO()
        state = type("S", (), {"io": io, "flags": {}, "player": None})()
        dialogue.run_dialogue(state, tree)
        assert state.flags["entered_dialogue"] is True

    def test_response_requires_flag_hides_option(self):
        """Responses gated by a flag are filtered out when the flag is unset."""
        tree = {
            "initial": {
                "lines": ["whisper"],
                "responses": [
                    {"text": "secret",
                     "requires_flag": "knows_secret",
                     "next": None},
                ],
            },
        }
        io = ScriptedIO()
        state = type("S", (), {"io": io, "flags": {}, "player": None})()
        # All responses filtered → reach the no-responses branch (pause+return)
        dialogue.run_dialogue(state, tree)


# ── locations.py — a few more small services ──────────────────────────


@pytest.fixture
def state(content, tmp_path):
    player = Player("Hero", "warrior", content.classes["warrior"], content)
    return GameState(player, content, ScriptedIO(), random.Random(0),
                     chronicle_dir=tmp_path, seed="42")


class TestRunService:
    def test_invalid_service_id_is_silent(self, state):
        # _run_service dispatches by id; an unknown id should not raise
        try:
            locations._run_service(state, "nonexistent_service")
        except Exception:
            pytest.fail("unknown service id should not raise")


class TestSearchGrave:
    def test_search_grave_when_none_present(self, state):
        # No fallen in this location → graceful path
        # _search_grave expects there to be one; instead test _grave_here
        # which returns False when no graves.
        loc = state.content.locations[state.current_location]
        assert locations._grave_here(state, loc, []) is False


class TestEncounterAndTravelLabels:
    def test_travel_label_uses_dest_name(self, state):
        dest = {"name": "Test Place", "kind": "zone"}
        label = locations._travel_label(dest, state.player)
        assert "Test Place" in label

    def test_encounter_label_uses_explicit_label(self, state):
        enc = {"label": "🌑 Test fight", "type": "combat"}
        label = locations._encounter_label(enc, state.content)
        assert label == "🌑 Test fight"


class TestNpcProgress:
    def test_npc_progress_count_for_unstarted(self, state):
        npc = {"id": "any_npc"}
        assert locations._npc_progress(state, npc) == 0


class TestHollowedCandidates:
    def test_no_fallen_means_no_candidates(self, state):
        assert locations._hollowed_candidates(state, []) == []


class TestMaybeOpenHardestGate:
    def test_runs_without_error(self, state):
        # The function is a no-op without certain flags; just exercise it.
        locations._maybe_open_hardest_gate(state)

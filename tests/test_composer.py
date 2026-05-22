"""Composer — note parsing, modes, the typed-input flow."""
import tempfile

import pytest

from terminalquest import composer
from terminalquest.state import GameState
from terminalquest.ui import ScriptedIO
from tests.conftest import StubRandom


# ── Pure helpers ────────────────────────────────────────────────────────


def test_parse_mode_f_phrygian():
    pcs = composer.parse_mode("F_phrygian")
    # F Phrygian: F Gb Ab Bb C Db Eb = pitch classes 5 6 8 10 0 1 3
    assert pcs == frozenset({0, 1, 3, 5, 6, 8, 10})


def test_parse_mode_c_ionian_is_major():
    pcs = composer.parse_mode("C_ionian")
    # C major: C D E F G A B = 0 2 4 5 7 9 11
    assert pcs == frozenset({0, 2, 4, 5, 7, 9, 11})


@pytest.mark.parametrize("bad", ["phrygian", "F", "F_", "_phrygian", "F_bogus",
                                  "X_phrygian", ""])
def test_parse_mode_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        composer.parse_mode(bad)


def test_note_pitch_class():
    assert composer.note_pitch_class("C4") == 0
    assert composer.note_pitch_class("C#3") == 1
    assert composer.note_pitch_class("Db5") == 1
    assert composer.note_pitch_class("F#2") == 6
    assert composer.note_pitch_class("Bb4") == 10


def test_parse_notes_line():
    assert composer.parse_notes_line("C4 G3 Eb4") == ["C4", "G3", "Eb4"]
    assert composer.parse_notes_line("C4,G3,Eb4") == ["C4", "G3", "Eb4"]
    assert composer.parse_notes_line("") == []


def test_parse_notes_line_rejects_garbage():
    with pytest.raises(ValueError, match="didn't understand"):
        composer.parse_notes_line("C4 not_a_note G3")


# ── Matching ────────────────────────────────────────────────────────────


def test_check_exact():
    assert composer.check_exact(["C4", "G3"], ["C4", "G3"])
    assert not composer.check_exact(["C4", "G3"], ["C4", "G#3"])
    assert not composer.check_exact(["C4", "G3"], ["C4", "G3", "Eb4"])


def test_check_by_mode_passes_when_all_notes_in_mode():
    comp = {
        "tolerance": "by_mode",
        "mode": "F_phrygian",
        "min_notes": 3,
        "max_notes": 6,
    }
    # F Phrygian notes
    assert composer.check_by_mode(["F3", "Gb3", "Ab3", "Bb3"], comp)


def test_check_by_mode_fails_when_a_note_is_out():
    comp = {
        "tolerance": "by_mode",
        "mode": "F_phrygian",
        "min_notes": 3,
        "max_notes": 6,
    }
    # E is NOT in F Phrygian (Phrygian has b2, so it has Gb but not E)
    assert not composer.check_by_mode(["F3", "Gb3", "Ab3", "E4"], comp)


def test_check_by_mode_respects_note_count():
    comp = {
        "tolerance": "by_mode",
        "mode": "F_phrygian",
        "min_notes": 4,
        "max_notes": 6,
    }
    # All in mode but only 3 notes — below min
    assert not composer.check_by_mode(["F3", "Gb3", "Ab3"], comp)


def test_check_by_mode_respects_octave_range():
    comp = {
        "tolerance": "by_mode",
        "mode": "F_phrygian",
        "min_notes": 1,
        "max_notes": 8,
        "octave_range": ["F3", "F4"],
    }
    # All in mode, in range
    assert composer.check_by_mode(["F3", "Ab3", "C4"], comp)
    # F5 is above the range
    assert not composer.check_by_mode(["F3", "F5"], comp)


# ── The flow (happy + sad paths) ────────────────────────────────────────


def _state(io):
    """Minimal state for the composer — it only needs io and audio."""
    # Disabled AudioEngine — no playback, no temp files
    return GameState(
        player=None, content=None, io=io, rng=StubRandom(),
        chronicle_dir=tempfile.mkdtemp(),
    )


BELL_QUEST = {
    "name": "The Bell, Once, For the Living",
    "flavor": "The bell tolls for the dead.",
    "target_composition": {
        "tolerance": "exact",
        "notes": ["C4", "G3", "Eb4", "G3"],
        "voice": "bell",
        "altar": "mourncross",
        "hints": ["one", "two", "three", "four"],
    },
}


def test_compose_success_returns_true():
    io = ScriptedIO(inputs=["C4 G3 Eb4 G3", "commit"])
    assert composer.compose(_state(io), BELL_QUEST) is True


def test_compose_wrong_notes_then_correct():
    io = ScriptedIO(inputs=[
        "C4 G3 Eb4 D4",       # 4 wrong notes
        "commit",              # fails
        "C4 G3 Eb4 G3",        # right
        "commit",              # passes
    ])
    assert composer.compose(_state(io), BELL_QUEST) is True


def test_compose_quit_returns_false():
    io = ScriptedIO(inputs=["quit"])
    assert composer.compose(_state(io), BELL_QUEST) is False


def test_compose_hint_progression_then_commit_with_hint_answer():
    io = ScriptedIO(inputs=[
        "hint", "hint", "hint", "hint",  # all four hints
        "C4 G3 Eb4 G3",                   # answer (final hint reveals it)
        "commit",
    ])
    assert composer.compose(_state(io), BELL_QUEST) is True


def test_compose_clear_resets_buffer():
    io = ScriptedIO(inputs=[
        "D4 F4",          # wrong start
        "clear",          # reset
        "C4 G3 Eb4 G3",   # correct
        "commit",
    ])
    assert composer.compose(_state(io), BELL_QUEST) is True


def test_compose_play_before_anything_typed():
    """play with nothing in the buffer should print a notice, not crash."""
    io = ScriptedIO(inputs=["play", "quit"])
    assert composer.compose(_state(io), BELL_QUEST) is False


def test_compose_extra_hints_past_the_last_are_safe():
    io = ScriptedIO(inputs=["hint"] * 6 + ["quit"])  # 6 hints; only 4 exist
    assert composer.compose(_state(io), BELL_QUEST) is False

"""Composer service — typed-input melody puzzle for melody quests.

A melody quest's ``target_composition`` describes a target the player must
match by typing notes. Two tolerance modes:

  exact   — note-for-note match (e.g., ['C4', 'G3', 'Eb4', 'G3'])
  by_mode — every note's pitch class must be in the given mode, note count
            in [min_notes, max_notes], optionally within an octave range

The flow runs synchronously through ``state.io`` (so headless tests work
via ScriptedIO) and plays compositions through ``state.audio`` (so a
disabled engine is a perfect no-op). Returns True on a successful match,
False if the player walks away.

Hints are soft — the last hint typically gives the answer outright. The
kingdom is mourning, not testing.
"""

from __future__ import annotations
from . import boss_music_synth as _synth

# Mode → list of semitone offsets from the root
_MODE_OFFSETS = {
    "aeolian":    [0, 2, 3, 5, 7, 8, 10],   # natural minor
    "phrygian":   [0, 1, 3, 5, 7, 8, 10],   # b2 b3 b6 b7
    "dorian":     [0, 2, 3, 5, 7, 9, 10],   # b3 b7
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],   # b7
    "ionian":     [0, 2, 4, 5, 7, 9, 11],   # major
    "locrian":    [0, 1, 3, 5, 6, 8, 10],   # b2 b3 b5 b6 b7
    "lydian":     [0, 2, 4, 6, 7, 9, 11],   # #4
}

_LETTER_TO_PC = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


# ── Pure helpers — easy to test ─────────────────────────────────────────


def parse_mode(mode_str):
    """``'F_phrygian'`` → ``frozenset({5, 6, 8, 10, 0, 1, 3})``."""
    parts = mode_str.split("_", 1)
    if len(parts) != 2:
        raise ValueError(f"mode must be 'ROOT_NAME' (e.g. 'F_phrygian'), "
                         f"got {mode_str!r}")
    root_str, mode_name = parts
    if root_str not in _LETTER_TO_PC:
        raise ValueError(f"unknown root in mode: {root_str!r}")
    if mode_name not in _MODE_OFFSETS:
        raise ValueError(f"unknown mode: {mode_name!r} "
                         f"(known: {', '.join(sorted(_MODE_OFFSETS))})")
    root_pc = _LETTER_TO_PC[root_str]
    return frozenset((root_pc + offset) % 12 for offset in _MODE_OFFSETS[mode_name])


def note_pitch_class(note_str):
    """``'C#4'`` → ``1``."""
    for i, ch in enumerate(note_str):
        if ch.isdigit() or ch == "-":
            letter = note_str[:i]
            if letter not in _LETTER_TO_PC:
                raise ValueError(f"unknown note letter: {letter!r}")
            return _LETTER_TO_PC[letter]
    raise ValueError(f"can't parse note: {note_str!r}")


def parse_notes_line(line):
    """``'C4 G3 Eb4'`` → ``['C4', 'G3', 'Eb4']`` or raise ``ValueError``."""
    tokens = line.replace(",", " ").split()
    result = []
    for tok in tokens:
        try:
            _synth.note_freq(tok)
        except (KeyError, ValueError, IndexError):
            raise ValueError(
                f"didn't understand '{tok}'. notes look like C4, G3, Eb4, F#5"
            ) from None
        result.append(tok)
    return result


def check_exact(player_notes, target_notes):
    return list(player_notes) == list(target_notes)


def check_by_mode(player_notes, comp):
    """Every note's pitch class in the mode set; count in [min, max];
    optionally within ``octave_range``."""
    mode_pcs = parse_mode(comp["mode"])
    min_n = comp.get("min_notes", 1)
    max_n = comp.get("max_notes", 999)
    if not (min_n <= len(player_notes) <= max_n):
        return False
    octave_range = comp.get("octave_range")
    low_freq = high_freq = None
    if octave_range:
        low_freq = _synth.note_freq(octave_range[0])
        high_freq = _synth.note_freq(octave_range[1])
    for note in player_notes:
        if note_pitch_class(note) not in mode_pcs:
            return False
        if low_freq is not None:
            freq = _synth.note_freq(note)
            if freq < low_freq or freq > high_freq:
                return False
    return True


def check_match(player_notes, comp):
    tolerance = comp.get("tolerance", "exact")
    if tolerance == "exact":
        return check_exact(player_notes, comp["notes"])
    if tolerance == "by_mode":
        return check_by_mode(player_notes, comp)
    return False


# ── The flow ────────────────────────────────────────────────────────────


_QUIT_WORDS = ("quit", "q", "exit", "give up", "walk away")


def compose(state, quest):
    """Run the composer flow for a melody quest. Returns True on a match,
    False if the player walks away."""
    io = state.io
    comp = quest["target_composition"]
    voice = comp.get("voice", "voice")
    hints = list(comp.get("hints", []))

    # For exact mode, target length caps the buffer. For by_mode, max_notes.
    if comp.get("tolerance", "exact") == "exact":
        target_len = len(comp["notes"])
    else:
        target_len = comp.get("max_notes", 8)

    io.show("")
    io.show(f"♪  {quest.get('name', 'Compose a melody')}")
    if quest.get("flavor"):
        io.show_slow(quest["flavor"])
    io.show("")
    io.show("   Type notes like  C4  G3  Eb4  F#5  (letter + octave).")
    io.show("   Commands: play · hint · commit · clear · quit")
    io.show("")

    notes = []
    hint_index = 0

    while True:
        raw = io.ask("♪ > ").strip()
        if not raw:
            continue
        low = raw.lower()

        if low in _QUIT_WORDS:
            io.show("   You walk away. The composition is unmade.")
            return False

        if low == "clear":
            notes = []
            io.show("   cleared.")
            continue

        if low == "play":
            if not notes:
                io.show("   nothing to play yet — type some notes first.")
                continue
            io.show(f"   playing: {' '.join(notes)}")
            state.audio.play_composition(notes, voice=voice)
            continue

        if low == "hint":
            if hint_index >= len(hints):
                io.show("   the world has nothing more to teach you. "
                        "type your guess and commit.")
                continue
            io.show(f"   ── hint {hint_index + 1} of {len(hints)} ──")
            io.show(f"   {hints[hint_index]}")
            hint_index += 1
            continue

        if low == "commit":
            if not notes:
                io.show("   you have nothing to commit — type your notes first.")
                continue
            io.show("   committing…")
            state.audio.play_composition(notes, voice=voice)
            if check_match(notes, comp):
                return True
            io.show("   it does not match. (try again, or 'quit' to walk away.)")
            notes = []
            continue

        # Treat as notes
        try:
            parsed = parse_notes_line(raw)
        except ValueError as e:
            io.show(f"   {e}")
            continue

        notes.extend(parsed)
        if len(notes) > target_len:
            notes = notes[-target_len:]
            io.show(f"   (kept last {target_len}: {' '.join(notes)})")
        else:
            io.show(f"   have: {' '.join(notes)}")
        if (comp.get("tolerance", "exact") == "exact"
                and len(notes) == target_len):
            io.show(f"   {len(notes)} notes. 'play' to hear, "
                    "'commit' when ready.")

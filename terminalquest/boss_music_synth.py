"""Boss music for Mournhold — eight lore-driven themes, pure-stdlib synthesis.

This file is the music team's score sheet. The engine on top renders notes;
the COMPOSITIONS section at the bottom is where the actual music lives —
one function per boss, hand-set, modal, motif-driven.

Each composition returns a list of events:

    (start_seconds, voice_name, note_or_freq, duration_seconds, velocity)

`voice_name` is one of the VOICES dict keys below. `note_or_freq` is either
a string like "A3" / "C#4" / "Bb2" (parsed by note_freq) or a raw Hz float
(used for percussion when pitch is meaningless).

Run directly to populate the cache or to A/B compare themes:

    python3 -m terminalquest.boss_music_synth      # render all to cache
    python3 -m terminalquest.boss_music_synth shadow_warden  # render one
"""

from __future__ import annotations
import argparse
import math
import pathlib
import random
import struct
import wave

SAMPLE_RATE = 16000
PEAK_TARGET = 0.78

DEFAULT_OUT_DIR = pathlib.Path.home() / ".terminalquest" / "audio" / "bosses"


# ── Note name → frequency (equal temperament, A4 = 440 Hz) ──────────────

_SEMITONES = {
    "C": -9, "C#": -8, "Db": -8, "D": -7, "D#": -6, "Eb": -6,
    "E": -5, "F": -4, "F#": -3, "Gb": -3, "G": -2, "G#": -1, "Ab": -1,
    "A": 0, "A#": 1, "Bb": 1, "B": 2,
}


def note_freq(name):
    """Parse 'A4', 'C#3', 'Bb2' into a frequency in Hz."""
    for i, ch in enumerate(name):
        if ch.isdigit() or ch == "-":
            letter = name[:i]
            octave = int(name[i:])
            break
    else:
        raise ValueError(f"can't parse note: {name!r}")
    semitones = _SEMITONES[letter] + (octave - 4) * 12
    return 440.0 * (2 ** (semitones / 12))


# ── Voice palette ───────────────────────────────────────────────────────
# Each voice = harmonic stack (ratio, amplitude) + ADSR envelope + noise.

VOICES = {
    "horn": {
        # Brass-like — many integer harmonics, medium attack
        "harmonics": [(1, 0.55), (2, 0.30), (3, 0.18), (4, 0.10), (5, 0.06)],
        "attack": 0.05, "decay": 0.25, "sustain": 0.55, "release": 0.40,
        "noise": 0.0,
    },
    "bell": {
        # Inharmonic partials — that's what makes a bell sound like a bell
        "harmonics": [(1.0, 0.55), (2.76, 0.40), (5.4, 0.18), (8.93, 0.08)],
        "attack": 0.002, "decay": 0.35, "sustain": 0.0, "release": 1.6,
        "noise": 0.0,
    },
    "voice": {
        # Vocal-formant approximation — odd harmonics emphasised
        "harmonics": [(1, 0.50), (2, 0.18), (3, 0.32), (5, 0.10)],
        "attack": 0.30, "decay": 0.40, "sustain": 0.75, "release": 0.70,
        "noise": 0.01,
    },
    "bass": {
        # Smooth low foundation
        "harmonics": [(1, 0.55), (1.5, 0.10), (2, 0.12)],
        "attack": 0.06, "decay": 0.18, "sustain": 0.70, "release": 0.40,
        "noise": 0.0,
    },
    "lead": {
        # Detuned chorus pair — for melody lines
        "harmonics": [(1, 0.45), (1.005, 0.45), (2, 0.10)],
        "attack": 0.08, "decay": 0.20, "sustain": 0.65, "release": 0.50,
        "noise": 0.0,
    },
    "drone": {
        # Long-fade pad
        "harmonics": [(1, 0.40), (1.5, 0.15), (2, 0.10)],
        "attack": 1.20, "decay": 0.40, "sustain": 0.90, "release": 1.20,
        "noise": 0.008,
    },
    "hammer": {
        # Percussive — low thud + click + decay
        "harmonics": [(1, 0.70), (1.5, 0.25), (3, 0.18)],
        "attack": 0.001, "decay": 0.08, "sustain": 0.0, "release": 0.18,
        "noise": 0.25,
    },
    "crackle": {
        # Pure short noise burst — freq ignored
        "harmonics": [(1, 0.0)],
        "attack": 0.001, "decay": 0.03, "sustain": 0.0, "release": 0.10,
        "noise": 1.0,
    },
    "stone": {
        # Low rumble for the Tomb
        "harmonics": [(1, 0.55)],
        "attack": 0.25, "decay": 0.15, "sustain": 0.80, "release": 0.50,
        "noise": 0.45,
    },
    "breath": {
        # Hollow, breathy — for the Penitent's gasps
        "harmonics": [(1, 0.30), (2, 0.10)],
        "attack": 0.10, "decay": 0.20, "sustain": 0.20, "release": 0.40,
        "noise": 0.60,
    },
}


# ── Renderer ─────────────────────────────────────────────────────────────


def _adsr(n_samples, sample_rate, voice):
    """Per-sample ADSR amplitude array, scaled if note is shorter than a+d+r."""
    a = voice["attack"]
    d = voice["decay"]
    s = voice["sustain"]
    r = voice["release"]
    total = a + d + r
    note_seconds = n_samples / sample_rate
    if total > note_seconds:
        scale = note_seconds / total
        a *= scale
        d *= scale
        r *= scale
    an = max(1, int(a * sample_rate))
    dn = max(1, int(d * sample_rate))
    rn = max(1, int(r * sample_rate))
    sn = max(0, n_samples - an - dn - rn)
    env = [0.0] * n_samples
    idx = 0
    for i in range(min(an, n_samples - idx)):
        env[idx] = i / an
        idx += 1
    for i in range(min(dn, n_samples - idx)):
        env[idx] = 1.0 - (1.0 - s) * (i / dn)
        idx += 1
    for i in range(min(sn, n_samples - idx)):
        env[idx] = s
        idx += 1
    for i in range(min(rn, n_samples - idx)):
        env[idx] = s * (1.0 - i / rn)
        idx += 1
    return env


def _render_note(freq, duration_s, voice_name, sample_rate, seed):
    """Render one note. Returns a list of float samples."""
    voice = VOICES[voice_name]
    n_samples = max(1, int(duration_s * sample_rate))
    env = _adsr(n_samples, sample_rate, voice)
    rng = random.Random(seed)
    out = [0.0] * n_samples
    two_pi = 2 * math.pi
    harmonics = voice["harmonics"]
    noise_amp = voice["noise"]
    for n in range(n_samples):
        t = n / sample_rate
        v = 0.0
        for ratio, amp in harmonics:
            if amp > 0.0:
                v += amp * math.sin(two_pi * freq * ratio * t)
        if noise_amp > 0.0:
            v += noise_amp * (rng.random() * 2.0 - 1.0)
        out[n] = v * env[n]
    return out


def render_events(events, total_seconds, sample_rate=SAMPLE_RATE, seed=0):
    """Render a sequence of voiced events to int16 mono samples."""
    n_total = int(total_seconds * sample_rate)
    out = [0.0] * n_total
    note_rng = random.Random(seed)
    for start_s, voice_name, note, duration_s, velocity in events:
        if isinstance(note, str) and note != "noise":
            freq = note_freq(note)
        else:
            freq = 220.0  # placeholder for unpitched / noise
        samples = _render_note(
            freq, duration_s, voice_name, sample_rate,
            seed=note_rng.randint(0, 99999),
        )
        start_idx = int(start_s * sample_rate)
        for i, s in enumerate(samples):
            j = start_idx + i
            if 0 <= j < n_total:
                out[j] += s * velocity
    # Loop-safe fade in/out
    fade_n = max(1, min(int(0.5 * sample_rate), n_total // 2))
    for n in range(fade_n):
        out[n] *= n / fade_n
        out[n_total - 1 - n] *= n / fade_n
    # Normalize to int16 with headroom
    peak = max((abs(v) for v in out), default=1.0) or 1.0
    scale = (32767 * PEAK_TARGET) / peak
    return [int(v * scale) for v in out]


def write_wav(samples, path, sample_rate=SAMPLE_RATE):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))


# ════════════════════════════════════════════════════════════════════════
#  COMPOSITIONS — one boss, one theme, hand-set per the lore brief
# ════════════════════════════════════════════════════════════════════════


def pallid_stag():
    """The Witherwood's corrupted forester. He wore antlers too long.

    Mode:    A natural minor — once-regal, going quiet.
    Tempo:   70 BPM.
    Motif:   A descending hunting-horn fanfare (A4–G4–F4–E4) that fractures
             on every third pass — the call he can no longer finish.
    Voices:  horn (lead), bass (pedal A1), crackle (a branch breaking under
             the antler-bearer).
    Arc:     three passes of the fanfare. Pass 3 ends on the wrong note.
    """
    beat = 60.0 / 70
    events = []

    # Bass pedal — held A1 for the whole piece
    events.append((0.0, "bass", "A1", 16 * beat, 0.55))
    events.append((8 * beat, "bass", "A1", 8 * beat, 0.45))

    # Three passes of the descending fanfare
    for pass_idx in range(3):
        offset = pass_idx * 5 * beat
        # Pass 3 is broken — last note shifts down a semitone (Eb instead of E)
        last = "Eb4" if pass_idx == 2 else "E4"
        events += [
            (offset + 0 * beat, "horn", "A4", beat, 0.85),
            (offset + 1 * beat, "horn", "G4", beat, 0.75),
            (offset + 2 * beat, "horn", "F4", beat, 0.75),
            (offset + 3 * beat, "horn", last, 1.5 * beat, 0.85),
        ]
        # Branch crackle on beat 3 of each pass
        events.append((offset + 2 * beat, "crackle", "noise", 0.25, 0.45))

    return events, 16 * beat


def red_beard():
    """The Brackmere smith. Drowned on his march to the capital, kept by
    the Pall — with the hammer.

    Mode:    E Phrygian — the b2 (F) gives the menace.
    Tempo:   accelerates 60 → 110 BPM, the rage rising.
    Motif:   hammer-blows on the beat over a low pedal. Each section
             halves the blow interval.
    Voices:  hammer (percussion), bass (E1 pedal), drone (low E2).
    Arc:     forge → strikes → frenzy.
    """
    events = []

    # Continuous low drone — water under stone
    events.append((0.0, "drone", "E2", 18.0, 0.45))
    events.append((0.0, "bass", "E1", 18.0, 0.50))

    # Section 1 — forge, slow blows. 60 BPM = 1.0 s/beat. 4 blows.
    t = 1.0
    for _ in range(4):
        events.append((t, "hammer", "E2", 0.4, 0.85))
        t += 1.0

    # Section 2 — strikes, faster. ~80 BPM = 0.75 s. 6 blows.
    for _ in range(6):
        events.append((t, "hammer", "E2", 0.3, 0.90))
        t += 0.75

    # Section 3 — frenzy, fastest. ~110 BPM = 0.55 s. 8 blows, last one
    # lands on F2 (the Phrygian b2 — wrong, but committed).
    for i in range(8):
        pitch = "F2" if i == 7 else "E2"
        events.append((t, "hammer", pitch, 0.25, 0.95))
        t += 0.55

    return events, 18.0


def maw_mother():
    """The granary-keeper who counted the stores 'too few to share.'
    Now she IS the kingdom's hunger.

    Mode:    D Locrian — the b5 (Ab) keeps everything off-balance.
    Tempo:   ~50 BPM, ponderous.
    Motif:   a descending three-note phrase that swallows itself —
             D3 → C3 → Ab2 — repeated with a half-step lower each cycle.
    Voices:  stone (rumble), bass (drop pedal), voice (a low murmur of
             counting).
    Arc:     three cycles, each cycle drops a semitone. The hoard sinks.
    """
    events = []
    beat = 60.0 / 50

    # Cycles: (root, start_time)
    cycles = [
        ("D",  0.0),
        ("C#", 6 * beat),
        ("C",  12 * beat),
    ]

    def desc_phrase(root_name, start, ampl):
        """Three-note descending phrase from the root."""
        # Roots: D2/D3, then transpose
        return [
            (start + 0 * beat, "voice", root_name + "3", 2 * beat, ampl),
            (start + 2 * beat, "voice", root_name + "3", 1 * beat, ampl * 0.8),
            # Wrong note — the b5 of this cycle's mode
        ]

    # Per cycle: stone rumble, bass drop, descending voice phrase
    for root, start in cycles:
        events.append((start, "stone", root + "2", 6 * beat, 0.55))
        events.append((start, "bass", root + "1", 6 * beat, 0.50))
        events += desc_phrase(root, start, 0.55)

    # Final swallow — long low Ab1 holds past the last cycle
    events.append((16 * beat, "stone", "Ab1", 4 * beat, 0.70))
    events.append((16 * beat, "bass", "Ab1", 4 * beat, 0.50))

    return events, 20 * beat


def hollow_bellward():
    """The bellward who rang the curfew that locked Mourncross' gates.
    He rings it yet. He cannot stop.

    Mode:    C Aeolian — the natural minor, but only one note matters.
    Tempo:   60 BPM exactly. One toll per second. For a full minute. Then
             the wrong note lands once, late, and we start again.
    Motif:   the same bell strike, C3, every second. The wrong toll (Db3)
             lands at t = 47 — well past where the listener has stopped
             paying attention. Then the loop returns to C3 for the rest
             of the minute. In game this means the wrong toll is rare:
             one in sixty.
    Voices:  bell, drone.
    Arc:     none. Repetition is the horror. The wrong toll is the
             reminder that he hears it, every time, and cannot stop.
    """
    events = []
    duration = 60.0

    # Foundation — low C2 drone for the whole minute
    events.append((0.0, "drone", "C2", duration, 0.40))

    # The bell. Sixty tolls. The 47th is wrong.
    for n in range(1, 60):
        wrong = (n == 47)
        pitch = "Db3" if wrong else "C3"
        velocity = 0.95 if wrong else 0.85
        events.append((float(n), "bell", pitch, 2.0, velocity))

    return events, duration


def cantor_vael():
    """He led the Rite of Unremembering. He knew it would break the
    kingdom. He sang it anyway.

    Mode:    starts F Mixolydian (the hymn), curdles to F Phrygian (the
             curse). The b2 (Gb) is the moment the rite turns.
    Tempo:   ~52 BPM, sustained.
    Motif:   a held vocal note (F3) above a descending melodic line
             F-Eb-Db-C. The Db is where the hymn becomes the curse.
    Voices:  voice (lead), bass, drone.
    Arc:     two passes. Pass 1 is the hymn. Pass 2, the Db lands harder,
             stays longer, opens into the still beauty of the curse.
    """
    events = []
    beat = 60.0 / 52

    # Held drone — F1 for the duration
    events.append((0.0, "drone", "F1", 24.0, 0.35))
    events.append((0.0, "bass", "F2", 24.0, 0.40))

    # Pass 1 — the hymn (Mixolydian)
    events += [
        (0 * beat,  "voice", "F3",  4 * beat, 0.70),
        (4 * beat,  "voice", "Eb3", 2 * beat, 0.65),
        (6 * beat,  "voice", "Db3", 2 * beat, 0.75),
        (8 * beat,  "voice", "C3",  4 * beat, 0.70),
    ]

    # Pass 2 — the curse (Phrygian). The Db lingers; a high held F3
    # joins as the rite opens itself wider.
    events += [
        (13 * beat, "voice", "F3",  4 * beat, 0.80),
        (13 * beat, "lead",  "F4",  6 * beat, 0.40),
        (17 * beat, "voice", "Eb3", 2 * beat, 0.70),
        (19 * beat, "voice", "Db3", 5 * beat, 0.95),
        (19 * beat, "lead",  "Ab4", 5 * beat, 0.45),
    ]

    return events, 26 * beat


def ashen_penitent():
    """The first to climb. The first to turn back. The Climb does not
    permit a man to leave it twice.

    Mode:    B Phrygian — the b2 (C) is the slip on the slope.
    Tempo:   ~80 BPM, breath-driven, irregular.
    Motif:   a melodic phrase that tries to ascend B-C-D-E-F#, but the
             top note never lands cleanly. Each pass climbs one note
             higher than the last, then collapses.
    Voices:  lead (the climbing voice), bass (pulling down), breath (the
             gasps between phrases).
    Arc:     three failed ascents, each one further up the slope.
    """
    events = []
    beat = 60.0 / 80

    # Bass — pulling down. Low B1, sustained.
    events.append((0.0, "bass", "B1", 22.0, 0.45))

    # Three attempts. Each pass reaches one note higher before failing.
    attempts = [
        # (start_beat, climb_notes, gasp_count)
        (0,  ["B3", "C4", "D4"],              2),  # Pass 1: climbs to D4
        (8,  ["B3", "C4", "D4", "E4"],        3),  # Pass 2: climbs to E4
        (16, ["B3", "C4", "D4", "E4", "F#4"], 4),  # Pass 3: climbs to F#4
    ]

    for start_b, climb, gasps in attempts:
        # Breath bursts before the attempt (the gasps)
        for g in range(gasps):
            t = (start_b + g * 0.3) * beat
            events.append((t, "breath", "G2", 0.4, 0.35))

        # The climb itself — each note slightly louder than the last,
        # the topmost note clipped short (the fall)
        for i, n in enumerate(climb):
            t = (start_b + 2 + i * 0.5) * beat
            dur = 0.6 * beat if i < len(climb) - 1 else 0.3 * beat
            vel = 0.55 + 0.08 * i
            events.append((t, "lead", n, dur, vel))

        # The collapse — bass thud
        events.append(((start_b + 2 + len(climb) * 0.5) * beat,
                       "hammer", "B2", 0.4, 0.65))

    return events, 22.0


# Per-boss quote fragments — each is a short echo of that boss's own theme,
# placed inside the Warden's base layout. Only the quotes for bosses the
# player has actually defeated *in this run* are added. Empty list means
# the Warden plays without any quotes — a cold, naked theme. That's its
# own kind of horror: it has no rehearsals to wear.
_WARDEN_QUOTES = {
    "pallid_stag": [
        # Stag's descending horn fanfare, transposed (D4-C4-Bb3)
        (0.5, "horn", "D4",  1.2, 0.55),
        (1.7, "horn", "C4",  1.2, 0.55),
        (2.9, "horn", "Bb3", 1.5, 0.60),
    ],
    "red_beard": [
        # Two hammer-blows — the smith's pulse, far away
        (5.0, "hammer", "Bb2", 0.3, 0.65),
        (5.6, "hammer", "Bb2", 0.3, 0.55),
    ],
    "maw_mother": [
        # The descending swallow — D3 dropping to Db3
        (7.0, "voice", "D3",  1.5, 0.50),
        (8.5, "voice", "Db3", 1.5, 0.55),
    ],
    "hollow_bellward": [
        # One toll, lower than his — the bellward heard distantly
        (4.5, "bell", "Bb2", 3.0, 0.70),
    ],
    "cantor_vael": [
        # The Cantor's b2 (Gb) creeping into a chord — the rite remembered
        (8.0,  "voice", "Bb3", 4.0, 0.60),
        (9.0,  "voice", "Gb3", 4.0, 0.55),
        (10.0, "voice", "F3",  5.0, 0.55),
    ],
    "ashen_penitent": [
        # A gasp, then a short climb that stops before the top
        (6.0, "breath", "G2", 0.3, 0.30),
        (6.4, "lead",   "C4", 0.4, 0.50),
        (6.8, "lead",   "D4", 0.4, 0.55),
        (7.2, "lead",   "E4", 0.2, 0.50),  # cut off
    ],
    "the_forgotten_thing": [
        # The high G#5 — the nursery-rhyme note a child wouldn't sing
        (1.5, "bell", "G#5", 1.5, 0.35),
    ],
}


def shadow_warden(defeated_bosses=None):
    """The first climber the Pall ever kept. It wears them like a coat.

    Mode:    chromatic — no key centre. It moves between modes by
             half-step at will. This is the only boss whose music has
             no home.
    Tempo:   shifting, layered. Two pulses at once: a slow 40 BPM bell
             and a faster 80 BPM hammer.
    Motif:   it **quotes** the prior bosses — but only the ones this
             character has actually defeated this run. A player who only
             beat Stag and Bellward hears the Warden wearing those two
             alone. A player who beat everyone hears the full chorus.
             A player who somehow reached the Summit without beating
             anyone hears the Warden cold — no echoes — and that is its
             own kind of horror.
    Voices:  every voice that any defeated boss used.
    Arc:     opening (0–8 s) gathers the quotes → middle (8–18 s) bell
             and hammer pulses layer with chromatic descent → final
             chord (18–24 s) held, unresolved.

    ``defeated_bosses`` — list of enemy ids defeated this run. None
    defaults to "all eight" so the design preview shows every quote.
    """
    if defeated_bosses is None:
        # Preview mode — quote every boss the engine knows about
        defeated_bosses = list(_WARDEN_QUOTES.keys())

    events = []

    # ── Base layout — present regardless of what was defeated ────

    # Low chromatic drone underneath
    events.append((0.0, "drone", "Bb1", 24.0, 0.40))
    events.append((4.0, "bass",  "Bb1", 20.0, 0.40))

    # Slow bell pulse (40 BPM) — three tolls, mid-piece
    for n in range(3):
        events.append((8.0 + n * 1.5, "bell", "Bb2", 1.5, 0.45))

    # Faster hammer pulse (80 BPM) — ten strikes underneath
    for n in range(10):
        events.append((9.0 + n * 0.75, "hammer", "Bb1", 0.25, 0.50))

    # Chromatic descent — all four notes wrong relative to Bb minor
    events += [
        (12.0, "lead", "F4",  1.0, 0.55),
        (13.0, "lead", "E4",  1.0, 0.55),
        (14.0, "lead", "Eb4", 1.0, 0.55),
        (15.0, "lead", "D4",  2.0, 0.65),
    ]

    # Final chord — Bb minor + Gb (the unresolved b2). Held to the end.
    events += [
        (18.0, "voice", "Bb3", 6.0, 0.65),
        (18.0, "voice", "Db4", 6.0, 0.55),
        (18.0, "voice", "F4",  6.0, 0.55),
        (18.0, "voice", "Gb4", 6.0, 0.50),
    ]

    # ── Quotes — added per defeated boss, layered on top of base ───
    for boss_id in defeated_bosses:
        events.extend(_WARDEN_QUOTES.get(boss_id, []))

    return events, 24.0


def forgotten_thing():
    """Something the Pall did not finish forgetting. Older than the Rite.
    It has watched every climber buried in the Witherwood. It knows your
    name and will not say it.

    Mode:    D Lydian, but distorted — the #4 (G#) sounds wrong in the
             register chosen.
    Tempo:   ~45 BPM, lullaby-slow.
    Motif:   a four-note nursery phrase D5-F#5-A5-G#5 — the G# is the
             note a child wouldn't sing. Played on a high bell. The
             phrase doesn't resolve; long silences between repetitions.
    Voices:  bell (the phrase), drone (something underneath).
    Arc:     three repetitions of the phrase. Each silence between them
             is a beat longer than the last. The last phrase fades early.
    """
    events = []

    # Underneath — low D1, almost not there
    events.append((0.0, "drone", "D1", 20.0, 0.35))

    # The nursery phrase (4 notes). 1.0 s per note.
    phrase = [("D5", 1.0), ("F#5", 1.0), ("A5", 1.0), ("G#5", 2.0)]

    # Three iterations, with growing silences (3, 4, 5 seconds)
    silences = [3.0, 4.0, 5.0]
    t = 0.5
    for iteration in range(3):
        for note, dur in phrase:
            ampl = 0.65 if iteration < 2 else 0.50
            events.append((t, "bell", note, dur, ampl))
            t += dur
        # Last iteration cut short — only first two notes, then silence
        if iteration == 2:
            break
        t += silences[iteration]

    return events, 20.0


# ── Theme registry — keyed by enemy id from data/enemies.json ──────────

THEMES = {
    "pallid_stag":         pallid_stag,
    "red_beard":           red_beard,
    "maw_mother":          maw_mother,
    "hollow_bellward":     hollow_bellward,
    "cantor_vael":         cantor_vael,
    "ashen_penitent":      ashen_penitent,
    "shadow_warden":       shadow_warden,
    "the_forgotten_thing": forgotten_thing,
}

BOSS_IDS = frozenset(THEMES.keys())

# The Shadow Warden is the only theme whose composition depends on per-run
# state (which bosses the player has actually defeated). Listed here so the
# audio engine knows to re-render its WAV per fight instead of caching.
DYNAMIC_THEMES = frozenset({"shadow_warden"})


def render_boss(boss_id, defeated_bosses=None, sample_rate=SAMPLE_RATE):
    """Render one boss theme to int16 samples.

    For shadow_warden, ``defeated_bosses`` is the list of enemy ids the
    player has actually killed this run — the Warden only quotes those.
    For every other boss the argument is ignored.
    """
    composer = THEMES[boss_id]
    if boss_id == "shadow_warden":
        events, duration = composer(defeated_bosses=defeated_bosses)
    else:
        events, duration = composer()
    return render_events(events, duration, sample_rate=sample_rate)


def render_all_to(out_dir=DEFAULT_OUT_DIR):
    """Render every non-dynamic boss theme to ``out_dir`` if missing.

    Skips themes already on disk. Skips DYNAMIC_THEMES entirely — those
    are rendered per-fight from runtime state.
    """
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for boss_id in THEMES:
        if boss_id in DYNAMIC_THEMES:
            continue
        path = out_dir / f"{boss_id}.wav"
        if path.exists():
            continue
        samples = render_boss(boss_id)
        write_wav(samples, path)
        written.append(boss_id)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("boss_id", nargs="?", default=None,
                    help="render one boss (default: render all non-dynamic)")
    ap.add_argument("--out", default=str(DEFAULT_OUT_DIR),
                    help=f"output directory (default: {DEFAULT_OUT_DIR})")
    args = ap.parse_args()
    out_dir = pathlib.Path(args.out)
    if args.boss_id:
        if args.boss_id not in THEMES:
            print(f"  unknown boss: {args.boss_id}")
            print(f"  known: {', '.join(sorted(THEMES))}")
            return
        out = out_dir / f"{args.boss_id}.wav"
        print(f"  rendering {args.boss_id} → {out}")
        out_dir.mkdir(parents=True, exist_ok=True)
        write_wav(render_boss(args.boss_id), out)
    else:
        written = render_all_to(out_dir)
        if written:
            print(f"  rendered {len(written)} themes into {out_dir}: "
                  f"{', '.join(written)}")
        else:
            print(f"  all non-dynamic themes already cached in {out_dir}")
        print(f"  ({len(DYNAMIC_THEMES)} dynamic themes are rendered per-fight: "
              f"{', '.join(sorted(DYNAMIC_THEMES))})")


if __name__ == "__main__":
    main()

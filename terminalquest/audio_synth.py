"""Procedural ambient drones for Mournhold — pure stdlib.

Seven palettes for the kingdom's seven moods, mapped across all 22 zones.
The whole sound bed is computed from ``math.sin`` and a handful of params.
No external assets. No numpy. The audio engine renders these WAVs once
into ``~/.terminalquest/audio/`` on first launch.

Run directly to populate the cache or to A/B compare palettes:

    python3 -m terminalquest.audio_synth         # render all to ~/.terminalquest/audio
    python3 -m terminalquest.audio_synth --list  # print recipes, no audio
"""
import argparse
import math
import pathlib
import random
import struct
import wave

SAMPLE_RATE = 16000
DURATION_S = 10
PEAK_TARGET = 0.78


DEFAULT_OUT_DIR = pathlib.Path.home() / ".terminalquest" / "audio"


# ── Palettes ─────────────────────────────────────────────────────────────
# Each palette is a dict the renderer consumes. Seven palettes cover the
# 22 zones. The mapping is in ZONE_PALETTE below.
#
# fundamental_hz  — base pitch
# partials        — list of (ratio_to_fundamental, amplitude)
# breath_hz       — slow amplitude LFO; period ≈ 1/breath_hz seconds
# heartbeat_hz    — narrow pulses at this rate, 0.0 to disable
# noise_amp       — broadband noise floor; 0.0 = silent floor
# low_pass        — one-pole low-pass coefficient, lower = warmer / more muffled

PALETTES = {
    "hearth": {
        "tag": "warmth held against ending — fires that haven't gone out",
        "fundamental_hz": 87.31,
        "partials": [(1.0, 0.40), (1.500, 0.16), (2.0, 0.10)],
        "breath_hz": 0.08,
        "heartbeat_hz": 0.5,
        "noise_amp": 0.015,
        "low_pass": 0.35,
    },
    "wither": {
        "tag": "the grey blew in here first — drift, dead branches",
        "fundamental_hz": 110.0,
        "partials": [(1.0, 0.30), (1.005, 0.30), (2.0, 0.08)],
        "breath_hz": 0.06,
        "heartbeat_hz": 0.0,
        "noise_amp": 0.04,
        "low_pass": 0.30,
    },
    "drown": {
        "tag": "the water remembers — deep, slow, takes its time",
        "fundamental_hz": 55.0,
        "partials": [(1.0, 0.50), (1.5, 0.10), (4.0, 0.04)],
        "breath_hz": 0.04,
        "heartbeat_hz": 0.0,
        "noise_amp": 0.025,
        "low_pass": 0.20,
    },
    "hall": {
        "tag": "long decay, no one home — Mourncross emptied",
        "fundamental_hz": 87.31,
        "partials": [(1.0, 0.30), (1.498, 0.25), (3.0, 0.06)],
        "breath_hz": 0.10,
        "heartbeat_hz": 0.0,
        "noise_amp": 0.0,
        "low_pass": 0.40,
    },
    "summit": {
        "tag": "thin, high, painful — and a rumble underneath",
        "fundamental_hz": 65.41,
        "partials": [(1.0, 0.30), (8.0, 0.13), (8.02, 0.13)],
        "breath_hz": 0.05,
        "heartbeat_hz": 0.0,
        "noise_amp": 0.06,
        "low_pass": 0.55,
    },
    "stone": {
        "tag": "she is the floor — almost still, grain in the stone",
        "fundamental_hz": 49.0,
        "partials": [(1.0, 0.50), (1.5, 0.05)],
        "breath_hz": 0.02,
        "heartbeat_hz": 0.0,
        "noise_amp": 0.02,
        "low_pass": 0.18,
    },
    "beyond": {
        "tag": "across the border — distant, cooler, watching",
        "fundamental_hz": 73.42,
        "partials": [(1.0, 0.30), (1.5, 0.15), (3.0, 0.08)],
        "breath_hz": 0.07,
        "heartbeat_hz": 0.0,
        "noise_amp": 0.012,
        "low_pass": 0.30,
    },
}


# Which zone maps to which palette. The 22 zones share 7 sound beds.
ZONE_PALETTE = {
    "crossroads":        "hearth",
    "village":           "hearth",
    "hunters_cache":     "hearth",
    "hidden_hold":       "hearth",
    "forest":            "wither",
    "mountain":          "wither",
    "reach":             "drown",
    "drowned_holds":     "drown",
    "cave":              "drown",
    "last_dyke":         "drown",
    "karst_outpost":     "drown",
    "mourncross":        "hall",
    "choir":             "hall",
    "burned_library":    "hall",
    "last_altar":        "hall",
    "pre_pall_shrine":   "hall",
    "sealed_chamber":    "hall",
    "summit":            "summit",
    "the_border":        "beyond",
    "wynne_camp":        "beyond",
    "margrave_monument": "beyond",
    "bone_tomb":         "stone",
}


# ── Renderer ─────────────────────────────────────────────────────────────


def render(palette, seconds=DURATION_S, sample_rate=SAMPLE_RATE, seed=0):
    """Generate int16 mono samples for a given palette dict.

    Pure function of (palette, seconds, rate, seed). Same seed → same WAV.
    """
    rng = random.Random(seed)
    n_samples = int(seconds * sample_rate)
    # Fade is 0.6 s by default but clamped to half the clip — for very short
    # clips (tests) the fade can't exceed what we have to fade.
    fade_n = max(1, min(int(0.6 * sample_rate), n_samples // 2))

    f0 = palette["fundamental_hz"]
    partials = palette["partials"]
    breath_hz = palette["breath_hz"]
    heart_hz = palette["heartbeat_hz"]
    noise_amp = palette["noise_amp"]
    alpha = palette["low_pass"]

    out = [0.0] * n_samples
    two_pi = 2 * math.pi

    for n in range(n_samples):
        t = n / sample_rate
        v = 0.0
        for ratio, amp in partials:
            v += amp * math.sin(two_pi * f0 * ratio * t)
        if breath_hz > 0.0:
            breath = 0.5 + 0.5 * math.sin(two_pi * breath_hz * t)
            v *= 0.55 + 0.45 * breath
        if heart_hz > 0.0:
            phase = (t * heart_hz) % 1.0
            pulse = math.exp(-60 * (phase - 0.5) ** 2)
            v += pulse * 0.18 * math.sin(two_pi * f0 * 0.5 * t)
        if noise_amp > 0.0:
            v += noise_amp * (rng.random() * 2.0 - 1.0)
        out[n] = v

    state = 0.0
    for n in range(n_samples):
        state = alpha * out[n] + (1.0 - alpha) * state
        out[n] = state

    for n in range(fade_n):
        out[n] *= n / fade_n
        out[n_samples - 1 - n] *= n / fade_n

    peak = max(abs(v) for v in out) or 1.0
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


def render_all(out_dir=DEFAULT_OUT_DIR):
    """Render every palette WAV into ``out_dir``. Skips ones already on disk."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, palette in PALETTES.items():
        path = out_dir / f"{name}.wav"
        if path.exists():
            continue
        write_wav(render(palette), path)
        written.append(name)
    return written


def list_recipes():
    print(f"\nMournhold — {len(PALETTES)} sound palettes for {len(ZONE_PALETTE)} zones\n")
    for name, p in PALETTES.items():
        zones = [z for z, pal in ZONE_PALETTE.items() if pal == name]
        print(f"  {name:8s}  {p['fundamental_hz']:6.2f} Hz  · {p['tag']}")
        print(f"           zones: {', '.join(zones)}")
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true",
                    help="print recipe table without generating audio")
    ap.add_argument("--out", default=str(DEFAULT_OUT_DIR),
                    help=f"output directory (default: {DEFAULT_OUT_DIR})")
    args = ap.parse_args()
    if args.list:
        list_recipes()
        return
    written = render_all(out_dir=args.out)
    if written:
        print(f"  rendered {len(written)} palettes into {args.out}: "
              f"{', '.join(written)}")
    else:
        print(f"  all palettes already cached in {args.out}")


if __name__ == "__main__":
    main()

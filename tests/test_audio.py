"""Audio engine — opt-in, fails silently, no subprocess when disabled."""
from unittest.mock import patch

from terminalquest import audio_synth
from terminalquest.audio import AudioEngine


def test_disabled_engine_is_total_no_op(tmp_path):
    """The default state of the engine — used by every headless test —
    must never touch a subprocess, never read or write the filesystem."""
    engine = AudioEngine(enabled=False, cache_dir=tmp_path / "cache")
    with patch("subprocess.Popen") as popen:
        engine.ensure_assets()
        engine.play_zone("forest")
        engine.play_zone("crossroads")
        engine.stop()
        assert popen.call_count == 0
    # Asset cache should not be created either.
    assert not (tmp_path / "cache").exists()


def test_play_zone_unknown_is_no_op(tmp_path):
    """A zone id not in ZONE_PALETTE is silently ignored — not an error."""
    engine = AudioEngine(enabled=True, cache_dir=tmp_path / "cache")
    with patch("subprocess.Popen") as popen:
        engine.play_zone("no_such_zone_qjxz")
        assert popen.call_count == 0
    engine.stop()


def test_zone_palette_covers_every_zone(content):
    """Every location in the game must have a palette assignment — adding
    a zone without one would mean an awkward silent-drone transition."""
    missing = [loc_id for loc_id in content.locations
               if loc_id not in audio_synth.ZONE_PALETTE]
    assert missing == [], f"zones without palettes: {missing}"


def test_mute_unmute_round_trip(tmp_path):
    engine = AudioEngine(enabled=True, cache_dir=tmp_path / "cache")
    assert engine.enabled is True
    engine.mute()
    assert engine.enabled is False
    engine.unmute()
    assert engine.enabled is True
    engine.stop()


def test_stop_is_idempotent(tmp_path):
    engine = AudioEngine(enabled=False, cache_dir=tmp_path / "cache")
    engine.stop()
    engine.stop()
    engine.stop()
    # If we got here, no exception was raised.


# ── audio_synth ─────────────────────────────────────────────────────────


def test_render_produces_expected_sample_count():
    palette = audio_synth.PALETTES["hearth"]
    samples = audio_synth.render(palette, seconds=0.1, sample_rate=8000)
    assert len(samples) == 800


def test_render_is_deterministic_for_same_seed():
    palette = audio_synth.PALETTES["wither"]   # uses noise → seed matters
    a = audio_synth.render(palette, seconds=0.1, sample_rate=8000, seed=42)
    b = audio_synth.render(palette, seconds=0.1, sample_rate=8000, seed=42)
    assert a == b


def test_render_samples_fit_int16_range():
    for palette in audio_synth.PALETTES.values():
        samples = audio_synth.render(palette, seconds=0.1, sample_rate=8000)
        assert all(-32768 <= s <= 32767 for s in samples)


def test_render_all_writes_wav_files(tmp_path):
    """Synthesis path end-to-end — no audio plays, only file output."""
    import wave
    # Pinch DURATION_S so the test stays fast.
    with patch.object(audio_synth, "DURATION_S", 0.1):
        written = audio_synth.render_all(out_dir=tmp_path)
    assert set(written) == set(audio_synth.PALETTES)
    for name in audio_synth.PALETTES:
        w = wave.open(str(tmp_path / f"{name}.wav"), "rb")
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == audio_synth.SAMPLE_RATE
        w.close()


def test_render_all_skips_existing(tmp_path):
    """Idempotent — re-running shouldn't regenerate what's already on disk."""
    (tmp_path / "hearth.wav").write_bytes(b"placeholder")
    with patch.object(audio_synth, "DURATION_S", 0.1):
        written = audio_synth.render_all(out_dir=tmp_path)
    assert "hearth" not in written
    assert (tmp_path / "hearth.wav").read_bytes() == b"placeholder"


def test_ensure_assets_warns_on_first_launch(tmp_path):
    """When WAVs are missing and an io is provided, surface a one-liner so
    the ~3-s synthesis pause doesn't look like a hang."""
    from terminalquest.ui import ScriptedIO
    engine = AudioEngine(enabled=True, cache_dir=tmp_path)
    io = ScriptedIO()
    with patch.object(audio_synth, "DURATION_S", 0.1):
        engine.ensure_assets(io=io)
    assert "Preparing" in io.text()


def test_ensure_assets_silent_when_cached(tmp_path):
    """Second launch — assets already on disk — must not print anything."""
    from terminalquest.ui import ScriptedIO
    # Pre-populate the cache so ensure_assets has nothing to do.
    for name in audio_synth.PALETTES:
        (tmp_path / f"{name}.wav").write_bytes(b"placeholder")
    engine = AudioEngine(enabled=True, cache_dir=tmp_path)
    io = ScriptedIO()
    engine.ensure_assets(io=io)
    assert io.text() == ""


# ── GameState integration ───────────────────────────────────────────────


def test_gamestate_default_audio_is_disabled_engine(content, warrior):
    """The default GameState construction (used by tests) gets a disabled
    engine — so callers can blindly do state.audio.play_zone(...)."""
    from terminalquest.state import GameState
    from terminalquest.ui import ScriptedIO
    state = GameState(warrior, content, ScriptedIO(), None)
    assert isinstance(state.audio, AudioEngine)
    assert state.audio.enabled is False

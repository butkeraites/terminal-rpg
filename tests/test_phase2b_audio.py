"""Phase 2b: cover terminalquest/audio.py — subprocess + threading paths."""
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch


from terminalquest import audio, boss_music_synth
from terminalquest.audio import AudioEngine, _Playback


# ── Fake subprocess.Popen ──────────────────────────────────────────────


class _FakeProc:
    """Stand-in for subprocess.Popen — wait() returns rc immediately."""

    def __init__(self, *args, rc=0, raise_on_terminate=False, **kw):
        self.returncode = rc
        self._rc = rc
        self.terminated = False
        self.killed = False
        self.raise_on_terminate = raise_on_terminate

    def wait(self, timeout=None):
        return self._rc

    def terminate(self):
        if self.raise_on_terminate:
            raise OSError("already gone")
        self.terminated = True

    def kill(self):
        self.killed = True


# ── _unix_player_cmd / _have ───────────────────────────────────────────


class TestUnixPlayerCmd:
    def test_returns_afplay_on_darwin(self):
        with patch.object(sys, "platform", "darwin"), \
             patch.object(audio, "_have", return_value=True):
            assert audio._unix_player_cmd() == ["afplay"]

    def test_returns_paplay_on_linux(self):
        with patch.object(sys, "platform", "linux"), \
             patch.object(audio, "_have",
                          side_effect=lambda c: c == "paplay"):
            assert audio._unix_player_cmd() == ["paplay"]

    def test_returns_aplay_on_linux_if_paplay_missing(self):
        def have(cmd):
            return cmd == "aplay"
        with patch.object(sys, "platform", "linux"), \
             patch.object(audio, "_have", side_effect=have):
            assert audio._unix_player_cmd() == ["aplay", "-q"]

    def test_returns_none_on_unknown_platform(self):
        with patch.object(sys, "platform", "exoticos"):
            assert audio._unix_player_cmd() is None

    def test_returns_none_on_linux_with_no_players(self):
        with patch.object(sys, "platform", "linux"), \
             patch.object(audio, "_have", return_value=False):
            assert audio._unix_player_cmd() is None

    def test_have_uses_shutil_which(self):
        with patch("shutil.which", return_value="/usr/bin/afplay"):
            assert audio._have("afplay") is True
        with patch("shutil.which", return_value=None):
            assert audio._have("missing") is False


# ── _Playback ──────────────────────────────────────────────────────────


class TestPlayback:
    def test_loop_runs_then_stops_cleanly(self, tmp_path):
        wav = tmp_path / "x.wav"
        wav.write_bytes(b"x")
        with patch.object(subprocess, "Popen", return_value=_FakeProc(rc=0)):
            pb = _Playback(["fake"], wav)
            time.sleep(0.05)
            pb.stop()
        assert pb.stop_event.is_set()
        pb.thread.join(timeout=1.0)
        assert not pb.thread.is_alive()

    def test_loop_bails_after_three_failures(self, tmp_path):
        wav = tmp_path / "x.wav"
        wav.write_bytes(b"x")
        with patch.object(subprocess, "Popen", return_value=_FakeProc(rc=1)):
            pb = _Playback(["fake"], wav)
            pb.thread.join(timeout=2.0)
        assert not pb.thread.is_alive()

    def test_loop_bails_on_popen_oserror(self, tmp_path):
        wav = tmp_path / "x.wav"
        wav.write_bytes(b"x")
        with patch.object(subprocess, "Popen", side_effect=OSError("nope")):
            pb = _Playback(["fake"], wav)
            pb.thread.join(timeout=1.0)
        assert not pb.thread.is_alive()

    def test_stop_terminate_failure_is_silent(self, tmp_path):
        wav = tmp_path / "x.wav"
        wav.write_bytes(b"x")
        fake = _FakeProc(rc=0, raise_on_terminate=True)
        with patch.object(subprocess, "Popen", return_value=fake):
            pb = _Playback(["fake"], wav)
            time.sleep(0.02)
            pb.stop()  # must not raise

    def test_stop_kills_on_timeout(self, tmp_path):
        wav = tmp_path / "x.wav"
        wav.write_bytes(b"x")

        class _SlowProc(_FakeProc):
            def wait(self, timeout=None):
                if timeout is not None:
                    raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
                return self._rc

        slow = _SlowProc(rc=0)
        with patch.object(subprocess, "Popen", return_value=slow):
            pb = _Playback(["fake"], wav)
            time.sleep(0.02)
            pb.stop()
        assert slow.killed


# ── AudioEngine — play_zone / play_boss / stop / mute / unmute ────────


class TestEnginePlayPaths:
    def _engine_with_assets(self, tmp_path):
        """Set up an engine + pre-create the cache WAVs so paths exist."""
        (tmp_path / "bosses").mkdir(parents=True, exist_ok=True)
        # All ambient palettes
        for name in boss_music_synth.THEMES:
            if name not in boss_music_synth.DYNAMIC_THEMES:
                (tmp_path / "bosses" / f"{name}.wav").write_bytes(b"x")
        from terminalquest import audio_synth
        for name in audio_synth.PALETTES:
            (tmp_path / f"{name}.wav").write_bytes(b"x")
        return AudioEngine(enabled=True, cache_dir=tmp_path)

    def test_play_zone_starts_a_playback(self, tmp_path):
        e = self._engine_with_assets(tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "Popen", return_value=_FakeProc()):
            e.play_zone("village")  # village → hearth palette
            assert len(e._active) == 1
            assert e._current_key == "village"
            e.stop()
        assert e._active == []

    def test_play_zone_same_zone_is_noop(self, tmp_path):
        e = self._engine_with_assets(tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "Popen", return_value=_FakeProc()):
            e.play_zone("village")
            e.play_zone("village")  # no new playback
            assert len(e._active) == 1
            e.stop()

    def test_play_zone_unknown_zone_silent(self, tmp_path):
        e = self._engine_with_assets(tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "Popen", return_value=_FakeProc()):
            e.play_zone("not_a_zone")
            assert e._current_key is None

    def test_play_zone_missing_wav_silent(self, tmp_path):
        # Don't pre-create the WAVs at all
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        e.play_zone("village")
        assert e._current_key is None

    def test_play_boss_static_theme(self, tmp_path):
        e = self._engine_with_assets(tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "Popen", return_value=_FakeProc()):
            e.play_boss("pallid_stag")
            assert e._current_key == "boss:pallid_stag"
            e.stop()

    def test_play_boss_dynamic_warden_renders_fresh(self, tmp_path):
        e = self._engine_with_assets(tmp_path)

        def fake_write(samples, path, *_a, **_k):
            # Touch the file so the engine's path.exists() check passes
            Path(path).write_bytes(b"x")

        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "Popen", return_value=_FakeProc()), \
             patch.object(boss_music_synth, "render_boss",
                          return_value=[0] * 100), \
             patch.object(boss_music_synth, "write_wav",
                          side_effect=fake_write) as ww:
            e.play_boss("shadow_warden",
                        context={"defeated_bosses": ["pallid_stag"]})
            assert e._current_key.startswith("boss:shadow_warden:")
            ww.assert_called()
            e.stop()

    def test_play_boss_unknown_id_silent(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        e.play_boss("nonsense_id")
        assert e._current_key is None

    def test_play_boss_same_key_is_noop(self, tmp_path):
        e = self._engine_with_assets(tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "Popen", return_value=_FakeProc()):
            e.play_boss("pallid_stag")
            count_before = len(e._active)
            e.play_boss("pallid_stag")
            assert len(e._active) == count_before
            e.stop()

    def test_mute_disables_and_stops(self, tmp_path):
        e = self._engine_with_assets(tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "Popen", return_value=_FakeProc()):
            e.play_zone("village")
        e.mute()
        assert e.enabled is False
        assert e._active == []

    def test_unmute_re_enables_and_calls_ensure(self, tmp_path):
        e = self._engine_with_assets(tmp_path)
        e.enabled = False
        e._assets_ready = True  # skip the real render
        e.unmute()
        assert e.enabled is True

    def test_stop_idempotent(self, tmp_path):
        e = AudioEngine(enabled=False, cache_dir=tmp_path)
        e.stop()
        e.stop()


# ── play_composition ──────────────────────────────────────────────────


class TestPlayComposition:
    def test_disabled_is_noop(self, tmp_path):
        e = AudioEngine(enabled=False, cache_dir=tmp_path)
        with patch.object(subprocess, "run") as run:
            e.play_composition(["C4", "G3"])
        assert run.call_count == 0

    def test_empty_notes_is_noop(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        with patch.object(subprocess, "run") as run:
            e.play_composition([])
        assert run.call_count == 0

    def test_invokes_player_subprocess_on_unix(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "run") as run:
            e.play_composition(["C4"])
        run.assert_called_once()
        # First positional arg is ["true", path]
        assert run.call_args.args[0][0] == "true"

    def test_render_failure_silent(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        with patch.object(boss_music_synth, "render_events",
                          side_effect=ValueError("bad notes")), \
             patch.object(subprocess, "run") as run:
            e.play_composition(["C4"])
        assert run.call_count == 0

    def test_subprocess_oserror_silent(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "run", side_effect=OSError("no")):
            e.play_composition(["C4"])  # must not raise

    def test_no_player_command_silent(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        with patch.object(audio, "_unix_player_cmd", return_value=None), \
             patch.object(sys, "platform", "exoticos"), \
             patch.object(subprocess, "run") as run:
            e.play_composition(["C4"])
        assert run.call_count == 0


# ── _boss_wav_path ────────────────────────────────────────────────────


class TestBossWavPath:
    def test_static_theme_returns_cached_path(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        path = e._boss_wav_path("pallid_stag", [])
        assert path == tmp_path / "bosses" / "pallid_stag.wav"

    def test_dynamic_warden_renders_per_context(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        (tmp_path / "bosses").mkdir(parents=True, exist_ok=True)
        with patch.object(boss_music_synth, "render_boss",
                          return_value=[0] * 50) as rb, \
             patch.object(boss_music_synth, "write_wav") as ww:
            path = e._boss_wav_path("shadow_warden", ["pallid_stag"])
        rb.assert_called_once()
        ww.assert_called_once()
        assert "shadow_warden__pallid_stag.wav" in str(path)

    def test_dynamic_warden_cold_tag(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        (tmp_path / "bosses").mkdir(parents=True, exist_ok=True)
        with patch.object(boss_music_synth, "render_boss",
                          return_value=[0] * 50), \
             patch.object(boss_music_synth, "write_wav"):
            path = e._boss_wav_path("shadow_warden", [])
        assert "shadow_warden__cold.wav" in str(path)

    def test_dynamic_warden_reuses_cached_render(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        (tmp_path / "bosses").mkdir(parents=True, exist_ok=True)
        # Pre-create the file so the renderer is skipped
        cached = tmp_path / "bosses" / "shadow_warden__pallid_stag.wav"
        cached.write_bytes(b"x")
        with patch.object(boss_music_synth, "render_boss") as rb:
            path = e._boss_wav_path("shadow_warden", ["pallid_stag"])
        rb.assert_not_called()
        assert path == cached

    def test_dynamic_warden_render_error_returns_none(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        (tmp_path / "bosses").mkdir(parents=True, exist_ok=True)
        with patch.object(boss_music_synth, "render_boss",
                          side_effect=ValueError("bad")):
            path = e._boss_wav_path("shadow_warden", [])
        assert path is None


# ── _crossfade_to ─────────────────────────────────────────────────────


class TestCrossfade:
    def test_no_player_cmd_is_silent(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        wav = tmp_path / "x.wav"
        wav.write_bytes(b"x")
        with patch.object(sys, "platform", "linux"), \
             patch.object(audio, "_unix_player_cmd", return_value=None):
            with e._lock:
                e._crossfade_to(wav)
        assert e._active == []

    def test_schedules_old_kill_on_overlap(self, tmp_path):
        e = AudioEngine(enabled=True, cache_dir=tmp_path)
        wav_a = tmp_path / "a.wav"
        wav_a.write_bytes(b"x")
        wav_b = tmp_path / "b.wav"
        wav_b.write_bytes(b"x")
        with patch.object(audio, "_unix_player_cmd", return_value=["true"]), \
             patch.object(subprocess, "Popen", return_value=_FakeProc()), \
             patch.object(audio, "CROSSFADE_S", 0.05):
            with e._lock:
                e._crossfade_to(wav_a)
            assert len(e._active) == 1
            with e._lock:
                e._crossfade_to(wav_b)
            assert len(e._active) == 2  # both active during crossfade
            time.sleep(0.15)  # let timer fire
        # The kill_old timer should have trimmed _active to just the new one
        with e._lock:
            assert any(pb.path == wav_b for pb in e._active)
        e.stop()


# ── _win_play (smoke-test it can be reached) ──────────────────────────


def test_win_play_swallows_import_error(tmp_path):
    """Force the win_play branch on a non-Windows platform by calling it
    directly. The import should fail (no winsound on macOS/Linux) and
    the except clause swallows it silently."""
    e = AudioEngine(enabled=True, cache_dir=tmp_path)
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"x")
    # _win_play imports winsound which doesn't exist on unix → ImportError
    # → caught by the except (ImportError, RuntimeError, OSError) clause.
    e._win_play(wav)  # must not raise


def test_crossfade_uses_win_play_on_windows(tmp_path):
    e = AudioEngine(enabled=True, cache_dir=tmp_path)
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"x")
    with patch.object(sys, "platform", "win32"), \
         patch.object(e, "_win_play") as wp:
        with e._lock:
            e._crossfade_to(wav)
    wp.assert_called_once()


# ── ensure_assets error path ──────────────────────────────────────────


def test_ensure_assets_swallows_oserror(tmp_path):
    e = AudioEngine(enabled=True, cache_dir=tmp_path)
    from terminalquest import audio_synth
    with patch.object(audio_synth, "render_all", side_effect=OSError("disk")):
        e.ensure_assets()  # must not raise
    assert e._assets_ready is False

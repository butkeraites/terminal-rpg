"""Ambient audio engine — opt-in, fails silently, no new dependencies.

The engine plays one looping zone drone at a time. Backed by the OS's
built-in CLI player (``afplay`` on macOS, ``paplay``/``aplay`` on Linux)
or stdlib ``winsound`` on Windows. If none of those are available the
engine becomes a no-op — the game runs without sound and never crashes.

Assets are generated once into ``~/.terminalquest/audio/`` by
``audio_synth.render_all()``. Zero binary audio ships in the repo.

Usage:
    engine = AudioEngine(enabled=True)
    engine.ensure_assets()       # one-time WAV synthesis
    engine.play_zone("forest")   # crossroads → forest, fades automatically
    engine.stop()                # on quit
"""
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from . import audio_synth

CACHE_DIR = Path.home() / ".terminalquest" / "audio"


def _have(cmd):
    return shutil.which(cmd) is not None


def _unix_player_cmd():
    """Return the player command (list of args) for unix-likes, or None."""
    if sys.platform == "darwin" and _have("afplay"):
        return ["afplay"]
    if sys.platform.startswith("linux"):
        if _have("paplay"):
            return ["paplay"]
        if _have("aplay"):
            return ["aplay", "-q"]
    return None


class AudioEngine:
    """Plays one looping zone drone at a time. Thread-safe, silent on error."""

    def __init__(self, enabled=False, cache_dir=None):
        self.enabled = enabled
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self._lock = threading.Lock()
        self._current_zone = None
        self._stop_event = threading.Event()
        self._thread = None
        self._proc = None
        self._assets_ready = False

    # ── lifecycle ──────────────────────────────────────────────────────

    def ensure_assets(self, io=None):
        """Render every palette WAV into the cache if missing.

        Idempotent. Safe to call on every launch. Takes ~3 s the first
        time (pure-Python synthesis of 7 short clips), instant after.
        Failure is silent — the engine just stays quiet if rendering
        fails for any reason.

        Pass ``io`` to surface a one-line message when the first-launch
        synthesis is about to happen — so the ~3-s pause doesn't look like
        a hang. Works through CursesIO too, so this is safe in TUI mode.
        """
        if not self.enabled or self._assets_ready:
            return
        missing = any(
            not (self.cache_dir / f"{name}.wav").exists()
            for name in audio_synth.PALETTES
        )
        if missing and io is not None:
            io.show("\nPreparing the kingdom's sound… (first launch only)")
        try:
            audio_synth.render_all(out_dir=self.cache_dir)
        except OSError:
            return
        self._assets_ready = True

    # ── playback ───────────────────────────────────────────────────────

    def play_zone(self, zone_id):
        """Switch to the drone for ``zone_id``. No-op if already on it,
        if the zone has no palette, or if the engine is disabled."""
        if not self.enabled:
            return
        palette = audio_synth.ZONE_PALETTE.get(zone_id)
        if palette is None:
            return
        with self._lock:
            if zone_id == self._current_zone:
                return
            self._stop_unlocked()
            path = self.cache_dir / f"{palette}.wav"
            if not path.exists():
                return
            self._current_zone = zone_id
            self._stop_event.clear()
            self._spawn(path)

    def stop(self):
        """Stop the current drone, if any."""
        with self._lock:
            self._stop_unlocked()

    def mute(self):
        self.enabled = False
        self.stop()

    def unmute(self, io=None):
        self.enabled = True
        self.ensure_assets(io=io)

    # ── internals ──────────────────────────────────────────────────────

    def _stop_unlocked(self):
        """Stop without taking the lock. Caller must hold ``self._lock``."""
        self._stop_event.set()
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except (OSError, ValueError):
                pass
        # If a winsound was started, stop it.
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except (ImportError, RuntimeError):
                pass
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=0.5)
        self._current_zone = None

    def _spawn(self, path):
        """Start playback. Caller must hold ``self._lock``."""
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
                )
            except (ImportError, RuntimeError, OSError):
                pass
            return
        cmd = _unix_player_cmd()
        if cmd is None:
            return
        # afplay/paplay don't loop natively, so re-spawn from a daemon thread.
        # The thread exits when _stop_event is set OR when the player exits
        # repeatedly without producing audio (gives up after 3 failures).
        self._thread = threading.Thread(
            target=self._loop, args=(cmd, path), daemon=True)
        self._thread.start()

    def _loop(self, cmd, path):
        failures = 0
        while not self._stop_event.is_set():
            try:
                proc = subprocess.Popen(
                    cmd + [str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            except (OSError, ValueError):
                return
            with self._lock:
                # Only record the proc if we're still the active thread —
                # a concurrent stop()/play_zone() may have superseded us.
                if threading.current_thread() is not self._thread:
                    try:
                        proc.terminate()
                    except OSError:
                        pass
                    return
                self._proc = proc
            try:
                rc = proc.wait()
            except (OSError, ValueError):
                return
            if rc != 0:
                failures += 1
                if failures >= 3:
                    return
            # tight loop guard — if the player exits instantly, don't busy-spin
            if self._stop_event.wait(0.02):
                return

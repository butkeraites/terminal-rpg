"""Ambient + boss + composition audio engine — opt-in, fails silently.

Two kinds of audio:

  * **Ambient zone drones** — one per palette (7 palettes cover 22 zones).
    Cached as WAVs in ``~/.terminalquest/audio/`` on first launch.
  * **Boss themes** — eight lore-driven, modal compositions. Cached in
    ``~/.terminalquest/audio/bosses/``. The Shadow Warden is dynamic —
    re-rendered per fight from the list of bosses the player has actually
    defeated this run (it quotes only those).

Playback is backed by the OS's built-in CLI player (``afplay`` on macOS,
``paplay``/``aplay`` on Linux) or stdlib ``winsound`` on Windows. If none
of those are available the engine becomes a no-op — the game runs without
sound and never crashes.

Track transitions (ambient → boss → ambient) are crossfaded by spawning
the new player and scheduling the old to die ~1 s later. Both tracks have
built-in 0.5 s fades, so the overlap reads as one fading into the other.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import audio_synth, boss_music_synth

if TYPE_CHECKING:
    from .ui import GameIO

CACHE_DIR = Path.home() / ".terminalquest" / "audio"
CROSSFADE_S = 1.0


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _unix_player_cmd() -> list[str] | None:
    """Return the player command (list of args) for unix-likes, or None."""
    if sys.platform == "darwin" and _have("afplay"):
        return ["afplay"]
    if sys.platform.startswith("linux"):
        if _have("paplay"):
            return ["paplay"]
        if _have("aplay"):
            return ["aplay", "-q"]
    return None


class _Playback:
    """One running loop — a thread that respawns the player on exit until
    stop() is called. Failures are silent."""

    cmd: list[str]
    path: Path
    stop_event: threading.Event
    proc: subprocess.Popen[bytes] | None
    thread: threading.Thread

    def __init__(self, cmd: list[str], path: Path) -> None:
        self.cmd = cmd
        self.path = path
        self.stop_event = threading.Event()
        self.proc = None
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self) -> None:
        failures = 0
        while not self.stop_event.is_set():
            try:
                self.proc = subprocess.Popen(
                    self.cmd + [str(self.path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            except (OSError, ValueError):
                return
            try:
                rc = self.proc.wait()
            except (OSError, ValueError):
                return
            if rc != 0:
                failures += 1
                if failures >= 3:
                    return
            # tight loop guard — if the player exits instantly, don't busy-spin
            if self.stop_event.wait(0.02):
                return

    def stop(self) -> None:
        self.stop_event.set()
        proc, self.proc = self.proc, None
        if proc is not None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except (OSError, ValueError):
                pass


class AudioEngine:
    """Plays one looping track at a time (ambient drone or boss theme).
    Thread-safe, silent on error, supports crossfade between tracks."""

    enabled: bool
    cache_dir: Path

    def __init__(
        self,
        enabled: bool = False,
        cache_dir: Path | str | None = None,
    ) -> None:
        self.enabled = enabled
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self._lock = threading.Lock()
        # All currently-spawned playbacks. Usually one; during crossfade,
        # two for ~1 s. Newest at the end.
        self._active = []
        # Identifier for "what's playing right now" — used to short-circuit
        # repeated calls to the same track. For ambient: the zone id. For
        # boss: "boss:<id>" or "boss:<id>:<context-hash>" for dynamic themes.
        self._current_key = None
        self._assets_ready = False

    # ── lifecycle ──────────────────────────────────────────────────────

    def ensure_assets(self, io: GameIO | None = None) -> None:
        """Render every palette + non-dynamic boss WAV into the cache if
        missing. Idempotent. Failure is silent.

        Pass ``io`` to surface a one-line message when first-launch
        synthesis is about to happen — so the ~3-s pause doesn't look like
        a hang. Works through CursesIO too.
        """
        if not self.enabled or self._assets_ready:
            return
        missing_ambient = any(
            not (self.cache_dir / f"{name}.wav").exists()
            for name in audio_synth.PALETTES
        )
        bosses_dir = self.cache_dir / "bosses"
        missing_boss = any(
            not (bosses_dir / f"{boss_id}.wav").exists()
            for boss_id in boss_music_synth.THEMES
            if boss_id not in boss_music_synth.DYNAMIC_THEMES
        )
        if (missing_ambient or missing_boss) and io is not None:
            io.show("\nPreparing the kingdom's sound… (first launch only)")
        try:
            audio_synth.render_all(out_dir=self.cache_dir)
            boss_music_synth.render_all_to(out_dir=bosses_dir)
        except OSError:
            return
        self._assets_ready = True

    # ── playback ───────────────────────────────────────────────────────

    def play_zone(self, zone_id: str) -> None:
        """Switch to the drone for ``zone_id``. Crossfades from whatever
        is playing now. No-op if already on it or if disabled."""
        if not self.enabled:
            return
        palette = audio_synth.ZONE_PALETTE.get(zone_id)
        if palette is None:
            return
        path = self.cache_dir / f"{palette}.wav"
        if not path.exists():
            return
        with self._lock:
            if zone_id == self._current_key:
                return
            self._current_key = zone_id
            self._crossfade_to(path)

    def play_boss(
        self,
        boss_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Switch to the boss theme. ``context`` is an optional dict; for
        the Shadow Warden, ``context['defeated_bosses']`` is the list of
        enemy ids defeated this run — the Warden quotes only those.

        No-op if the boss has no theme, if already playing this track, or
        if the engine is disabled.
        """
        if not self.enabled:
            return
        if boss_id not in boss_music_synth.BOSS_IDS:
            return
        defeated = sorted((context or {}).get("defeated_bosses", []))
        path = self._boss_wav_path(boss_id, defeated)
        if path is None or not path.exists():
            return
        if boss_id in boss_music_synth.DYNAMIC_THEMES:
            key = f"boss:{boss_id}:{','.join(defeated)}"
        else:
            key = f"boss:{boss_id}"
        with self._lock:
            if key == self._current_key:
                return
            self._current_key = key
            self._crossfade_to(path)

    def stop(self) -> None:
        """Stop all playbacks immediately. Idempotent."""
        with self._lock:
            for playback in self._active:
                playback.stop()
            self._active = []
            self._current_key = None

    def play_composition(
        self,
        notes: list[str],
        voice: str = "voice",
        note_seconds: float = 0.7,
    ) -> None:
        """Play a one-shot melody synchronously, layered over whatever is
        currently playing. Used by the composer for melody quests — the
        player hears their typed notes immediately, then continues.

        Disabled engine, empty note list, or missing player command: no-op.
        """
        if not self.enabled or not notes:
            return
        events = [
            (i * note_seconds, voice, note, note_seconds * 1.5, 0.85)
            for i, note in enumerate(notes)
        ]
        duration = len(notes) * note_seconds + 1.0
        try:
            samples = boss_music_synth.render_events(events, duration)
        except (KeyError, ValueError):
            return
        handle, path = tempfile.mkstemp(suffix=".wav")
        os.close(handle)
        try:
            boss_music_synth.write_wav(samples, path)
            cmd = _unix_player_cmd()
            if cmd is not None:
                try:
                    subprocess.run(
                        cmd + [str(path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                except (OSError, ValueError):
                    pass
            elif sys.platform == "win32":
                try:
                    import winsound
                    winsound.PlaySound(str(path), winsound.SND_FILENAME)
                except (ImportError, RuntimeError, OSError):
                    pass
        finally:
            try:
                Path(path).unlink()
            except OSError:
                pass

    def mute(self) -> None:
        self.enabled = False
        self.stop()

    def unmute(self, io: GameIO | None = None) -> None:
        self.enabled = True
        self.ensure_assets(io=io)

    # ── internals ──────────────────────────────────────────────────────

    def _boss_wav_path(
        self,
        boss_id: str,
        defeated_bosses: list[str],
    ) -> Path | None:
        """Resolve the WAV path for a boss. Renders dynamic themes fresh."""
        bosses_dir = self.cache_dir / "bosses"
        if boss_id in boss_music_synth.DYNAMIC_THEMES:
            # Re-render every time the context changes. Filename derived
            # from a stable key so re-entering the fight with the same
            # context reuses the file (skips synthesis).
            tag = "_".join(defeated_bosses) if defeated_bosses else "cold"
            path = bosses_dir / f"{boss_id}__{tag}.wav"
            if not path.exists():
                try:
                    samples = boss_music_synth.render_boss(
                        boss_id, defeated_bosses=defeated_bosses)
                    boss_music_synth.write_wav(samples, path)
                except (OSError, ValueError):
                    return None
            return path
        return bosses_dir / f"{boss_id}.wav"

    def _crossfade_to(self, path: Path) -> None:
        """Start a new playback; schedule current ones to die after CROSSFADE_S.
        Caller must hold ``self._lock``."""
        if sys.platform == "win32":
            self._win_play(path)
            return
        cmd = _unix_player_cmd()
        if cmd is None:
            return
        new = _Playback(cmd, path)
        old = self._active
        self._active = [new] + old
        if old:
            def _kill_old():
                for playback in old:
                    playback.stop()
                with self._lock:
                    # Trim killed playbacks from _active so the list doesn't grow
                    if old and self._active:
                        self._active = [p for p in self._active if p not in old]
            threading.Timer(CROSSFADE_S, _kill_old).start()

    def _win_play(self, path: Path) -> None:
        """Windows fallback — winsound is single-track, no crossfade. Hard
        cut: stop everything, then play. Caller must hold ``self._lock``."""
        for playback in self._active:
            playback.stop()
        self._active = []
        try:
            import winsound
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
            )
        except (ImportError, RuntimeError, OSError):
            pass

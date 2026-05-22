"""Persistent user settings stored alongside the Chronicle.

A small JSON at ``~/.terminalquest/settings.json`` keeps choices that
should outlive a run but don't belong in the Chronicle — chiefly the
emoji-rendering preference set by the first-launch smoke test.
"""
import json
import os
import tempfile
from pathlib import Path

DEFAULT_DIR = Path.home() / ".terminalquest"
_FILENAME = "settings.json"

DEFAULTS = {
    "ascii_mode": False,        # render emojis as bracket-text instead of glyphs
    "emoji_test_done": False,   # first-launch smoke test has been answered
    "audio_enabled": False,     # play per-zone ambient drones (opt-in)
}


def _path(settings_dir):
    return Path(settings_dir) / _FILENAME


def load(settings_dir=DEFAULT_DIR):
    """Return the user's settings, defaulting any missing keys."""
    try:
        raw = json.loads(_path(settings_dir).read_text(encoding="utf-8"))
        return {**DEFAULTS, **{k: raw[k] for k in DEFAULTS if k in raw}}
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return dict(DEFAULTS)


def save(settings, settings_dir=DEFAULT_DIR):
    """Atomically write settings. Any failure is swallowed."""
    try:
        sdir = Path(settings_dir)
        sdir.mkdir(parents=True, exist_ok=True)
        handle, tmp = tempfile.mkstemp(dir=sdir, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(settings, fh, indent=2)
            os.replace(tmp, _path(sdir))
        except OSError:
            Path(tmp).unlink(missing_ok=True)
    except OSError:
        pass

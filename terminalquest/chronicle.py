"""The Chronicle of the Fallen — a local record of past characters.

When a run ends — the player falls, or breaks the Pall — that character
is appended to ``chronicle.json``, so later runs can feel them: named at
character creation, found as graves where they fell, or risen as the
Hollowed.

The chronicle is a keepsake, never load-bearing: a missing or corrupt
file simply reads as no past characters, and a failed write is swallowed.
"""
import json
import os
import tempfile
from pathlib import Path

CHRONICLE_VERSION = 1
DEFAULT_DIR = Path.home() / ".terminalquest"
_FILENAME = "chronicle.json"


def _path(chronicle_dir):
    return Path(chronicle_dir) / _FILENAME


def load(chronicle_dir=DEFAULT_DIR):
    """Return recorded characters, oldest first. Never raises."""
    try:
        data = json.loads(_path(chronicle_dir).read_text(encoding="utf-8"))
        entries = data["entries"]
        return list(entries) if isinstance(entries, list) else []
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return []


def record(state, fate, chronicle_dir=DEFAULT_DIR):
    """Append the current character to the chronicle.

    ``fate`` is 'fell' or 'triumphed'. The write is atomic; any failure
    is swallowed — a keepsake is not worth crashing the end of a run over.
    """
    entry = {
        "fate": fate,
        "location": state.current_location,
        "player": state.player.to_dict(),
    }
    payload = {
        "version": CHRONICLE_VERSION,
        "entries": load(chronicle_dir) + [entry],
    }
    try:
        cdir = Path(chronicle_dir)
        cdir.mkdir(parents=True, exist_ok=True)
        handle, tmp = tempfile.mkstemp(dir=cdir, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, _path(cdir))
        except OSError:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError:
        pass


def fallen(entries):
    """The subset of entries for characters who died (not victors)."""
    return [e for e in entries if e.get("fate") == "fell"]

"""The Chronicle of the Fallen — a local record of past characters.

When a run ends — the player falls, or breaks the Warden and is kept by
the Pall as the next one — that character is appended to ``chronicle.json``,
so later runs can feel them: named at character creation, found as graves
where they fell, risen as the Hollowed, or faced at the Summit as the
Shadow Warden they became.

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


def _write(payload, chronicle_dir):
    """Atomically write the chronicle. Any failure is swallowed."""
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


def record(state, fate, chronicle_dir=DEFAULT_DIR):
    """Append the current character to the chronicle.

    ``fate`` is 'fell' (died) or 'warden' (broke the Warden and was kept
    by the Pall as the next one). The write is atomic; failure is swallowed.
    """
    entry = {
        "fate": fate,
        "location": state.current_location,
        "seed": state.seed,
        "player": state.player.to_dict(),
    }
    _write({"version": CHRONICLE_VERSION, "entries": load(chronicle_dir) + [entry]},
           chronicle_dir)


def lay_to_rest(entry, chronicle_dir=DEFAULT_DIR):
    """Mark a fallen character as freed — they no longer rise as the Hollowed."""
    entries = load(chronicle_dir)
    for stored in entries:
        if stored == entry:
            stored["resolved"] = True
    _write({"version": CHRONICLE_VERSION, "entries": entries}, chronicle_dir)


def fallen(entries):
    """Characters who died and have not yet been laid to rest."""
    return [e for e in entries
            if e.get("fate") == "fell" and not e.get("resolved")]


def wardens(entries):
    """Characters the Pall kept — past victors, now the Shadow Warden."""
    return [e for e in entries if e.get("fate") == "warden"]

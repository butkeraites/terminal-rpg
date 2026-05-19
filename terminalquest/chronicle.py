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


def _load_raw(chronicle_dir):
    """Return the whole chronicle as ``{entries, unlocks}``. Never raises."""
    try:
        data = json.loads(_path(chronicle_dir).read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        unlocks = data.get("unlocks", [])
        return {
            "entries": list(entries) if isinstance(entries, list) else [],
            "unlocks": list(unlocks) if isinstance(unlocks, list) else [],
        }
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return {"entries": [], "unlocks": []}


def load(chronicle_dir=DEFAULT_DIR):
    """Return recorded characters, oldest first. Never raises."""
    return _load_raw(chronicle_dir)["entries"]


def unlocked(chronicle_dir=DEFAULT_DIR):
    """Return the set of tokens permanently unlocked across runs. Never raises."""
    return set(_load_raw(chronicle_dir)["unlocks"])


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


def _save(raw, chronicle_dir):
    """Atomically write the whole chronicle (``{entries, unlocks}``)."""
    _write({"version": CHRONICLE_VERSION,
            "entries": raw["entries"], "unlocks": raw["unlocks"]}, chronicle_dir)


def record(state, fate, chronicle_dir=DEFAULT_DIR):
    """Append the current character to the chronicle.

    ``fate`` is 'fell' (died) or 'warden' (broke the Warden and was kept
    by the Pall as the next one). The write is atomic; failure is swallowed.
    """
    raw = _load_raw(chronicle_dir)
    raw["entries"].append({
        "fate": fate,
        "location": state.current_location,
        "seed": state.seed,
        "player": state.player.to_dict(),
    })
    _save(raw, chronicle_dir)


def lay_to_rest(entry, chronicle_dir=DEFAULT_DIR):
    """Mark a fallen character as freed — they no longer rise as the Hollowed."""
    raw = _load_raw(chronicle_dir)
    for stored in raw["entries"]:
        if stored == entry:
            stored["resolved"] = True
    _save(raw, chronicle_dir)


def unlock(token, chronicle_dir=DEFAULT_DIR):
    """Permanently unlock ``token`` across all future runs. Idempotent."""
    raw = _load_raw(chronicle_dir)
    if token not in raw["unlocks"]:
        raw["unlocks"].append(token)
        _save(raw, chronicle_dir)


def fallen(entries):
    """Characters who died and have not yet been laid to rest."""
    return [e for e in entries
            if e.get("fate") == "fell" and not e.get("resolved")]


def wardens(entries):
    """Characters the Pall kept — past victors, now the Shadow Warden."""
    return [e for e in entries if e.get("fate") == "warden"]

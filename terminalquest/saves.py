"""Save-game persistence.

Saves are schema-versioned JSON written atomically (temp file + replace)
to ``~/.terminalquest/saves`` by default. The directory is overridable so
tests can use a temporary path. No third-party dependencies — the game
stays hermetic.

A save stores a whole ``GameState`` (the player plus the current location
and world flags). ``_migrate`` upgrades older payloads forward in place.
"""
import json
import os
import tempfile
from pathlib import Path

from .state import GameState

SAVE_VERSION = 2
DEFAULT_SAVE_DIR = Path.home() / ".terminalquest" / "saves"
SLOTS = (1, 2, 3)


class SaveError(ValueError):
    """Raised when a save file exists but cannot be read or migrated."""


def _slot_path(slot, save_dir):
    return Path(save_dir) / f"slot{slot}.json"


def _migrate(data):
    """Upgrade an older save payload to the current schema in place.

    New cases are added here as ``SAVE_VERSION`` grows.
    """
    version = data.get("save_version", 0)
    if version > SAVE_VERSION:
        raise ValueError(
            f"save is version {version}; this game supports up to {SAVE_VERSION}"
        )
    if version <= 1:
        # v1 stored a bare player; v2 wraps it in a GameState payload.
        player = data.pop("player", {})
        player.pop("position", None)  # v1's vestigial field, dropped in v2
        data["state"] = {
            "current_location": "crossroads",
            "flags": {},
            "player": player,
        }
    data["save_version"] = SAVE_VERSION
    return data


def save_game(state, slot, save_dir=DEFAULT_SAVE_DIR):
    """Write ``state`` to ``slot``, replacing any existing save atomically."""
    if slot not in SLOTS:
        raise ValueError(f"invalid save slot {slot}")
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    payload = {"save_version": SAVE_VERSION, "state": state.to_dict()}

    handle, tmp_name = tempfile.mkstemp(dir=save_dir, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as tmp:
            json.dump(payload, tmp, indent=2)
        os.replace(tmp_name, _slot_path(slot, save_dir))
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def load_game(slot, content, io, rng, save_dir=DEFAULT_SAVE_DIR):
    """Load and return the GameState from ``slot``, or None if the slot is empty.

    Raises ``SaveError`` if the slot holds a file that cannot be parsed.
    """
    path = _slot_path(slot, Path(save_dir))
    if not path.exists():
        return None
    try:
        data = _migrate(json.loads(path.read_text(encoding="utf-8")))
        return GameState.from_dict(data["state"], content, io, rng)
    except (KeyError, ValueError) as exc:
        raise SaveError(f"save slot {slot} could not be loaded: {exc}") from exc


def list_saves(save_dir=DEFAULT_SAVE_DIR):
    """Return ``{slot: summary_string}`` for every occupied slot."""
    summaries = {}
    for slot in SLOTS:
        path = _slot_path(slot, Path(save_dir))
        if not path.exists():
            continue
        try:
            data = _migrate(json.loads(path.read_text(encoding="utf-8")))
            p = data["state"]["player"]
            summaries[slot] = (f"{p['name']} the {p['class_name']} "
                               f"- Level {p['level']}")
        except (json.JSONDecodeError, KeyError, ValueError):
            summaries[slot] = "(corrupt save)"
    return summaries


def delete_save(slot, save_dir=DEFAULT_SAVE_DIR):
    """Remove the save in ``slot`` if it exists."""
    _slot_path(slot, Path(save_dir)).unlink(missing_ok=True)

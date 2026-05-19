"""Save-game persistence.

Saves are schema-versioned JSON written atomically (temp file + replace)
to ``~/.terminalquest/saves`` by default. The directory is overridable so
tests can use a temporary path. No third-party dependencies — the game
stays hermetic.
"""
import json
import os
import tempfile
from pathlib import Path

from .player import Player

SAVE_VERSION = 1
DEFAULT_SAVE_DIR = Path.home() / ".terminalquest" / "saves"
SLOTS = (1, 2, 3)


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
    # No migrations needed yet — version 1 is the first schema.
    data["save_version"] = SAVE_VERSION
    return data


def save_game(player, slot, save_dir=DEFAULT_SAVE_DIR):
    """Write the player to ``slot``, replacing any existing save atomically."""
    if slot not in SLOTS:
        raise ValueError(f"invalid save slot {slot}")
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    payload = {"save_version": SAVE_VERSION, "player": player.to_dict()}

    handle, tmp_name = tempfile.mkstemp(dir=save_dir, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as tmp:
            json.dump(payload, tmp, indent=2)
        os.replace(tmp_name, _slot_path(slot, save_dir))
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def load_game(slot, save_dir=DEFAULT_SAVE_DIR):
    """Load and return the Player from ``slot``, or None if the slot is empty."""
    path = _slot_path(slot, Path(save_dir))
    if not path.exists():
        return None
    data = _migrate(json.loads(path.read_text(encoding="utf-8")))
    return Player.from_dict(data["player"])


def list_saves(save_dir=DEFAULT_SAVE_DIR):
    """Return ``{slot: summary_string}`` for every occupied slot."""
    summaries = {}
    for slot in SLOTS:
        path = _slot_path(slot, Path(save_dir))
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            p = data["player"]
            summaries[slot] = (f"{p['name']} the {p['class_name']} "
                               f"- Level {p['level']}")
        except (json.JSONDecodeError, KeyError):
            summaries[slot] = "(corrupt save)"
    return summaries


def delete_save(slot, save_dir=DEFAULT_SAVE_DIR):
    """Remove the save in ``slot`` if it exists."""
    _slot_path(slot, Path(save_dir)).unlink(missing_ok=True)

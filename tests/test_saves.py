"""Save-game persistence: round-trips, slots and version handling."""
import json

import pytest

from terminalquest import saves


def test_save_load_round_trip(tmp_path, warrior):
    warrior.gain_xp(120)
    warrior.inventory.append("Health Potion")
    saves.save_game(warrior, 1, save_dir=tmp_path)
    loaded = saves.load_game(1, save_dir=tmp_path)
    assert loaded.to_dict() == warrior.to_dict()


def test_load_empty_slot_returns_none(tmp_path):
    assert saves.load_game(2, save_dir=tmp_path) is None


def test_list_saves_summarizes_occupied_slots(tmp_path, warrior):
    saves.save_game(warrior, 3, save_dir=tmp_path)
    listed = saves.list_saves(save_dir=tmp_path)
    assert 3 in listed
    assert warrior.name in listed[3]


def test_delete_save(tmp_path, warrior):
    saves.save_game(warrior, 1, save_dir=tmp_path)
    saves.delete_save(1, save_dir=tmp_path)
    assert saves.load_game(1, save_dir=tmp_path) is None


def test_invalid_slot_is_rejected(tmp_path, warrior):
    with pytest.raises(ValueError):
        saves.save_game(warrior, 9, save_dir=tmp_path)


def test_future_save_version_is_rejected(tmp_path, warrior):
    saves.save_game(warrior, 1, save_dir=tmp_path)
    path = tmp_path / "slot1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["save_version"] = 999
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        saves.load_game(1, save_dir=tmp_path)

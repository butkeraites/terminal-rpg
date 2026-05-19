"""Save-game persistence: round-trips, slots and version handling."""
import json

import pytest
from conftest import StubRandom, make_state

from terminalquest import saves
from terminalquest.ui import ScriptedIO
from terminalquest.weapon import make_weapon


def _load(slot, content, tmp_path):
    return saves.load_game(slot, content, ScriptedIO(), StubRandom(), save_dir=tmp_path)


def test_save_load_round_trip(tmp_path, content, warrior):
    warrior.gain_xp(120)
    warrior.consumables.append("Health Potion")
    state = make_state(warrior, content, current_location="forest")
    saves.save_game(state, 1, save_dir=tmp_path)
    loaded = _load(1, content, tmp_path)
    assert loaded.to_dict() == state.to_dict()


def test_load_empty_slot_returns_none(tmp_path, content):
    assert _load(2, content, tmp_path) is None


def test_list_saves_summarizes_occupied_slots(tmp_path, content, warrior):
    saves.save_game(make_state(warrior, content), 3, save_dir=tmp_path)
    listed = saves.list_saves(save_dir=tmp_path)
    assert 3 in listed
    assert warrior.name in listed[3]


def test_delete_save(tmp_path, content, warrior):
    saves.save_game(make_state(warrior, content), 1, save_dir=tmp_path)
    saves.delete_save(1, save_dir=tmp_path)
    assert _load(1, content, tmp_path) is None


def test_invalid_slot_is_rejected(tmp_path, content, warrior):
    with pytest.raises(ValueError):
        saves.save_game(make_state(warrior, content), 9, save_dir=tmp_path)


def test_future_save_version_is_rejected(tmp_path, content, warrior):
    saves.save_game(make_state(warrior, content), 1, save_dir=tmp_path)
    path = tmp_path / "slot1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["save_version"] = 999
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        _load(1, content, tmp_path)


def test_migrates_v1_save_forward(tmp_path, content, warrior):
    """A legacy v1 payload (bare player, position, flat inventory) migrates forward."""
    v1_player = warrior.to_dict()
    v1_player["inventory"] = v1_player.pop("consumables")  # v1's flat field
    del v1_player["equipment"]                             # v1 had no equipment
    v1_player["position"] = "world"                        # v1's vestigial field
    legacy = {"save_version": 1, "player": v1_player}
    (tmp_path / "slot1.json").write_text(json.dumps(legacy), encoding="utf-8")
    loaded = _load(1, content, tmp_path)
    assert loaded.current_location == "crossroads"
    assert loaded.flags == {}
    assert loaded.player.name == warrior.name
    assert loaded.player.consumables == warrior.consumables
    assert loaded.player.equipment == {}


def test_migrates_v2_save_to_v3(tmp_path, content, warrior):
    """A v2 payload (player.inventory) migrates to v3 — consumables plus equipment."""
    v2_player = warrior.to_dict()
    v2_player["inventory"] = v2_player.pop("consumables")
    del v2_player["equipment"]
    legacy = {"save_version": 2,
              "state": {"current_location": "forest", "flags": {},
                        "player": v2_player}}
    (tmp_path / "slot1.json").write_text(json.dumps(legacy), encoding="utf-8")
    loaded = _load(1, content, tmp_path)
    assert loaded.current_location == "forest"
    assert loaded.player.consumables == warrior.consumables
    assert loaded.player.equipment == {}


def test_corrupt_save_raises_save_error(tmp_path, content):
    """A slot holding unparseable data raises SaveError, not a raw crash."""
    (tmp_path / "slot1.json").write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(saves.SaveError):
        _load(1, content, tmp_path)


def test_save_round_trips_an_equipped_weapon(tmp_path, content, warrior):
    """An equipped weapon survives a save/load cycle with its stats intact."""
    weapon = make_weapon(content, {"head": "reliquary_edge", "haft": "weir_pole",
                                   "core": "pall_glass_core",
                                   "inscription": "unremembered_name"}, "Probe")
    warrior.equip_weapon(weapon)
    state = make_state(warrior, content)
    saves.save_game(state, 1, save_dir=tmp_path)
    loaded = _load(1, content, tmp_path)
    assert loaded.player.equipment["weapon"].name == "Probe"
    assert loaded.player.equipment["weapon"].stats == weapon.stats
    assert loaded.to_dict() == state.to_dict()

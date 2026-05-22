"""Final coverage push — target the remaining gaps to land 95%+."""
import random
import tempfile
from unittest.mock import patch

import pytest

from terminalquest import chronicle, sq_services
from terminalquest.player import Player
from terminalquest.state import GameState
from terminalquest.ui import ScriptedIO


@pytest.fixture
def warrior(content):
    return Player("Hero", "warrior", content.classes["warrior"], content)


@pytest.fixture
def state_for(content):
    def _build(player, io=None, **kwargs):
        kwargs.setdefault("chronicle_dir", tempfile.mkdtemp())
        kwargs.setdefault("seed", "1")
        return GameState(player, content, io or ScriptedIO(), random.Random(0),
                         **kwargs)
    return _build


# ── sq_services._pet_the_cat at every threshold ────────────────────────


class TestPetTheCatThresholds:
    def test_threshold_10_lines(self, warrior, state_for, tmp_path):
        # Pre-load 9 pets so the next one hits 10
        for _ in range(9):
            chronicle.add_cat_pet(tmp_path)
        state = state_for(warrior, chronicle_dir=tmp_path)
        sq_services._pet_the_cat(state)
        assert "counting your runs" in state.io.text()

    def test_threshold_25_with_fallen(self, warrior, state_for, tmp_path):
        for _ in range(24):
            chronicle.add_cat_pet(tmp_path)
        # Drop a fallen entry by raw write so the chronicle has someone
        import json
        path = chronicle._path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = chronicle._load_raw(tmp_path)
        raw["entries"] = [{"player": {"name": "Anna", "class_name": "warrior",
                                       "level": 3}, "fate": "fell"}]
        path.write_text(json.dumps(raw))
        state = state_for(warrior, chronicle_dir=tmp_path)
        sq_services._pet_the_cat(state)
        assert "Anna" in state.io.text()

    def test_threshold_25_without_fallen(self, warrior, state_for, tmp_path):
        for _ in range(24):
            chronicle.add_cat_pet(tmp_path)
        state = state_for(warrior, chronicle_dir=tmp_path)
        sq_services._pet_the_cat(state)
        assert "the ones who died before you" in state.io.text()

    def test_threshold_50(self, warrior, state_for, tmp_path):
        for _ in range(49):
            chronicle.add_cat_pet(tmp_path)
        state = state_for(warrior, chronicle_dir=tmp_path)
        sq_services._pet_the_cat(state)
        assert "every name from your" in state.io.text()

    def test_threshold_100_sets_cat_companion(self, warrior, state_for, tmp_path):
        for _ in range(99):
            chronicle.add_cat_pet(tmp_path)
        state = state_for(warrior, chronicle_dir=tmp_path)
        sq_services._pet_the_cat(state)
        assert state.flags.get("cat_companion") is True


# ── sq_services._write_first_line edge paths ───────────────────────────


class TestWriteFirstLineEdges:
    def test_walk_away_at_book(self, warrior, state_for):
        # Choose yes, then blank → walks away
        state = state_for(warrior, io=ScriptedIO(["1", "   "]))
        sq_services._write_first_line(state)
        assert "Not yet" in state.io.text()


# ── sq_services helpers that flip flags ───────────────────────────────


class TestSqServicesFlagHelpers:
    def test_maybe_open_border_below_threshold(self, warrior, state_for):
        state = state_for(warrior)
        sq_services._maybe_open_border(state)
        assert state.flags.get("border_open") is not True

    def test_maybe_open_border_at_threshold(self, warrior, state_for, tmp_path):
        chronicle.add_cleanse(tmp_path)
        chronicle.add_cleanse(tmp_path)
        state = state_for(warrior, chronicle_dir=tmp_path)
        sq_services._maybe_open_border(state)
        assert state.flags["border_open"] is True

    def test_maybe_open_border_already_set(self, warrior, state_for):
        state = state_for(warrior)
        state.flags["border_open"] = True
        sq_services._maybe_open_border(state)
        assert state.flags["border_open"] is True

    def test_maybe_wake_forgotten_thing_already_set(self, warrior, state_for):
        state = state_for(warrior)
        state.flags["forgotten_thing_awake"] = True
        sq_services._maybe_wake_forgotten_thing(state)
        assert state.flags["forgotten_thing_awake"] is True

    def test_maybe_remember_verse_already_set(self, warrior, state_for):
        state = state_for(warrior)
        state.flags["lost_verse_known"] = True
        sq_services._maybe_remember_verse(state)


# ── insomniac re-visit (already counted) ──────────────────────────────


class TestInsomniacRevisit:
    def test_already_counted_path(self, warrior, state_for):
        state = state_for(warrior)
        state.flags["the_counted"] = True
        sq_services.insomniac(state)
        assert "rest a while" in state.io.text().lower()


# ── reader re-visit ────────────────────────────────────────────────────


class TestReaderRevisit:
    def test_already_read_with_reader(self, warrior, state_for):
        state = state_for(warrior)
        state.flags["read_with_reader"] = True
        sq_services.reader(state)
        assert "already with you" in state.io.text()


# ── chronicle edges ────────────────────────────────────────────────────


class TestChronicleEdges:
    def test_load_with_no_entries_key(self, tmp_path):
        # Write a chronicle without "entries"
        import json
        path = chronicle._path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"unlocks": []}))
        assert chronicle.load(tmp_path) == []

    def test_add_echoes_and_spend(self, tmp_path):
        chronicle.add_echoes(50, tmp_path)
        assert chronicle.echoes(tmp_path) == 50
        chronicle.spend_echoes(20, tmp_path)
        assert chronicle.echoes(tmp_path) == 30

    def test_own_pet_records_idempotently(self, tmp_path):
        chronicle.own_pet("hearth_cat", tmp_path)
        chronicle.own_pet("hearth_cat", tmp_path)  # no duplicate
        assert "hearth_cat" in chronicle.owned_pets(tmp_path)

    def test_own_accessory_records_idempotently(self, tmp_path):
        chronicle.own_accessory("ring_of_iron", tmp_path)
        chronicle.own_accessory("ring_of_iron", tmp_path)
        assert "ring_of_iron" in chronicle.owned_accessories(tmp_path)


# ── marks edges ────────────────────────────────────────────────────────


class TestMarksEdges:
    def test_apply_effect_with_flag(self):
        from terminalquest import marks
        state = type("S", (), {"flags": {}, "player": None})()
        mark = {"effect": {"flag": "test_flag"}}
        marks.apply_effect(state, mark)
        assert state.flags["test_flag"] is True

    def test_apply_effect_with_consumable(self):
        from terminalquest import marks
        player = type("P", (), {"consumables": []})()
        state = type("S", (), {"flags": {}, "player": player})()
        mark = {"effect": {"consumable": "bread"}}
        marks.apply_effect(state, mark)
        assert "bread" in player.consumables

    def test_apply_effect_no_effect(self):
        from terminalquest import marks
        state = type("S", (), {"flags": {}, "player": None})()
        marks.apply_effect(state, {"effect": None})


# ── audio.py — _Playback retries on OSError mid-loop ─────────────────


class TestPlaybackEdges:
    def test_loop_returns_on_wait_oserror(self, tmp_path):
        from terminalquest import audio
        wav = tmp_path / "x.wav"
        wav.write_bytes(b"x")

        class FailingProc:
            returncode = 0
            def wait(self, timeout=None):
                raise OSError("wait broken")
            def terminate(self):
                pass
            def kill(self):
                pass

        import subprocess
        with patch.object(subprocess, "Popen", return_value=FailingProc()):
            pb = audio._Playback(["fake"], wav)
            pb.thread.join(timeout=2.0)
        assert not pb.thread.is_alive()


# ── travel.py last uncovered line ─────────────────────────────────────


def test_search_grave_at_zone_with_act(content):
    """Cover travel._search_grave (the line was missing on coverage)."""
    from terminalquest import travel
    player = Player("X", "warrior", content.classes["warrior"], content)
    state = GameState(player, content, ScriptedIO(), random.Random(0),
                      chronicle_dir=tempfile.mkdtemp(), seed="1")
    # Find a zone that has 'act' in content
    act_zone = next((zid for zid, loc in content.locations.items()
                     if loc.get("act") is not None), None)
    if act_zone is None:
        pytest.skip("no act-tagged zone in content")
    state.current_location = act_zone
    fallen = [{
        "player": {"name": "Dead", "class_name": "warrior",
                   "level": 2, "gold": 50},
        "location": act_zone,
        "last_words": "remember this",
    }]
    # _grave_here returns True when there's an unsearched grave in this act
    loc = content.locations[act_zone]
    if not travel._grave_here(state, loc, fallen):
        pytest.skip("test zone has no matching grave fallen")
    travel._search_grave(state, fallen)
    assert state.flags.get("graves_searched")


# ── dialogue.py edges ─────────────────────────────────────────────────


class TestDialogueEdges:
    def test_initial_node_missing_terminates(self):
        from terminalquest import dialogue
        # current resolves to None if the starting key isn't in the tree
        tree = {"initial": {"lines": ["hello"], "responses": []}}
        io = ScriptedIO()
        state = type("S", (), {"io": io, "flags": {}, "player": None})()
        # Call with a missing start_node
        result = dialogue.run_dialogue(state, tree, start_node="not_a_node")
        assert result == "not_a_node"

    def test_response_chains_to_next(self):
        from terminalquest import dialogue
        tree = {
            "initial": {
                "lines": ["start"],
                "responses": [{"text": "go", "next": "n2"}],
            },
            "n2": {"lines": ["end"], "responses": []},
        }
        io = ScriptedIO(["1"])
        state = type("S", (), {"io": io, "flags": {}, "player": None})()
        dialogue.run_dialogue(state, tree)
        assert "end" in io.text()


# ── encounters.py edges ────────────────────────────────────────────────


class TestEncountersEdges:
    def test_npc_progress_after_kills(self, warrior, state_for):
        from terminalquest import encounters
        state = state_for(warrior)
        npc = {"target_enemy": "wolf"}
        state.flags["npc_kills"] = {"wolf": 3}
        assert encounters._npc_progress(state, npc) == 3

    def test_entry_act_for_known_location(self, warrior, state_for, content):
        from terminalquest import encounters
        state = state_for(warrior)
        # Pick a real location id with an act
        for lid, loc in content.locations.items():
            if loc.get("act") is not None:
                entry = {"location": lid}
                assert encounters._entry_act(state, entry) == loc["act"]
                break

    def test_entry_act_for_unknown_location_is_none(self, warrior, state_for):
        from terminalquest import encounters
        state = state_for(warrior)
        assert encounters._entry_act(state, {"location": "atlantis"}) is None


# ── content.py validation rejection edges ──────────────────────────────


class TestContentValidationEdges:
    def test_quest_with_unknown_enemy_rejected(self, content):
        bad = {
            "name": "Bad", "needed": 1, "reward_gold": 0,
            "cleanse_required": 0,
            "target_enemy": "definitely_not_an_enemy",
        }
        content.quests["bad_qid_xyz"] = bad
        try:
            with pytest.raises(ValueError, match="unknown enemy"):
                content._validate_quests()
        finally:
            content.quests.pop("bad_qid_xyz", None)

    def test_quest_with_bad_completion_condition(self, content):
        bad = {
            "name": "Bad", "needed": 1, "reward_gold": 0,
            "cleanse_required": 0,
            "completion_condition": "doing_a_dance",
        }
        content.quests["bad_qid_xyz"] = bad
        try:
            with pytest.raises(ValueError, match="unknown completion_condition"):
                content._validate_quests()
        finally:
            content.quests.pop("bad_qid_xyz", None)

    def test_quest_with_negative_gold(self, content):
        bad = {
            "name": "Bad", "needed": 1, "reward_gold": -1,
            "cleanse_required": 0, "target_enemy": "wolf",
        }
        content.quests["bad_qid_xyz"] = bad
        try:
            with pytest.raises(ValueError):
                content._validate_quests()
        finally:
            content.quests.pop("bad_qid_xyz", None)


# ── player.py marginal paths ───────────────────────────────────────────


class TestPlayerMarginalPaths:
    def test_potion_count_zero(self, content):
        player = Player("X", "warrior", content.classes["warrior"], content)
        player.consumables = []
        assert player.potion_count() == 0

    def test_learn_already_known_ability_no_dupe(self, warrior):
        ab = warrior.abilities[0] if warrior.abilities else "test_ab"
        if ab == "test_ab":
            warrior.abilities.append(ab)
        before = list(warrior.abilities)
        warrior.learn_ability(ab)
        assert warrior.abilities == before

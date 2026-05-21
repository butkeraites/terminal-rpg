"""Tests for the Marks system — irreversible per-character events."""
from conftest import StubRandom, make_state

from terminalquest import marks
from terminalquest.ui import ScriptedIO


def _player(content):
    """Build a level-1 Warrior for marks tests."""
    from terminalquest.player import Player
    return Player("Test", "warrior", content.classes["warrior"], content)


def test_fire_mark_records_id_and_writes_sidecar(content, tmp_path):
    """Firing a mark adds it to player.marks AND writes the sidecar atomically."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    mark = {"id": "test_mark", "lines": ["test line"], "effect": None}
    marks.fire_mark(state, mark)
    assert "test_mark" in state.player.marks
    sidecar = marks.load_sidecar(tmp_path, state.player.run_id)
    assert "test_mark" in sidecar


def test_merge_sidecar_into_player(content, tmp_path):
    """Sidecar marks fold back into player.marks on load — the save-scum guard."""
    player = _player(content)
    # Write a sidecar with a mark the player save did not yet know about.
    marks.write_sidecar(tmp_path, player.run_id, ["seal_mark"])
    assert player.marks == []
    marks.merge_sidecar_into_player(player, tmp_path)
    assert "seal_mark" in player.marks


def test_merge_sidecar_is_idempotent(content, tmp_path):
    """Merging twice does not duplicate marks."""
    player = _player(content)
    player.marks.append("already_here")
    marks.write_sidecar(tmp_path, player.run_id, ["already_here", "also_here"])
    marks.merge_sidecar_into_player(player, tmp_path)
    assert player.marks.count("already_here") == 1
    assert "also_here" in player.marks


def test_clear_sidecar_removes_file(content, tmp_path):
    """clear_sidecar deletes the sidecar — called when the character dies."""
    player = _player(content)
    marks.write_sidecar(tmp_path, player.run_id, ["mark"])
    assert marks.load_sidecar(tmp_path, player.run_id) == ["mark"]
    marks.clear_sidecar(tmp_path, player.run_id)
    assert marks.load_sidecar(tmp_path, player.run_id) == []


def test_eligible_already_fired_returns_false(content, tmp_path):
    """A mark already in player.marks is not eligible to fire again."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    state.player.marks.append("fired_already")
    mark = {"id": "fired_already", "trigger": {"at": ["zone_arrival"]},
            "lines": ["x"]}
    assert not marks.eligible(state, mark, "zone_arrival")


def test_eligible_wrong_site_returns_false(content, tmp_path):
    """A mark tagged for ``combat_victory`` is not eligible on ``zone_arrival``."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    mark = {"id": "combat_only", "trigger": {"at": ["combat_victory"]},
            "lines": ["x"]}
    assert not marks.eligible(state, mark, "zone_arrival")
    assert marks.eligible(state, mark, "combat_victory")


def test_eligible_respects_denies_mark(content, tmp_path):
    """A blocked mark cannot fire even if its other conditions match."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    state.player.marks.append("first")
    mark = {"id": "second", "trigger": {"at": ["zone_arrival"],
                                         "denies_mark": ["first"]},
            "lines": ["x"]}
    assert not marks.eligible(state, mark, "zone_arrival")


def test_eligible_respects_requires_class(content, tmp_path):
    """A class-gated mark only fires for one of its allowed classes."""
    # Warrior is the class built by _player(content). Make a mark that only
    # rolls for mages — it must not be eligible for the warrior.
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    mage_only = {"id": "for_mages", "trigger": {"at": ["zone_arrival"],
                                                 "requires_class": ["mage"]},
                 "lines": ["x"]}
    assert not marks.eligible(state, mage_only, "zone_arrival")
    # A mark that allows warriors (alone or in a list) must be eligible.
    warrior_ok = {"id": "for_warriors", "trigger": {"at": ["zone_arrival"],
                                                     "requires_class": ["warrior",
                                                                        "ranger"]},
                  "lines": ["x"]}
    assert marks.eligible(state, warrior_ok, "zone_arrival")


def test_apply_effect_changes_player_stat(content, tmp_path):
    """A mark with a stat effect changes the player's stat by the delta."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    before = state.player.attack
    mark = {"id": "calloused", "effect": {"stat": "attack", "delta": 2},
            "lines": ["x"]}
    marks.apply_effect(state, mark)
    assert state.player.attack == before + 2


def test_apply_effect_sets_flag(content, tmp_path):
    """A mark with a flag effect sets that flag on state.flags."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    mark = {"id": "knows", "effect": {"flag": "wolf_knows_you"},
            "lines": ["x"]}
    marks.apply_effect(state, mark)
    assert state.flags.get("wolf_knows_you") is True


def test_roll_at_picks_one_from_eligible_pool(content, tmp_path):
    """``roll_at`` walks the pool and fires the first eligible-and-rolled mark."""
    # Force chance=1.0 on a small pool so we get a deterministic fire.
    custom_pool = {
        "always_fires": {
            "id": "always_fires",
            "trigger": {"at": ["zone_arrival"], "chance": 1.0},
            "effect": None,
            "lines": ["it fired"],
        },
    }
    content.marks = custom_pool
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(rnd=0.0),
                       chronicle_dir=tmp_path)
    fired = marks.roll_at(state, "zone_arrival")
    assert fired == "always_fires"
    assert "always_fires" in state.player.marks


def test_describe_returns_one_line_per_mark(content, tmp_path):
    """describe() returns a list of one-line summaries (first line per mark)."""
    pool = {
        "a": {"id": "a", "lines": ["line A1", "line A2"], "trigger": {}, "effect": None},
        "b": {"id": "b", "lines": ["line B1"], "trigger": {}, "effect": None},
    }
    player = _player(content)
    player.marks = ["a", "b"]
    summaries = marks.describe(player, pool)
    assert len(summaries) == 2
    assert "line A1" in summaries[0]
    assert "line B1" in summaries[1]


def test_player_save_roundtrip_preserves_marks(content):
    """Marks survive ``Player.to_dict``/``from_dict``."""
    from terminalquest.player import Player
    player = _player(content)
    player.marks = ["forgot_smell_of_pine", "small_un_remembers_you"]
    restored = Player.from_dict(player.to_dict())
    assert restored.marks == player.marks
    assert restored.run_id == player.run_id


def test_player_save_roundtrip_handles_missing_fields(content):
    """An older save without marks/run_id loads cleanly with sensible defaults."""
    from terminalquest.player import Player
    player = _player(content)
    data = player.to_dict()
    del data["marks"]
    del data["run_id"]
    restored = Player.from_dict(data)
    assert restored.marks == []
    assert isinstance(restored.run_id, str) and len(restored.run_id) > 0


def test_content_loads_marks_with_ids_injected(content):
    """The content loader injects each mark's dict key as its ``id``."""
    assert hasattr(content, "marks")
    if content.marks:
        sample_id, sample_mark = next(iter(content.marks.items()))
        assert sample_mark["id"] == sample_id


def test_eligible_respects_min_visits(content, tmp_path):
    """A mark with ``min_visits`` only fires after the zone has been visited enough times."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    state.current_location = "forest"
    state.flags["zone_visits"] = {"forest": 1}
    mark = {"id": "after_three", "trigger": {"at": ["zone_arrival"],
                                              "location": ["forest"],
                                              "min_visits": 3},
            "lines": ["x"]}
    assert not marks.eligible(state, mark, "zone_arrival")
    state.flags["zone_visits"]["forest"] = 3
    assert marks.eligible(state, mark, "zone_arrival")


def test_eligible_respects_requires_flag(content, tmp_path):
    """A flag-gated mark only fires after its flag is set on state.flags."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    mark = {"id": "needs_companion", "trigger": {"at": ["zone_arrival"],
                                                  "requires_flag": "has_companion"},
            "lines": ["x"]}
    assert not marks.eligible(state, mark, "zone_arrival")
    state.flags["has_companion"] = True
    assert marks.eligible(state, mark, "zone_arrival")


def test_level_up_fire_site_has_base_rate(content):
    """The level_up fire site is registered with a generous base rate."""
    # The site was added in v1.58 when the level-up moments batch shipped.
    assert "level_up" in marks._BASE_RATES
    # Generous enough that growings feel weighty without being guaranteed.
    assert 0.2 <= marks._BASE_RATES["level_up"] <= 0.5


def test_realistic_playthrough_accumulates_marks_in_design_range(content, tmp_path):
    """A simulated late-game-ish playthrough should accumulate 5–40 marks.

    Locks in the design intent (originally 5–15; expanded to 5–40 to match
    the post-1000-mark content depth) so future content or engine changes
    don't accidentally silence the marks system or make it too noisy.
    """
    import random
    from terminalquest.state import GameState
    from terminalquest.player import Player

    player = Player("Sim", "warrior", content.classes["warrior"], content)
    rng = random.Random("design-intent-2026-05-21")
    state = GameState(player, content, ScriptedIO(), rng,
                      chronicle_dir=tmp_path)
    state.flags["zone_visits"] = {}

    # Walk a realistic-ish run: 50 zone arrivals across 7 zones, with combat,
    # saves, and discoveries proportional to a typical playthrough. Level up
    # at every 7th arrival to climb to ~level 8.
    zones = ["forest", "reach", "drowned_holds", "cave", "mourncross",
             "choir", "mountain"]
    for arrival in range(50):
        state.current_location = zones[arrival % len(zones)]
        state.flags["zone_visits"][state.current_location] = (
            state.flags["zone_visits"].get(state.current_location, 0) + 1)
        if arrival > 0 and arrival % 7 == 0 and player.level < 9:
            player.level += 1
            marks.roll_at(state, "level_up")
        marks.roll_at(state, "zone_arrival")
        marks.roll_at(state, "combat_victory")
        if arrival % 3 == 0:
            marks.roll_at(state, "combat_low_hp")
        if arrival % 5 == 0:
            marks.roll_at(state, "save_action")
            marks.roll_at(state, "discovery_read")

    accumulated = len(player.marks)
    # The design target: the kingdom marks you several times per run but does
    # not drown you in marks. If this band changes intentionally, update it
    # in the same commit (same pattern as tools/balance_baseline.json).
    assert 5 <= accumulated <= 40, (
        f"realistic playthrough accumulated {accumulated} marks; "
        "expected the design band of 5..40")

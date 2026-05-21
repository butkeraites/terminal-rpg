"""Content files load and are internally consistent."""
import pytest

from terminalquest.content import ContentError, _load, load_content


def test_load_content_succeeds():
    content = load_content()
    assert len(content.classes) == 5
    assert content.abilities and content.enemies and content.locations


def test_class_abilities_exist():
    content = load_content()
    for cls in content.classes.values():
        for ability_id in cls["abilities"]:
            assert ability_id in content.abilities


def test_location_encounters_reference_real_enemies():
    content = load_content()
    for loc in content.locations.values():
        for encounter in loc.get("encounters", []):
            for enemy_id in encounter.get("enemies", []):
                assert enemy_id in content.enemies


def test_location_connections_resolve():
    content = load_content()
    for loc in content.locations.values():
        for dest in loc.get("connections", []):
            assert dest in content.locations


def test_validate_rejects_unknown_enemy_reference():
    content = load_content()
    content.locations["forest"]["encounters"][0]["enemies"].append("dragon")
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_unknown_ai():
    content = load_content()
    content.enemies["goblin"]["ai"] = "berserk"
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_dangling_connection():
    content = load_content()
    content.locations["forest"]["connections"].append("atlantis")
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_unreachable_location():
    content = load_content()
    content.locations["crossroads"]["connections"].remove("forest")
    with pytest.raises(ValueError):
        content.validate()


def test_boss_location_has_single_valid_enemy():
    content = load_content()
    boss_locs = [loc for loc in content.locations.values() if loc.get("boss")]
    assert boss_locs, "expected at least one boss location"
    for loc in boss_locs:
        encounters = loc["encounters"]
        assert len(encounters) == 1
        assert len(encounters[0]["enemies"]) == 1
        assert encounters[0]["enemies"][0] in content.enemies


def test_zones_have_a_recommended_level():
    content = load_content()
    for loc in content.locations.values():
        if loc.get("kind") == "zone" and not loc.get("boss"):
            assert isinstance(loc["recommended_level"], int)


def test_load_rejects_a_missing_data_file():
    """A missing data file fails with a clear ContentError, not a raw crash."""
    with pytest.raises(ContentError):
        _load("does_not_exist.json")


def test_every_zone_declares_an_act():
    content = load_content()
    for loc_id, loc in content.locations.items():
        if loc.get("kind") == "zone":
            assert loc["act"] in (1, 2, 3), loc_id


def test_discovery_encounters_carry_an_id_and_lines():
    content = load_content()
    discoveries = [enc for loc in content.locations.values()
                   for enc in loc.get("encounters", []) if enc["type"] == "discovery"]
    assert discoveries, "the expanded world should add discovery fragments"
    for discovery in discoveries:
        assert discovery["id"]
        assert discovery["lines"]


def test_validate_rejects_a_discovery_without_lines():
    content = load_content()
    content.locations["forest"]["encounters"].append(
        {"type": "discovery", "id": "phantom"})
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_a_zone_without_an_act():
    content = load_content()
    del content.locations["forest"]["act"]
    with pytest.raises(ValueError):
        content.validate()


def test_components_load_with_four_slots():
    content = load_content()
    for slot in ("head", "haft", "core", "inscription"):
        assert content.components[slot], slot


def test_validate_rejects_an_unknown_component_stat():
    content = load_content()
    some_head = next(iter(content.components["head"].values()))
    some_head["stats"]["wisdom"] = 5
    with pytest.raises(ValueError):
        content.validate()


def test_component_pool_has_breadth():
    """D3: each weapon slot offers a substantial pool of components."""
    content = load_content()
    for slot in ("head", "haft", "core", "inscription"):
        assert len(content.components[slot]) >= 12, slot


def test_validate_rejects_an_unknown_proc_status():
    content = load_content()
    some_core = next(iter(content.components["core"].values()))
    some_core["proc"] = {"trigger": "on_hit", "status": "enlightenment", "turns": 1}
    with pytest.raises(ValueError):
        content.validate()


def test_every_class_has_a_three_step_progression():
    """Each class unlocks three new abilities across the climb (levels 3/5/7)."""
    content = load_content()
    for class_id, cls in content.classes.items():
        progression = cls.get("progression")
        assert progression and len(progression) == 3, class_id
        for entry in progression:
            assert entry["ability"] in content.abilities, (class_id, entry)
            assert isinstance(entry["level"], int) and entry["level"] > 0


def test_validate_rejects_unknown_progression_ability():
    content = load_content()
    content.classes["warrior"]["progression"].append(
        {"ability": "wisdom_of_the_pall", "level": 4})
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_a_non_positive_progression_level():
    content = load_content()
    content.classes["warrior"]["progression"][0]["level"] = 0
    with pytest.raises(ValueError):
        content.validate()


def test_quests_load_and_target_real_enemies():
    """quests.json is loaded as Content.quests and every target_enemy exists."""
    content = load_content()
    assert content.quests, "quests.json should ship with the game"
    for qid, quest in content.quests.items():
        assert quest["target_enemy"] in content.enemies, (
            f"quest {qid!r} targets unknown enemy {quest['target_enemy']!r}")
        assert isinstance(quest["needed"], int) and quest["needed"] > 0
        assert isinstance(quest["reward_gold"], int) and quest["reward_gold"] >= 0
        assert isinstance(quest["cleanse_required"], int)
        assert quest["cleanse_required"] >= 0


def test_validate_rejects_quest_targeting_unknown_enemy():
    """A quest with a typo in target_enemy must fail content validation."""
    content = load_content()
    content.quests["bogus_quest"] = {
        "name": "Hunt the Imaginary",
        "target_enemy": "this_enemy_does_not_exist",
        "needed": 1,
        "reward_gold": 1,
        "cleanse_required": 0,
    }
    with pytest.raises(ValueError):
        content.validate()


def test_validate_rejects_quest_missing_required_field():
    """A quest missing 'needed' (or any required field) fails validation."""
    content = load_content()
    content.quests["incomplete"] = {
        "name": "Half a Quest",
        "target_enemy": "wolf",
        # 'needed' deliberately omitted
        "reward_gold": 50,
        "cleanse_required": 0,
    }
    with pytest.raises(ValueError):
        content.validate()


# --- Phase 1 Batch 1: rich quest schema -----------------------------------
#
# These tests pin the *acceptance* and *reference-integrity* contracts of
# the extended quest schema (docs/QUESTS.md). The engine does not yet wire
# all of these fields into behaviour; that happens in subsequent batches.
# But the schema must be honest from the first authoring batch — typos in
# requires_quest, requires_class, requires_mark, etc. fail at load time.

def _base_quest():
    """Return a minimal-but-valid quest dict that we mutate per test."""
    return {
        "name": "Test Quest",
        "target_enemy": "wolf",
        "needed": 1,
        "reward_gold": 1,
        "cleanse_required": 0,
    }


def test_quest_accepts_target_trophy_instead_of_target_enemy():
    """A trophy quest replaces target_enemy with a known trophy name."""
    content = load_content()
    # Pick any trophy that an enemy actually drops.
    trophy = next(e["trophy"] for e in content.enemies.values() if e.get("trophy"))
    q = _base_quest()
    del q["target_enemy"]
    q["target_trophy"] = trophy
    q["needed"] = 5
    content.quests["test_trophy_q"] = q
    content.validate()  # no raise


def test_quest_rejects_unknown_trophy():
    content = load_content()
    q = _base_quest()
    del q["target_enemy"]
    q["target_trophy"] = "no_such_trophy_exists_anywhere"
    content.quests["bad_trophy"] = q
    with pytest.raises(ValueError):
        content.validate()


def test_quest_rejects_both_target_enemy_and_trophy():
    """A quest with both target_enemy AND target_trophy is ambiguous."""
    content = load_content()
    trophy = next(e["trophy"] for e in content.enemies.values() if e.get("trophy"))
    q = _base_quest()
    q["target_trophy"] = trophy
    content.quests["double_targeted"] = q
    with pytest.raises(ValueError):
        content.validate()


def test_quest_accepts_completion_condition_with_no_kill_target():
    """A pure-conditional quest (no kill target) uses completion_condition."""
    content = load_content()
    q = {
        "name": "Win Without Healing",
        "needed": 1,
        "reward_gold": 0,
        "cleanse_required": 0,
        "completion_condition": "no_healing_received",
    }
    content.quests["conditional_only"] = q
    content.validate()


def test_quest_rejects_unknown_completion_condition():
    content = load_content()
    q = _base_quest()
    q["completion_condition"] = "this_condition_is_imaginary"
    content.quests["bad_cond"] = q
    with pytest.raises(ValueError):
        content.validate()


def test_quest_rejects_requires_class_unknown():
    content = load_content()
    q = _base_quest()
    q["requires_class"] = ["paladin"]  # not a real class
    content.quests["bad_class"] = q
    with pytest.raises(ValueError):
        content.validate()


def test_quest_accepts_known_requires_class():
    content = load_content()
    q = _base_quest()
    q["requires_class"] = ["warrior", "ranger"]
    content.quests["good_class"] = q
    content.validate()


def test_quest_rejects_unknown_requires_mark():
    content = load_content()
    if not content.marks:
        pytest.skip("marks pool empty; cannot test mark-id validation")
    q = _base_quest()
    q["requires_mark"] = "this_mark_does_not_exist"
    content.quests["bad_mark"] = q
    with pytest.raises(ValueError):
        content.validate()


def test_quest_accepts_known_requires_mark():
    content = load_content()
    if not content.marks:
        pytest.skip("marks pool empty; cannot test mark-id validation")
    real_mark = next(iter(content.marks))
    q = _base_quest()
    q["requires_mark"] = real_mark
    content.quests["good_mark"] = q
    content.validate()


def test_quest_rejects_requires_quest_unknown():
    content = load_content()
    q = _base_quest()
    q["requires_quest"] = ["this_quest_id_is_not_real"]
    content.quests["bad_prereq"] = q
    with pytest.raises(ValueError):
        content.validate()


def test_quest_accepts_requires_quest_pointing_to_existing():
    content = load_content()
    existing = next(iter(content.quests))
    q = _base_quest()
    q["requires_quest"] = [existing]
    content.quests["after_existing"] = q
    content.validate()


def test_quest_rejects_chain_next_unknown():
    content = load_content()
    q = _base_quest()
    q["chain_next"] = "nonexistent_quest"
    content.quests["bad_chain"] = q
    with pytest.raises(ValueError):
        content.validate()


def test_quest_accepts_full_rich_schema():
    """A quest using every optional field validates clean when refs are real."""
    content = load_content()
    if not content.marks:
        pytest.skip("marks pool empty; cannot exercise mark refs")
    real_mark = next(iter(content.marks))
    existing_q = next(iter(content.quests))
    q = {
        "name": "The Full Schema Exercise",
        "flavor": "Walked all the way to the design doc and back.",
        "target_enemy": "wolf",
        "needed": 3,
        "reward_gold": 100,
        "reward_consumables": ["bread"],
        "reward_marks": [real_mark],
        "reward_chronicle_line": "They proved the schema worked.",
        "reward_ending_unlock": "demo_ending",
        "cleanse_required": 0,
        "min_level": 1,
        "requires_flag": "the_counted",
        "requires_flags": ["a", "b"],
        "requires_mark": real_mark,
        "requires_marks": [real_mark],
        "requires_class": ["warrior"],
        "requires_ending": ["atrel_peace"],
        "requires_quest": [existing_q],
        "denies_quest": [existing_q],
        "requires_discovery": ["any_string_ok"],
        "requires_chronicle_entry": {"fell_in_zone": "reach"},
        "chain_next": existing_q,
        "hidden": False,
    }
    content.quests["rich_q"] = q
    content.validate()


def test_quest_rejects_negative_min_level():
    content = load_content()
    q = _base_quest()
    q["min_level"] = 0  # must be >= 1
    content.quests["bad_level"] = q
    with pytest.raises(ValueError):
        content.validate()

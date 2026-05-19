"""The Chronicle of the Fallen: recording, resilient loading, filtering."""
from conftest import make_state

from terminalquest import chronicle


def test_record_and_load_round_trip(tmp_path, content, warrior):
    state = make_state(warrior, content, current_location="forest",
                       chronicle_dir=tmp_path)
    chronicle.record(state, "fell", tmp_path)
    entries = chronicle.load(tmp_path)
    assert len(entries) == 1
    assert entries[0]["fate"] == "fell"
    assert entries[0]["location"] == "forest"
    assert entries[0]["player"]["name"] == warrior.name


def test_record_appends_across_runs(tmp_path, content, warrior):
    state = make_state(warrior, content, chronicle_dir=tmp_path)
    chronicle.record(state, "fell", tmp_path)
    chronicle.record(state, "warden", tmp_path)
    assert len(chronicle.load(tmp_path)) == 2


def test_load_missing_chronicle_is_empty(tmp_path):
    assert chronicle.load(tmp_path) == []


def test_load_corrupt_chronicle_is_empty(tmp_path):
    (tmp_path / "chronicle.json").write_text("{ not json", encoding="utf-8")
    assert chronicle.load(tmp_path) == []


def test_fallen_excludes_wardens(tmp_path, content, warrior):
    state = make_state(warrior, content, chronicle_dir=tmp_path)
    chronicle.record(state, "fell", tmp_path)
    chronicle.record(state, "warden", tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    assert len(fallen) == 1
    assert fallen[0]["fate"] == "fell"


def test_wardens_lists_those_kept_by_the_pall(tmp_path, content, warrior):
    state = make_state(warrior, content, current_location="summit",
                       chronicle_dir=tmp_path)
    chronicle.record(state, "warden", tmp_path)
    chronicle.record(state, "fell", tmp_path)
    kept = chronicle.wardens(chronicle.load(tmp_path))
    assert len(kept) == 1
    assert kept[0]["fate"] == "warden"


def test_lay_to_rest_frees_a_fallen_character(tmp_path, content, warrior):
    state = make_state(warrior, content, current_location="forest",
                       chronicle_dir=tmp_path)
    chronicle.record(state, "fell", tmp_path)
    entry = chronicle.load(tmp_path)[0]
    chronicle.lay_to_rest(entry, tmp_path)
    reloaded = chronicle.load(tmp_path)
    assert reloaded[0].get("resolved") is True
    assert chronicle.fallen(reloaded) == []


def test_record_carries_the_run_seed(tmp_path, content, warrior):
    """B3: a recorded character keeps the seed of the run that made it."""
    state = make_state(warrior, content, chronicle_dir=tmp_path, seed="473019")
    chronicle.record(state, "fell", tmp_path)
    assert chronicle.load(tmp_path)[0]["seed"] == "473019"


def test_unlock_persists_and_is_idempotent(tmp_path):
    """E1m: the cross-run unlock store survives and never double-records."""
    chronicle.unlock("pallid_stag", tmp_path)
    chronicle.unlock("pallid_stag", tmp_path)  # idempotent
    chronicle.unlock("maw_mother", tmp_path)
    assert chronicle.unlocked(tmp_path) == {"pallid_stag", "maw_mother"}


def test_unlocks_and_entries_coexist(tmp_path, content, warrior):
    """Recording a death keeps the unlocks; unlocking keeps the fallen."""
    chronicle.unlock("pallid_stag", tmp_path)
    chronicle.record(make_state(warrior, content, chronicle_dir=tmp_path), "fell",
                     tmp_path)
    chronicle.unlock("maw_mother", tmp_path)
    assert chronicle.unlocked(tmp_path) == {"pallid_stag", "maw_mother"}
    assert len(chronicle.load(tmp_path)) == 1

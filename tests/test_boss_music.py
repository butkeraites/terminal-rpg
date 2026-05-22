"""Boss music — synth + engine + combat hook."""
from unittest.mock import patch

import pytest

from terminalquest import boss_music_synth
from terminalquest.audio import AudioEngine


# ── Synth ───────────────────────────────────────────────────────────────


EXPECTED_BOSS_IDS = {
    "pallid_stag", "red_beard", "maw_mother", "hollow_bellward",
    "cantor_vael", "ashen_penitent", "shadow_warden", "the_forgotten_thing",
}


def test_boss_ids_cover_exactly_the_eight():
    assert set(boss_music_synth.BOSS_IDS) == EXPECTED_BOSS_IDS


def test_dynamic_themes_set_is_just_the_warden():
    assert boss_music_synth.DYNAMIC_THEMES == frozenset({"shadow_warden"})


def test_every_theme_id_matches_a_real_enemy(content):
    """Adding a theme that doesn't match an enemy id breaks the music hook —
    locations.py looks up enemy.enemy_id in BOSS_IDS, so they must align."""
    missing = [bid for bid in boss_music_synth.BOSS_IDS
               if bid not in content.enemies]
    assert missing == [], f"theme ids missing from enemies.json: {missing}"


@pytest.mark.parametrize("boss_id", sorted(EXPECTED_BOSS_IDS))
def test_render_boss_does_not_raise(boss_id):
    """Each theme renders to a non-empty sample array. Catches typos in
    voice names, note names, or composition syntax."""
    samples = boss_music_synth.render_boss(boss_id)
    assert len(samples) > 0
    assert all(-32768 <= s <= 32767 for s in samples[::1000])


def test_dynamic_warden_with_no_defeated_is_just_base():
    """A player who reaches the Summit having beaten nothing hears the
    Warden's base layout — no quotes."""
    cold = boss_music_synth.render_boss("shadow_warden", defeated_bosses=[])
    full = boss_music_synth.render_boss(
        "shadow_warden", defeated_bosses=list(EXPECTED_BOSS_IDS))
    assert cold != full, "cold Warden should differ from quote-everyone Warden"


def test_dynamic_warden_differs_per_context():
    """Different defeated lists produce different audio — that's the whole
    point. Compare two non-empty subsets."""
    a = boss_music_synth.render_boss(
        "shadow_warden", defeated_bosses=["pallid_stag"])
    b = boss_music_synth.render_boss(
        "shadow_warden", defeated_bosses=["hollow_bellward"])
    assert a != b


def test_render_all_to_skips_dynamic(tmp_path):
    """The Warden must not be pre-cached — it's per-fight."""
    written = boss_music_synth.render_all_to(out_dir=tmp_path)
    assert "shadow_warden" not in written
    assert set(written) == EXPECTED_BOSS_IDS - boss_music_synth.DYNAMIC_THEMES


def test_render_all_to_skips_existing(tmp_path):
    """Idempotent — re-running shouldn't regenerate what's on disk."""
    (tmp_path / "pallid_stag.wav").write_bytes(b"placeholder")
    written = boss_music_synth.render_all_to(out_dir=tmp_path)
    assert "pallid_stag" not in written
    assert (tmp_path / "pallid_stag.wav").read_bytes() == b"placeholder"


# ── Engine ──────────────────────────────────────────────────────────────


def test_disabled_engine_play_boss_is_no_op(tmp_path):
    """play_boss on a disabled engine must never spawn a subprocess and
    must never render a WAV (no filesystem touch)."""
    engine = AudioEngine(enabled=False, cache_dir=tmp_path)
    with patch("subprocess.Popen") as popen:
        engine.play_boss("shadow_warden",
                         context={"defeated_bosses": ["pallid_stag"]})
        engine.play_boss("pallid_stag")
        assert popen.call_count == 0
    assert not (tmp_path / "bosses").exists()


def test_play_boss_unknown_id_is_silent(tmp_path):
    """Calling with a non-boss id silently does nothing."""
    engine = AudioEngine(enabled=True, cache_dir=tmp_path)
    with patch("subprocess.Popen") as popen:
        engine.play_boss("some_random_enemy_id_qjxz")
        assert popen.call_count == 0


# ── Combat hook ─────────────────────────────────────────────────────────


class _RecordingEngine:
    """Stand-in AudioEngine that records every call. Doesn't touch audio."""

    def __init__(self):
        self.enabled = True
        self.boss_calls = []
        self.zone_calls = []
        self.stops = 0

    def ensure_assets(self, io=None):
        pass

    def play_zone(self, zone_id):
        self.zone_calls.append(zone_id)

    def play_boss(self, boss_id, context=None):
        self.boss_calls.append((boss_id, context))

    def stop(self):
        self.stops += 1

    def mute(self):
        self.enabled = False

    def unmute(self, io=None):
        self.enabled = True


def test_bosses_defeated_appended_on_boss_victory(content, warrior):
    """Boss kill records the enemy id in state.flags['bosses_defeated'].
    Future Warden fights read this list to choose quotes."""
    import tempfile

    from terminalquest import locations
    from terminalquest.state import GameState
    from terminalquest.ui import ScriptedIO
    from tests.conftest import StubRandom

    # Build a minimal boss encounter dict pointing at a real boss
    encounter = {
        "id": "test_boss",
        "type": "combat",
        "boss": True,
        "enemies": ["pallid_stag"],
    }
    audio = _RecordingEngine()
    state = GameState(
        warrior, content, ScriptedIO(), StubRandom(),
        chronicle_dir=tempfile.mkdtemp(), audio=audio,
    )
    # locations.py imports run_combat by name (`from .combat import run_combat`),
    # so patch its reference inside the locations module.
    from terminalquest import encounters
    with patch.object(encounters, "run_combat", return_value="victory"), \
            patch.object(encounters, "_offer_drop"):
        outcome = locations.run_encounter(state, encounter, [], [])
    assert outcome == "boss_victory"
    assert "pallid_stag" in state.flags["bosses_defeated"]
    # play_boss called once with the run's defeated list (empty going in)
    assert audio.boss_calls == [("pallid_stag", {"defeated_bosses": []})]
    # Ambient restored after the fight
    assert audio.zone_calls == [state.current_location]


def test_warden_gets_defeated_bosses_context(content, warrior):
    """When the Warden fight starts, the engine is handed the full list of
    bosses defeated this run as context."""
    import tempfile

    from terminalquest import locations
    from terminalquest.state import GameState
    from terminalquest.ui import ScriptedIO
    from tests.conftest import StubRandom

    audio = _RecordingEngine()
    state = GameState(
        warrior, content, ScriptedIO(), StubRandom(),
        chronicle_dir=tempfile.mkdtemp(), audio=audio,
    )
    state.flags["bosses_defeated"] = ["pallid_stag", "hollow_bellward"]
    encounter = {"id": "summit_fight", "type": "combat", "boss": True,
                 "enemies": ["shadow_warden"]}
    from terminalquest import encounters
    with patch.object(encounters, "run_combat", return_value="defeat"), \
            patch.object(encounters, "_offer_drop"):
        locations.run_encounter(state, encounter, [], [])
    assert audio.boss_calls == [
        ("shadow_warden",
         {"defeated_bosses": ["pallid_stag", "hollow_bellward"]}),
    ]

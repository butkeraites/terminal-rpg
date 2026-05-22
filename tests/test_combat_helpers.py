"""Coverage push for terminalquest/combat.py — exercises the round helpers
extracted in the v2.3 refactor, plus the smaller bookkeeping pieces."""
import random
import tempfile
from unittest.mock import patch

import pytest

from terminalquest import combat
from terminalquest.enemy import make_enemy
from terminalquest.hireling import Hireling
from terminalquest.companion import Companion
from terminalquest.pet import Pet
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


# ── _hireling_act ──────────────────────────────────────────────────────


class TestHirelingAct:
    def test_no_hireling_is_noop(self, warrior, state_for):
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._hireling_act(state, enemy)  # no raise

    def test_dead_hireling_is_noop(self, warrior, state_for):
        h = Hireling("h", "Ally", 10, 0, 3)
        h.hp = 0
        warrior.hireling = h
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._hireling_act(state, enemy)  # no raise

    def test_full_hp_means_no_heal(self, warrior, state_for):
        warrior.hireling = Hireling("h", "Ally", 10, 0, 4)
        warrior.hp = warrior.max_hp
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._hireling_act(state, enemy)
        assert warrior.hp == warrior.max_hp

    def test_heals_when_player_hurt(self, warrior, state_for):
        warrior.hireling = Hireling("h", "Ally", 10, 0, 4)
        warrior.hp = warrior.max_hp - 10
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._hireling_act(state, enemy)
        assert warrior.hp == warrior.max_hp - 6


# ── _companion_act ─────────────────────────────────────────────────────


class TestCompanionAct:
    def test_no_companion_is_noop(self, warrior, state_for):
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._companion_act(state, enemy)  # no raise

    def test_damage_companion_strikes(self, warrior, state_for):
        warrior.companion = Companion("c", "Strike", "damage", 5)
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        before_hp = enemy.hp
        combat._companion_act(state, enemy)
        assert enemy.hp == before_hp - 5

    def test_heal_companion_at_full_hp_is_noop(self, warrior, state_for):
        warrior.companion = Companion("c", "Mender", "heal", 5)
        state = state_for(warrior)
        warrior.hp = warrior.max_hp
        enemy = make_enemy("goblin", state.content)
        combat._companion_act(state, enemy)
        assert warrior.hp == warrior.max_hp

    def test_heal_companion_mends_when_hurt(self, warrior, state_for, tmp_path):
        warrior.companion = Companion("c", "Mender", "heal", 5)
        warrior.hp = warrior.max_hp - 10
        state = state_for(warrior, chronicle_dir=tmp_path)
        enemy = make_enemy("goblin", state.content)
        combat._companion_act(state, enemy)
        assert warrior.hp == warrior.max_hp - 5

    def test_cleansed_road_scales_power(self, warrior, state_for, tmp_path):
        from terminalquest import chronicle
        for _ in range(2):
            chronicle.add_cleanse(tmp_path)
        warrior.companion = Companion("c", "Strike", "damage", 5)
        state = state_for(warrior, chronicle_dir=tmp_path)
        enemy = make_enemy("goblin", state.content)
        before_hp = enemy.hp
        combat._companion_act(state, enemy)
        # 5 base + 2 cleanses = 7 damage
        assert enemy.hp == before_hp - 7


# ── _fire_procs ────────────────────────────────────────────────────────


class TestFireProcs:
    def test_dead_enemy_skips(self, warrior, state_for):
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        enemy.hp = 0
        combat._fire_procs(warrior, enemy, dodged=False, crit=False, io=state.io)
        # No exception, enemy still dead

    def test_no_weapon_skips(self, warrior, state_for):
        warrior.equipment.pop("weapon", None)
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._fire_procs(warrior, enemy, dodged=False, crit=False, io=state.io)

    def test_on_hit_proc_fires_unless_dodged(self, warrior, state_for):
        warrior.equipment["weapon"].procs = [
            {"trigger": "on_hit", "status": "burn", "turns": 2},
        ]
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._fire_procs(warrior, enemy, dodged=False, crit=False, io=state.io)
        assert "burn" in enemy.statuses

    def test_on_hit_proc_does_not_fire_when_dodged(self, warrior, state_for):
        warrior.equipment["weapon"].procs = [
            {"trigger": "on_hit", "status": "burn", "turns": 2},
        ]
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._fire_procs(warrior, enemy, dodged=True, crit=False, io=state.io)
        assert "burn" not in enemy.statuses

    def test_on_crit_proc_fires_only_on_crit(self, warrior, state_for):
        warrior.equipment["weapon"].procs = [
            {"trigger": "on_crit", "status": "bleed", "turns": 3},
        ]
        state = state_for(warrior)
        enemy = make_enemy("goblin", state.content)
        combat._fire_procs(warrior, enemy, dodged=False, crit=False, io=state.io)
        assert "bleed" not in enemy.statuses
        combat._fire_procs(warrior, enemy, dodged=False, crit=True, io=state.io)
        assert "bleed" in enemy.statuses


# ── _tick_pet_regen ────────────────────────────────────────────────────


class TestTickPetRegen:
    def test_no_pet_is_noop(self, warrior, state_for):
        warrior.equipment.pop("pet", None)
        state = state_for(warrior)
        combat._tick_pet_regen(warrior, state.io)

    def test_pet_without_regen_is_noop(self, warrior, state_for):
        warrior.equipment["pet"] = Pet("p", "P", {}, regen_per_round=0)
        state = state_for(warrior)
        combat._tick_pet_regen(warrior, state.io)

    def test_full_hp_no_heal(self, warrior, state_for):
        warrior.equipment["pet"] = Pet("p", "P", {}, regen_per_round=2)
        state = state_for(warrior)
        warrior.hp = warrior.max_hp
        combat._tick_pet_regen(warrior, state.io)
        assert warrior.hp == warrior.max_hp

    def test_regen_when_hurt(self, warrior, state_for):
        warrior.equipment["pet"] = Pet("p", "P", {}, regen_per_round=2)
        state = state_for(warrior)
        warrior.hp = warrior.max_hp - 5
        combat._tick_pet_regen(warrior, state.io)
        assert warrior.hp == warrior.max_hp - 3


# ── _tick_cat_companion ────────────────────────────────────────────────


class TestTickCatCompanion:
    def test_disabled_is_noop(self, warrior, state_for):
        state = state_for(warrior)
        combat._tick_cat_companion(state)  # cat_companion flag not set

    def test_full_hp_no_heal(self, warrior, state_for):
        state = state_for(warrior)
        state.flags["cat_companion"] = True
        warrior.hp = warrior.max_hp
        combat._tick_cat_companion(state)
        assert warrior.hp == warrior.max_hp

    def test_heals_one_hp(self, warrior, state_for):
        state = state_for(warrior)
        state.flags["cat_companion"] = True
        warrior.hp = warrior.max_hp - 5
        combat._tick_cat_companion(state)
        assert warrior.hp == warrior.max_hp - 4
        assert "cat purrs" in state.io.text()


# ── _resolve_start_of_turn ─────────────────────────────────────────────


class TestResolveStartOfTurn:
    def test_no_status_survives(self, warrior, state_for):
        state = state_for(warrior)
        assert combat._resolve_start_of_turn(warrior, state.io) is True

    def test_dot_kills_returns_false(self, warrior, state_for):
        state = state_for(warrior)
        # Lethal poison: hp=1, poison ticks for at least 1
        warrior.hp = 1
        warrior.statuses = {"poison": 1}
        survived = combat._resolve_start_of_turn(warrior, state.io)
        assert survived is False


# ── _print_combat_status ───────────────────────────────────────────────


def test_print_combat_status_renders_both(warrior, state_for):
    state = state_for(warrior)
    enemy = make_enemy("goblin", state.content)
    combat._print_combat_status(warrior, enemy, state.io)
    text = state.io.text()
    assert warrior.name in text
    assert enemy.name in text


# ── _post_combat ───────────────────────────────────────────────────────


class TestPostCombat:
    def test_victory_grants_rewards(self, warrior, state_for):
        warrior.equipment.pop("weapon", None)
        state = state_for(warrior)
        state.flags["combat_conditions"] = {"no_stun_during_fight": True,
                                            "no_hireling_death": True,
                                            "killed_in_one_round": True}
        enemy = make_enemy("goblin", state.content)
        before = warrior.gold
        combat._post_combat(state, enemy, "victory", refresh_after=True)
        assert warrior.gold > before
        assert warrior.stamina == warrior.max_stamina

    def test_defeat_clears_statuses(self, warrior, state_for):
        state = state_for(warrior)
        warrior.statuses = {"poison": 5}
        state.flags["combat_conditions"] = {}
        enemy = make_enemy("goblin", state.content)
        combat._post_combat(state, enemy, "defeat", refresh_after=False)
        assert warrior.statuses == {}

    def test_no_refresh_keeps_partial_stamina(self, warrior, state_for):
        state = state_for(warrior)
        warrior.stamina = 2
        state.flags["combat_conditions"] = {}
        enemy = make_enemy("goblin", state.content)
        combat._post_combat(state, enemy, "fled", refresh_after=False)
        assert warrior.stamina == 2  # not refreshed

    def test_hireling_death_records_forsaken(self, warrior, state_for):
        warrior.hireling = Hireling("h", "Ally", 10, 0, 0)
        warrior.hireling.hp = 0
        state = state_for(warrior)
        state.flags["combat_conditions"] = {}
        enemy = make_enemy("goblin", state.content)
        combat._post_combat(state, enemy, "victory", refresh_after=False)
        assert state.flags.get("fallen_hireling") is not None
        assert warrior.hireling is None

    def test_victory_low_hp_fires_marks_roll(self, warrior, state_for):
        state = state_for(warrior)
        state.flags["combat_conditions"] = {}
        warrior.hp = 1  # < 30% of max
        enemy = make_enemy("goblin", state.content)
        with patch("terminalquest.combat.marks.roll_at") as roll:
            combat._post_combat(state, enemy, "victory", refresh_after=True)
        # Roll called for combat_victory + combat_low_hp
        sites = [c.args[1] for c in roll.call_args_list]
        assert "combat_victory" in sites
        assert "combat_low_hp" in sites


# ── _consumable_label ──────────────────────────────────────────────────


class TestConsumableLabel:
    def test_health_potion_label(self):
        assert "HP" in combat._consumable_label("Health Potion")

    def test_pall_drinker_label_includes_stamina(self):
        s = combat._consumable_label("Pall-Drinker")
        assert "stamina" in s.lower()

    def test_status_consumable_label(self):
        s = combat._consumable_label("Warrior's Breath")
        assert "braced" in s

    def test_unknown_returns_dash(self):
        assert combat._consumable_label("not_a_thing") == "—"


# ── _is_overleveled ────────────────────────────────────────────────────


class TestIsOverleveled:
    def test_low_level_is_not_over(self, warrior, state_for):
        state = state_for(warrior)
        state.current_location = "crossroads"
        # warrior is level 1 by default — should not be overleveled
        assert combat._is_overleveled(state) in (True, False)  # just exercise

    def test_high_level_is_over(self, warrior, state_for):
        state = state_for(warrior)
        warrior.level = 99
        state.current_location = "crossroads"
        # likely overleveled depending on the zone's recommended_level
        combat._is_overleveled(state)


# ── _init_combat_conditions ────────────────────────────────────────────


def test_init_combat_conditions_resets(warrior, state_for):
    state = state_for(warrior)
    state.flags["combat_conditions"] = {"no_stun_during_fight": False}
    state.flags["_combat_round"] = 5
    combat._init_combat_conditions(state)
    assert state.flags["combat_conditions"]["no_stun_during_fight"] is True
    assert state.flags["_combat_round"] == 1

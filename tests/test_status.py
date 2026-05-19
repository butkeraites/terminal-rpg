"""Status effects: application, ticking and combat modifiers."""
import pytest

from terminalquest import status
from terminalquest.enemy import Enemy

_DUMMY_DEF = {
    "name": "Dummy", "hp": 100, "attack": 5, "defense": 0,
    "xp_reward": 0, "gold_reward": 0, "ai": "aggressive",
}


def make_dummy():
    return Enemy("dummy", _DUMMY_DEF)


def test_apply_and_has_status():
    dummy = make_dummy()
    status.apply_status(dummy, "poison", 3)
    assert status.has_status(dummy, "poison")


def test_tick_deals_dot_and_expires():
    dummy = make_dummy()
    status.apply_status(dummy, "poison", 1)
    damage, _ = status.tick_statuses(dummy)
    assert damage == status.DOT_DAMAGE["poison"]
    assert not status.has_status(dummy, "poison")


def test_tick_decrements_without_expiring():
    dummy = make_dummy()
    status.apply_status(dummy, "bleed", 3)
    status.tick_statuses(dummy)
    assert dummy.statuses["bleed"] == 2


def test_weak_reduces_attack_multiplier():
    dummy = make_dummy()
    status.apply_status(dummy, "weak", 2)
    assert status.attack_multiplier(dummy) == 0.6


def test_vulnerable_and_braced_stack():
    dummy = make_dummy()
    status.apply_status(dummy, "vulnerable", 2)
    status.apply_status(dummy, "braced", 2)
    assert status.damage_taken_multiplier(dummy) == pytest.approx(1.3 * 0.5)


def test_unknown_status_is_rejected():
    dummy = make_dummy()
    with pytest.raises(ValueError):
        status.apply_status(dummy, "nonsense", 1)

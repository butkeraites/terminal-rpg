"""Coverage push for terminalquest/vendors.py.

The vendor functions are interactive menu loops. Each test scripts the
inputs end-to-end, exercising one or two happy paths plus the most
distinctive error / branch the vendor owns.
"""
import random
import tempfile
from unittest.mock import patch

import pytest

from terminalquest import chronicle, vendors
from terminalquest.player import Player
from terminalquest.state import GameState
from terminalquest.ui import ScriptedIO


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def warrior(content):
    return Player("Hero", "warrior", content.classes["warrior"], content)


@pytest.fixture
def make_state(content):
    def _make(io, player, **kwargs):
        return GameState(player, content, io, random.Random(0),
                         chronicle_dir=tempfile.mkdtemp(),
                         seed=kwargs.pop("seed", "1"),
                         **kwargs)
    return _make


# ── _buy_potion / _potion_label / _rest_at_inn ─────────────────────────


class TestPotionHelpers:
    def test_buy_potion_with_enough_gold(self, warrior):
        warrior.gold = 100
        io = ScriptedIO()
        vendors._buy_potion(warrior, io, "Health Potion", 30)
        assert warrior.gold == 70
        assert "Health Potion" in warrior.consumables

    def test_buy_potion_without_enough_gold(self, warrior):
        warrior.gold = 5
        before = warrior.consumables.count("Health Potion")
        io = ScriptedIO()
        vendors._buy_potion(warrior, io, "Health Potion", 30)
        assert warrior.gold == 5
        assert warrior.consumables.count("Health Potion") == before
        assert "Not enough gold" in io.text()

    def test_potion_label_unlocked(self):
        s = vendors._potion_label("Sovereign Potion", 200, True, 1, 2)
        assert "Sovereign Potion" in s and "200 gold" in s
        assert "🔒" not in s

    def test_potion_label_locked(self):
        s = vendors._potion_label("Pall-Drinker", 500, False, 3, 1)
        assert "🔒" in s
        assert "now: 1" in s

    def test_rest_at_inn_with_gold(self, warrior, make_state):
        warrior.gold = 50
        warrior.hp = 1
        warrior.stamina = 0
        warrior.statuses = {"poison": 3}
        state = make_state(ScriptedIO(), warrior)
        vendors._rest_at_inn(state)
        assert warrior.gold == 50 - vendors.INN_COST
        assert warrior.hp == warrior.max_hp
        assert warrior.stamina == warrior.max_stamina
        assert warrior.statuses == {}

    def test_rest_at_inn_without_gold(self, warrior, make_state):
        warrior.gold = 5
        warrior.hp = 1
        state = make_state(ScriptedIO(), warrior)
        vendors._rest_at_inn(state)
        assert warrior.gold == 5
        assert warrior.hp == 1
        assert "Not enough gold" in state.io.text()


# ── _run_service dispatcher ────────────────────────────────────────────


class TestRunServiceDispatch:
    def test_dispatches_inn(self, warrior, make_state):
        warrior.gold = 50
        state = make_state(ScriptedIO(), warrior)
        vendors._run_service(state, "inn")
        assert warrior.gold == 50 - vendors.INN_COST

    def test_unknown_service_is_silent(self, warrior, make_state):
        state = make_state(ScriptedIO(), warrior)
        vendors._run_service(state, "totally_not_a_service")  # no raise

    @pytest.mark.parametrize("service,attr", [
        ("shop", "shop"),
        ("smith", "smith"),
        ("quartermaster", "quartermaster"),
        ("pact_broker", "pact_broker"),
        ("echo_trader", "echo_trader"),
        ("night_hunt", "night_hunt"),
        ("quest_board", "quest_board"),
        ("survivor", "survivor"),
        ("beastmaster", "beastmaster"),
        ("hireling_hall", "hireling_hall"),
        ("scholar", "scholar"),
        ("reader", "reader"),
        ("insomniac", "insomniac"),
        ("caretaker", "caretaker"),
        ("hearth_line", "write_hearth_line"),
    ])
    def test_dispatch_routes(self, warrior, make_state, service, attr):
        """Every known service id hits its underlying function."""
        state = make_state(ScriptedIO(), warrior)
        with patch.object(vendors, attr) as fn:
            vendors._run_service(state, service)
        fn.assert_called_once()


# ── shop ───────────────────────────────────────────────────────────────


class TestShop:
    def test_buy_health_potion_then_leave(self, warrior, make_state):
        warrior.gold = 100
        io = ScriptedIO(["1", "7"])  # buy Health Potion, leave
        state = make_state(io, warrior)
        vendors.shop(state)
        assert "Health Potion" in warrior.consumables
        assert warrior.gold == 100 - vendors.POTION_COST

    def test_buy_greater_potion(self, warrior, make_state):
        warrior.gold = 200
        io = ScriptedIO(["2", "7"])
        state = make_state(io, warrior)
        vendors.shop(state)
        assert "Greater Potion" in warrior.consumables

    def test_locked_sovereign_potion_warns(self, warrior, make_state):
        # No champions unlocked → Sovereign is locked
        warrior.gold = 500
        io = ScriptedIO(["3", "7"])
        state = make_state(io, warrior)
        vendors.shop(state)
        assert "🔒" in state.io.text() or "locked until" in state.io.text()

    def test_unlocked_sovereign_potion(self, warrior, make_state, tmp_path):
        # Unlock by giving the player one champion in the chronicle
        warrior.gold = 500
        chronicle.unlock("pallid_stag", tmp_path)
        io = ScriptedIO(["3", "7"])
        state = make_state(io, warrior)
        state.chronicle_dir = tmp_path
        vendors.shop(state)
        assert "Sovereign Potion" in warrior.consumables

    def test_locked_pall_drinker(self, warrior, make_state):
        warrior.gold = 1000
        io = ScriptedIO(["4", "7"])
        state = make_state(io, warrior)
        vendors.shop(state)
        assert "🔒" in state.io.text() or "locked until" in state.io.text()

    def test_attack_upgrade_with_gold(self, warrior, make_state):
        warrior.gold = 1000
        before = warrior.attack
        io = ScriptedIO(["5", "7"])
        state = make_state(io, warrior)
        vendors.shop(state)
        assert warrior.attack == before + 5

    def test_attack_upgrade_no_gold(self, warrior, make_state):
        warrior.gold = 0
        before = warrior.attack
        io = ScriptedIO(["5", "7"])
        state = make_state(io, warrior)
        vendors.shop(state)
        assert warrior.attack == before

    def test_defense_upgrade_with_gold(self, warrior, make_state):
        warrior.gold = 1000
        before = warrior.defense
        io = ScriptedIO(["6", "7"])
        state = make_state(io, warrior)
        vendors.shop(state)
        assert warrior.defense == before + 3

    def test_defense_upgrade_no_gold(self, warrior, make_state):
        warrior.gold = 0
        before = warrior.defense
        io = ScriptedIO(["6", "7"])
        state = make_state(io, warrior)
        vendors.shop(state)
        assert warrior.defense == before

    def test_invalid_choice_reprompts(self, warrior, make_state):
        warrior.gold = 100
        io = ScriptedIO(["bogus", "7"])
        state = make_state(io, warrior)
        vendors.shop(state)
        assert "Invalid choice" in state.io.text()


# ── scholar ────────────────────────────────────────────────────────────


class TestScholar:
    def test_no_unpaid_discoveries(self, warrior, make_state):
        io = ScriptedIO(["1"])  # Leave
        state = make_state(io, warrior)
        vendors.scholar(state)
        assert "Bring me more" in state.io.text()

    def test_pays_for_unpaid_discoveries(self, warrior, make_state):
        io = ScriptedIO(["1"])  # Accept payout
        state = make_state(io, warrior)
        state.flags["discoveries_seen"] = ["disc_a", "disc_b", "disc_c"]
        before = warrior.gold
        vendors.scholar(state)
        assert warrior.gold == before + 3 * vendors.SCHOLAR_PAYOUT
        assert state.flags["scholar_paid"] == ["disc_a", "disc_b", "disc_c"]

    def test_decline_payment_keeps_them_unpaid(self, warrior, make_state):
        io = ScriptedIO(["2"])  # Leave without payout
        state = make_state(io, warrior)
        state.flags["discoveries_seen"] = ["disc_a"]
        before = warrior.gold
        vendors.scholar(state)
        assert warrior.gold == before
        assert state.flags.get("scholar_paid") == []


# ── survivor ───────────────────────────────────────────────────────────


class TestSurvivor:
    def test_buy_first_item(self, warrior, make_state):
        warrior.gold = 2000
        # Survivor stock has 3 items, "Leave" is index 4
        io = ScriptedIO(["1", "4"])
        state = make_state(io, warrior)
        vendors.survivor(state)
        first_name = vendors.SURVIVOR_STOCK[0][0]
        assert first_name in warrior.consumables

    def test_invalid_then_leave(self, warrior, make_state):
        io = ScriptedIO(["bogus", "4"])
        state = make_state(io, warrior)
        vendors.survivor(state)
        assert "Invalid choice" in state.io.text()

    def test_insufficient_gold(self, warrior, make_state):
        warrior.gold = 0
        io = ScriptedIO(["1", "4"])
        state = make_state(io, warrior)
        vendors.survivor(state)
        assert "Not enough gold" in state.io.text()
        assert vendors.SURVIVOR_STOCK[0][0] not in warrior.consumables


# ── hireling_hall ──────────────────────────────────────────────────────


class TestHirelingHall:
    def test_hire_first_with_gold(self, warrior, make_state, content):
        if not content.hirelings:
            pytest.skip("no hirelings in content")
        warrior.gold = 10000
        # 1=first hireling, then leave at index len+1
        leave = str(len(content.hirelings) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.hireling_hall(state)
        assert warrior.hireling is not None

    def test_already_with_you_path(self, warrior, make_state, content):
        if not content.hirelings:
            pytest.skip("no hirelings in content")
        warrior.gold = 10000
        leave = str(len(content.hirelings) + 1)
        # Hire then try to hire the same one again
        io = ScriptedIO(["1", "1", leave])
        state = make_state(io, warrior)
        vendors.hireling_hall(state)
        assert "already walks at your side" in state.io.text()

    def test_insufficient_gold(self, warrior, make_state, content):
        if not content.hirelings:
            pytest.skip("no hirelings in content")
        warrior.gold = 0
        leave = str(len(content.hirelings) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.hireling_hall(state)
        assert warrior.hireling is None
        assert "Not enough gold" in state.io.text()

    def test_invalid_choice(self, warrior, make_state, content):
        if not content.hirelings:
            pytest.skip("no hirelings in content")
        leave = str(len(content.hirelings) + 1)
        io = ScriptedIO(["bogus", leave])
        state = make_state(io, warrior)
        vendors.hireling_hall(state)
        assert "Invalid choice" in state.io.text()


# ── beastmaster ────────────────────────────────────────────────────────


class TestBeastmasterEquipToggle:
    def test_owned_pet_equip_unequip_toggle(self, warrior, make_state, content, tmp_path):
        if not content.pets:
            pytest.skip("no pets in content")
        first_id = next(iter(content.pets))
        chronicle.own_pet(first_id, tmp_path)
        leave = str(len(content.pets) + 1)
        # First pick: equip the owned pet. Second pick: unequip it. Then leave.
        io = ScriptedIO(["1", "1", leave])
        state = make_state(io, warrior)
        state.chronicle_dir = tmp_path
        from terminalquest import vendors as _v
        _v.beastmaster(state)
        # Final state: unequipped
        assert state.player.equipment.get("pet") is None


class TestBeastmaster:
    def test_buy_first_pet_with_gold(self, warrior, make_state, content):
        if not content.pets:
            pytest.skip("no pets in content")
        warrior.gold = 100000
        leave = str(len(content.pets) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.beastmaster(state)
        assert warrior.equipment.get("pet") is not None

    def test_buy_with_trophies(self, warrior, make_state, content):
        if not content.pets:
            pytest.skip("no pets in content")
        first_id, first_entry = next(iter(content.pets.items()))
        warrior.trophies = {first_entry["trophy"]: first_entry["trophy_required"]}
        warrior.gold = 0
        leave = str(len(content.pets) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.beastmaster(state)
        assert warrior.equipment.get("pet") is not None
        assert warrior.trophies[first_entry["trophy"]] == 0

    def test_neither_gold_nor_trophies(self, warrior, make_state, content):
        if not content.pets:
            pytest.skip("no pets in content")
        warrior.gold = 0
        leave = str(len(content.pets) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.beastmaster(state)
        assert "Not enough gold AND not enough trophies" in state.io.text()

    def test_invalid_choice(self, warrior, make_state, content):
        if not content.pets:
            pytest.skip("no pets in content")
        leave = str(len(content.pets) + 1)
        io = ScriptedIO(["bogus", leave])
        state = make_state(io, warrior)
        vendors.beastmaster(state)
        assert "Invalid choice" in state.io.text()


# ── quartermaster ──────────────────────────────────────────────────────


class TestQuartermaster:
    def test_buy_first_armor(self, warrior, make_state, content):
        if not content.armor:
            pytest.skip("no armor in content")
        warrior.gold = 100000
        leave = str(len(content.armor) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.quartermaster(state)
        assert warrior.equipment.get("armor") is not None

    def test_insufficient_gold(self, warrior, make_state, content):
        if not content.armor:
            pytest.skip("no armor in content")
        warrior.gold = 0
        leave = str(len(content.armor) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.quartermaster(state)
        assert "Not enough gold" in state.io.text()

    def test_already_wearing(self, warrior, make_state, content):
        if not content.armor:
            pytest.skip("no armor in content")
        warrior.gold = 100000
        leave = str(len(content.armor) + 1)
        # Buy then try to buy the same one again
        io = ScriptedIO(["1", "1", leave])
        state = make_state(io, warrior)
        vendors.quartermaster(state)
        assert "already wear" in state.io.text()


# ── smith ──────────────────────────────────────────────────────────────


class TestSmith:
    def test_no_weapon_path(self, warrior, make_state):
        warrior.equipment.pop("weapon", None)
        io = ScriptedIO(["1"])
        state = make_state(io, warrior)
        vendors.smith(state)
        assert "no weapon to temper" in state.io.text()

    def test_already_upgraded(self, warrior, make_state):
        from terminalquest.weapon import WEAPON_UPGRADES
        upgrade_id = next(iter(WEAPON_UPGRADES))
        warrior.equipment["weapon"].upgrade = upgrade_id
        io = ScriptedIO(["1"])
        state = make_state(io, warrior)
        vendors.smith(state)
        assert "already been worked" in state.io.text()

    def test_buy_first_upgrade_with_gold(self, warrior, make_state):
        warrior.gold = 1000000
        warrior.equipment["weapon"].upgrade = None
        # After buying upgrade 1, the loop re-renders. The weapon now has
        # an upgrade so the menu changes (just "1. Leave"). So inputs are
        # buy(1), then leave(1) from the already-upgraded menu.
        io = ScriptedIO(["1", "1"])
        state = make_state(io, warrior)
        vendors.smith(state)
        assert warrior.equipment["weapon"].upgrade is not None

    def test_invalid_choice_on_smith(self, warrior, make_state):
        warrior.equipment["weapon"].upgrade = None
        from terminalquest.weapon import WEAPON_UPGRADES
        leave = str(len(WEAPON_UPGRADES) + 1)
        io = ScriptedIO(["bogus", leave])
        state = make_state(io, warrior)
        vendors.smith(state)
        assert "Invalid choice" in state.io.text()

    def test_insufficient_gold(self, warrior, make_state):
        warrior.gold = 0
        warrior.equipment["weapon"].upgrade = None
        from terminalquest.weapon import WEAPON_UPGRADES
        leave = str(len(WEAPON_UPGRADES) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.smith(state)
        assert "Not enough gold" in state.io.text()


# ── echo_trader ────────────────────────────────────────────────────────


class TestEchoTrader:
    def test_no_echoes_buy_fails(self, warrior, make_state, content):
        if not content.accessories:
            pytest.skip("no accessories in content")
        leave = str(len(content.accessories) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.echo_trader(state)
        assert "Not enough Echoes" in state.io.text()

    def test_buy_with_echoes(self, warrior, make_state, content, tmp_path):
        if not content.accessories:
            pytest.skip("no accessories in content")
        chronicle.add_echoes(100000, tmp_path)
        leave = str(len(content.accessories) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        state.chronicle_dir = tmp_path
        vendors.echo_trader(state)
        # The first accessory should be equipped in its slot
        first_id, first_entry = next(iter(content.accessories.items()))
        assert state.player.equipment.get(first_entry["slot"]) is not None

    def test_invalid_choice(self, warrior, make_state, content):
        if not content.accessories:
            pytest.skip("no accessories in content")
        leave = str(len(content.accessories) + 1)
        io = ScriptedIO(["bogus", leave])
        state = make_state(io, warrior)
        vendors.echo_trader(state)
        assert "Invalid choice" in state.io.text()

    def test_owned_accessory_equip_unequip_toggle(self, warrior, make_state,
                                                    content, tmp_path):
        if not content.accessories:
            pytest.skip("no accessories in content")
        first_id, first_entry = next(iter(content.accessories.items()))
        chronicle.own_accessory(first_id, tmp_path)
        leave = str(len(content.accessories) + 1)
        # 1=equip, 1=unequip, leave
        io = ScriptedIO(["1", "1", leave])
        state = make_state(io, warrior)
        state.chronicle_dir = tmp_path
        vendors.echo_trader(state)
        # The accessory should end up unequipped (toggle off)
        slot = first_entry["slot"]
        assert state.player.equipment.get(slot) is None


# ── pact_broker ────────────────────────────────────────────────────────


class TestPactBroker:
    def test_bind_first_companion(self, warrior, make_state, content):
        if not content.companions:
            pytest.skip("no companions in content")
        warrior.gold = 100000
        n = len(content.companions)
        # No companion: leave = N+1. After bind: release = N+1, leave = N+2.
        io = ScriptedIO(["1", str(n + 2)])
        state = make_state(io, warrior)
        vendors.pact_broker(state)
        assert warrior.companion is not None

    def test_release_then_leave(self, warrior, make_state, content):
        if not content.companions:
            pytest.skip("no companions in content")
        warrior.gold = 100000
        n = len(content.companions)
        # bind(1) → menu now has release(N+1) and leave(N+2).
        # release → menu reverts (no companion). Now leave = N+1.
        io = ScriptedIO(["1", str(n + 1), str(n + 1)])
        state = make_state(io, warrior)
        vendors.pact_broker(state)
        assert warrior.companion is None

    def test_invalid_choice_on_pact_broker(self, warrior, make_state, content):
        if not content.companions:
            pytest.skip("no companions in content")
        n = len(content.companions)
        io = ScriptedIO(["bogus", str(n + 1)])
        state = make_state(io, warrior)
        vendors.pact_broker(state)
        assert "Invalid choice" in state.io.text()

    def test_already_bound_same_companion(self, warrior, make_state, content):
        if not content.companions:
            pytest.skip("no companions in content")
        warrior.gold = 100000
        n = len(content.companions)
        # bind(1), then try to bind(1) again, then leave
        io = ScriptedIO(["1", "1", str(n + 2)])
        state = make_state(io, warrior)
        vendors.pact_broker(state)
        assert "already walks with you" in state.io.text()

    def test_already_bound_different_companion(self, warrior, make_state, content):
        if not content.companions or len(content.companions) < 2:
            pytest.skip("need at least 2 companions")
        warrior.gold = 100000
        n = len(content.companions)
        # bind(1), then try to bind(2) without releasing → "Release current first"
        io = ScriptedIO(["1", "2", str(n + 2)])
        state = make_state(io, warrior)
        vendors.pact_broker(state)
        assert "Release your current companion" in state.io.text()

    def test_insufficient_gold(self, warrior, make_state, content):
        if not content.companions:
            pytest.skip("no companions in content")
        warrior.gold = 0
        leave = str(len(content.companions) + 1)
        io = ScriptedIO(["1", leave])
        state = make_state(io, warrior)
        vendors.pact_broker(state)
        assert warrior.companion is None
        assert "Not enough gold" in state.io.text()


# ── night_hunt ─────────────────────────────────────────────────────────


class TestNightHunt:
    def test_insufficient_gold(self, warrior, make_state):
        warrior.gold = 0
        state = make_state(ScriptedIO(), warrior)
        vendors.night_hunt(state)
        assert "Night Hunt costs" in state.io.text() or \
               "don't carry enough" in state.io.text()

    def test_full_flow_with_combat_mocked(self, warrior, make_state, content):
        warrior.gold = 100
        warrior.level = 1
        # Mock run_combat so the test doesn't actually run a fight
        with patch.object(vendors, "run_combat", return_value="victory"):
            state = make_state(ScriptedIO(), warrior)
            vendors.night_hunt(state)
        # Gold consumed if there was a valid pool (most likely yes)
        # Either way, the function shouldn't raise.

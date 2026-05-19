"""The location graph: travel, signposting, encounters, the boss and the shop."""
from conftest import StubRandom, make_state

from terminalquest import locations
from terminalquest.locations import GREATER_POTION_COST
from terminalquest.player import Player
from terminalquest.ui import ScriptedIO


def _player(content):
    return Player("Hero", "warrior", content.classes["warrior"])


def _strong_player(content):
    """A player who one-shots any enemy, for deterministic fight outcomes."""
    player = _player(content)
    player.attack = 1000
    player.max_hp = player.hp = 10000
    return player


def test_location_loop_shows_recommended_levels(content):
    io = ScriptedIO(["8"])  # quit from the Crossroads
    locations.location_loop(make_state(_player(content), content, io, StubRandom()))
    assert "recommended Lv" in io.text()


def test_boss_travel_locked_below_unlock_level(content):
    io = ScriptedIO(["5", "8"])  # try to travel to the boss (sealed), then quit
    locations.location_loop(make_state(_player(content), content, io, StubRandom()))
    text = io.text()
    assert "sealed" in text
    assert "VICTORY" not in text


def test_boss_victory_ends_the_game(content):
    player = _strong_player(content)
    player.level = 5  # the summit unlocks at level 5
    io = ScriptedIO(["5", "1", "1"])  # travel to summit -> challenge -> attack
    locations.location_loop(make_state(player, content, io, StubRandom()))
    text = io.text()
    assert "VICTORY" in text
    assert "Thank you for playing" in text


def test_run_encounter_returns_boss_victory(content):
    state = make_state(_strong_player(content), content, ScriptedIO(["1"]), StubRandom())
    encounter = content.locations["summit"]["encounters"][0]
    assert locations.run_encounter(state, encounter) == "boss_victory"


def test_run_encounter_normal_victory_is_plain_victory(content):
    state = make_state(_strong_player(content), content, ScriptedIO(["1"]), StubRandom())
    encounter = content.locations["forest"]["encounters"][0]
    assert locations.run_encounter(state, encounter) == "victory"


def test_overlevel_travel_warns_and_can_turn_back(content):
    # level 1 vs Mountain (recommended level 5): travel -> warned -> turn back -> quit
    io = ScriptedIO(["4", "2", "8"])
    locations.location_loop(make_state(_player(content), content, io, StubRandom()))
    text = io.text()
    assert "recommended for level" in text
    assert "turn back" in text.lower()


def test_travel_into_a_zone_fight_and_return(content):
    # travel to the forest, win a fight, travel back to the Crossroads, quit
    io = ScriptedIO(["2", "1", "1", "2", "8"])
    state = make_state(_strong_player(content), content, io, StubRandom())
    locations.location_loop(state)
    text = io.text()
    assert "Dark Forest" in text
    assert "You defeated" in text
    assert state.current_location == "crossroads"


def test_shop_buys_greater_potion(content):
    player = _player(content)
    player.gold = 100
    locations.shop(make_state(player, content, ScriptedIO(["2", "5"]), StubRandom()))
    assert "Greater Potion" in player.inventory
    assert player.gold == 100 - GREATER_POTION_COST


def test_shop_attack_upgrade_renumbered_to_option_three(content):
    player = _player(content)
    player.gold = 200
    starting_attack = player.attack
    locations.shop(make_state(player, content, ScriptedIO(["3", "5"]), StubRandom()))
    assert player.attack == starting_attack + 5

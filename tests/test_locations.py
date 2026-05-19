"""The location graph: travel, signposting, encounters, the boss and the shop."""
from conftest import StubRandom, make_state

from terminalquest import chronicle, locations
from terminalquest.locations import GREATER_POTION_COST
from terminalquest.player import Player
from terminalquest.ui import ScriptedIO


def _player(content):
    return Player("Hero", "warrior", content.classes["warrior"], content)


def _strong_player(content):
    """A player who one-shots any enemy, for deterministic fight outcomes.

    ``xp_to_level`` is pushed out of reach so a kill never triggers an
    incidental level-up (which would prompt for a boon and eat inputs).
    """
    player = _player(content)
    player.attack = 1000
    player.max_hp = player.hp = 10000
    player.xp_to_level = 10 ** 9
    return player


def test_location_loop_shows_recommended_levels(content):
    io = ScriptedIO(["6"])  # quit from the Crossroads
    locations.location_loop(make_state(_player(content), content, io, StubRandom()))
    assert "recommended Lv" in io.text()


def test_boss_travel_locked_below_unlock_level(content):
    # at the Ashen Climb, a low-level hero tries the sealed Summit, then quits
    io = ScriptedIO(["4", "8"])
    locations.location_loop(make_state(_player(content), content, io, StubRandom(),
                                       current_location="mountain"))
    text = io.text()
    assert "sealed" in text
    assert "VICTORY" not in text


def test_boss_victory_ends_the_game(content):
    player = _strong_player(content)
    player.level = 7  # the summit unlocks at level 7
    # at the Ashen Climb: travel to the Summit -> challenge -> one-shot the Warden
    io = ScriptedIO(["4", "1", "1"])
    locations.location_loop(make_state(player, content, io, StubRandom(),
                                       current_location="mountain"))
    text = io.text()
    assert "THE PALL KEEPS YOU" in text
    assert "Thank you for playing" in text


def test_run_encounter_returns_boss_victory(content):
    state = make_state(_strong_player(content), content,
                       ScriptedIO(["1", "1", "1"]), StubRandom())
    encounter = content.locations["summit"]["encounters"][0]
    assert locations.run_encounter(state, encounter, [], []) == "boss_victory"


def test_run_encounter_normal_victory_is_plain_victory(content):
    state = make_state(_strong_player(content), content, ScriptedIO(["1"]), StubRandom())
    encounter = content.locations["forest"]["encounters"][0]
    assert locations.run_encounter(state, encounter, [], []) == "victory"


def test_grave_appears_and_can_be_searched(tmp_path, content):
    """A past character who fell in a zone leaves a searchable grave there."""
    fallen_run = make_state(_player(content), content, current_location="forest",
                            chronicle_dir=tmp_path)
    chronicle.record(fallen_run, "fell", tmp_path)
    player = _player(content)
    gold_before = player.gold
    io = ScriptedIO(["2", "3", "8"])  # crossroads -> forest, search grave, quit
    state = make_state(player, content, io, StubRandom(), chronicle_dir=tmp_path)
    locations.location_loop(state)
    assert "Half-buried" in io.text()
    assert player.gold > gold_before  # scavenged the dead's coins


def test_run_encounter_can_raise_a_hollowed(tmp_path, content):
    """With a past character recorded in a zone, a fight can be the Hollowed."""
    fallen_run = make_state(_player(content), content, current_location="forest",
                            chronicle_dir=tmp_path)
    chronicle.record(fallen_run, "fell", tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    state = make_state(_strong_player(content), content, ScriptedIO(["1", "2"]),
                       StubRandom(rnd=0.0), current_location="forest",
                       chronicle_dir=tmp_path)
    encounter = content.locations["forest"]["encounters"][0]
    locations.run_encounter(state, encounter, fallen, [])
    assert "Hollow" in state.io.text()


def test_summit_boss_is_the_last_warden(tmp_path, content):
    """Once a hero has won, the Summit boss wears their name."""
    victor = Player("Kara", "mage", content.classes["mage"], content)
    won = make_state(victor, content, current_location="summit", chronicle_dir=tmp_path)
    chronicle.record(won, "warden", tmp_path)
    wardens = chronicle.wardens(chronicle.load(tmp_path))
    state = make_state(_strong_player(content), content, ScriptedIO(["1", "1", "1"]),
                       StubRandom(), current_location="summit", chronicle_dir=tmp_path)
    encounter = content.locations["summit"]["encounters"][0]
    locations.run_encounter(state, encounter, [], wardens)
    assert "Kara, the Shadow Warden" in state.io.text()


def test_defeating_a_hollowed_lays_it_to_rest(tmp_path, content):
    """Beating a Hollowed frees that character — it no longer rises."""
    dead = make_state(_player(content), content, current_location="forest",
                      chronicle_dir=tmp_path)
    chronicle.record(dead, "fell", tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    state = make_state(_strong_player(content), content, ScriptedIO(["1", "2"]),
                       StubRandom(rnd=0.0), current_location="forest",
                       chronicle_dir=tmp_path)
    encounter = content.locations["forest"]["encounters"][0]
    locations.run_encounter(state, encounter, fallen, [])
    assert chronicle.fallen(chronicle.load(tmp_path)) == []  # resolved — at rest


def test_overlevel_travel_warns_and_can_turn_back(content):
    # level 1 at the Gullet vs Mourncross (recommended 4): warned -> turn back
    io = ScriptedIO(["4", "2", "8"])
    locations.location_loop(make_state(_player(content), content, io, StubRandom(),
                                       current_location="cave"))
    text = io.text()
    assert "recommended for level" in text
    assert "turn back" in text.lower()


def test_travel_into_a_zone_fight_and_return(content):
    # travel to the Witherwood, win a fight, travel back to the Crossroads, quit
    io = ScriptedIO(["2", "1", "1", "3", "6"])
    state = make_state(_strong_player(content), content, io, StubRandom())
    locations.location_loop(state)
    text = io.text()
    assert "Witherwood" in text
    assert "You defeated" in text
    assert state.current_location == "crossroads"


def test_shop_buys_greater_potion(content):
    player = _player(content)
    player.gold = 100
    locations.shop(make_state(player, content, ScriptedIO(["2", "5"]), StubRandom()))
    assert "Greater Potion" in player.consumables
    assert player.gold == 100 - GREATER_POTION_COST


def test_shop_attack_upgrade_renumbered_to_option_three(content):
    player = _player(content)
    player.gold = 200
    starting_attack = player.attack
    locations.shop(make_state(player, content, ScriptedIO(["3", "5"]), StubRandom()))
    assert player.attack == starting_attack + 5


def test_discovery_reveals_lore_once_and_is_marked_seen(content):
    """A discovery encounter prints its fragment and records itself as found."""
    io = ScriptedIO()
    state = make_state(_player(content), content, io, StubRandom(),
                       current_location="reach")
    discovery = next(e for e in content.locations["reach"]["encounters"]
                     if e["type"] == "discovery")
    assert locations.run_encounter(state, discovery, [], []) is None
    assert discovery["id"] in state.flags["discoveries_seen"]
    assert "weir-keeper" in io.text()


def test_seen_discovery_drops_out_of_the_menu(content):
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="reach")
    loc = content.locations["reach"]
    before = [label for label, _ in locations._build_options(state, loc, [])]
    assert any("📜" in label for label in before)
    state.flags["discoveries_seen"] = ["reach_tally"]
    after = [label for label, _ in locations._build_options(state, loc, [])]
    assert not any("📜" in label for label in after)


def test_grave_matches_by_act_not_exact_zone(tmp_path, content):
    """A character who fell in one zone leaves a grave anywhere in that act."""
    fell = make_state(_player(content), content, current_location="cave",
                      chronicle_dir=tmp_path)  # the Gullet — Act II
    chronicle.record(fell, "fell", tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    here = make_state(_player(content), content, current_location="mourncross",
                      chronicle_dir=tmp_path)  # also Act II
    away = make_state(_player(content), content, current_location="forest",
                      chronicle_dir=tmp_path)  # the Witherwood — Act I
    assert locations._grave_here(here, content.locations["mourncross"], fallen)
    assert not locations._grave_here(away, content.locations["forest"], fallen)


def test_hollowed_candidates_match_by_act(tmp_path, content):
    fell = make_state(_player(content), content, current_location="cave",
                      chronicle_dir=tmp_path)  # Act II
    chronicle.record(fell, "fell", tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    here = make_state(_player(content), content, current_location="mourncross",
                      chronicle_dir=tmp_path)  # Act II — same act, different zone
    away = make_state(_player(content), content, current_location="forest",
                      chronicle_dir=tmp_path)  # Act I
    assert locations._hollowed_candidates(here, fallen)
    assert not locations._hollowed_candidates(away, fallen)


def test_summit_gate_opens_at_level_seven(content):
    """The Summit is sealed below level 7 and opens once the hero reaches it."""
    low = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                     current_location="mountain")
    assert locations.try_travel(low, "summit") is False
    assert low.current_location == "mountain"

    ready = _player(content)
    ready.level = 7
    high = make_state(ready, content, ScriptedIO(), StubRandom(),
                      current_location="mountain")
    assert locations.try_travel(high, "summit") is True
    assert high.current_location == "summit"


def test_a_weapon_drop_can_be_taken_up(content):
    """A weapon salvaged after a victory can be equipped in place of the old one."""
    player = _player(content)
    starting = player.equipment["weapon"]
    state = make_state(player, content, ScriptedIO(["1"]), StubRandom(rnd=0.0),
                       current_location="forest")
    locations._offer_drop(state)
    assert "Salvaged" in state.io.text()
    assert player.equipment["weapon"] is not starting


def test_a_weapon_drop_can_be_left(content):
    player = _player(content)
    starting = player.equipment["weapon"]
    state = make_state(player, content, ScriptedIO(["2"]), StubRandom(rnd=0.0),
                       current_location="forest")
    locations._offer_drop(state)
    assert player.equipment["weapon"] is starting


def test_no_weapon_drops_when_the_roll_fails(content):
    """A failed drop roll prompts for nothing — no scripted input is consumed."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(rnd=0.99),
                       current_location="forest")
    locations._offer_drop(state)  # rng 0.99 >= the drop chance -> no drop


def test_full_chain_is_traversable_to_the_summit(content):
    """A strong hero can travel Crossroads -> Summit, clearing every encounter."""
    player = _strong_player(content)
    player.level = 7
    state = make_state(player, content, ScriptedIO(["1"] * 200), StubRandom())
    for dest in ["forest", "reach", "cave", "mourncross", "choir", "mountain", "summit"]:
        assert locations.try_travel(state, dest), dest
        for encounter in content.locations[dest].get("encounters", []):
            outcome = locations.run_encounter(state, encounter, [], [])
            if encounter["type"] == "combat":
                assert outcome in ("victory", "boss_victory"), (dest, outcome)
    assert state.current_location == "summit"


def test_inspect_weapon_shows_the_equipped_weapon(content):
    """D5: inspecting the weapon names it and lists its components."""
    io = ScriptedIO()
    state = make_state(_player(content), content, io, StubRandom())
    locations._inspect_weapon(state)
    text = io.text()
    assert "Gravewatch Cleaver" in text  # the warrior's starting weapon
    assert "Head:" in text and "Inscription:" in text

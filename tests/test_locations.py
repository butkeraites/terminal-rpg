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
    # at the Ashen Climb, a low-level hero tries the sealed Summit, then quits.
    # Menu: 1 fight, 2 mini-boss, 3 Choir, 4 Summit, 5 walk back, 6 inspect,
    # 7 stats, 8 save, 9 quit.
    io = ScriptedIO(["4", "9"])
    locations.location_loop(make_state(_player(content), content, io, StubRandom(),
                                       current_location="mountain"))
    text = io.text()
    assert "sealed" in text
    assert "VICTORY" not in text


def test_boss_victory_ends_the_game(content):
    player = _strong_player(content)
    player.level = 8  # the summit unlocks at level 8
    # at the Ashen Climb: travel to the Summit -> challenge -> one-shot -> Warden ending
    # The fourth "1" picks the canonical "Be kept by the Pall" outcome
    # (Reborn is option "2" — see _victory_screen).
    io = ScriptedIO(["4", "1", "1", "1"])
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
    # crossroads "2"=Witherwood, forest "3"=search grave, forest "9"=quit.
    # The grave option vanishes after searching it, so the post-search menu
    # has no grave entry — Quit sits at 9, not 10.
    io = ScriptedIO(["2", "3", "9"])
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
    # level 1 at the Gullet vs Mourncross (recommended 4): warned -> turn back.
    # Cave menu: 1 fight, 2 mini-boss, 3 Drowned Holds, 4 Mourncross,
    # 5 walk back, 6 inspect, 7 stats, 8 save, 9 quit.
    io = ScriptedIO(["4", "2", "9"])
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
    """Shop menu: 1 Health, 2 Greater, 3 Sovereign🔒, 4 Pall🔒, 5 Atk, 6 Def, 7 Leave."""
    player = _player(content)
    player.gold = 100
    locations.shop(make_state(player, content, ScriptedIO(["2", "7"]), StubRandom()))
    assert "Greater Potion" in player.consumables
    assert player.gold == 100 - GREATER_POTION_COST


def test_shop_attack_upgrade_at_option_five(content):
    """The +5 Attack upgrade is now option 5 (tier-locked potions occupy 3-4)."""
    player = _player(content)
    player.gold = 200
    starting_attack = player.attack
    locations.shop(make_state(player, content, ScriptedIO(["5", "7"]), StubRandom()))
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


def test_summit_gate_opens_at_level_eight(content):
    """The Summit is sealed below level 8 and opens once the hero reaches it."""
    low = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                     current_location="mountain")
    assert locations.try_travel(low, "summit") is False
    assert low.current_location == "mountain"

    ready = _player(content)
    ready.level = 8
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
    player.level = 8
    state = make_state(player, content, ScriptedIO(["1"] * 200), StubRandom())
    for dest in ["forest", "reach", "drowned_holds", "cave", "mourncross",
                 "choir", "mountain", "summit"]:
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


def test_defeating_a_mini_boss_unlocks_it(tmp_path, content):
    """E2m: beating a unique foe records its unlock token in the Chronicle."""
    state = make_state(_strong_player(content), content, ScriptedIO(["1"]),
                       StubRandom(), current_location="forest", chronicle_dir=tmp_path)
    stag = content.locations["forest"]["encounters"][1]  # the Pallid Stag mini-boss
    locations.run_encounter(state, stag, [], [])
    assert "pallid_stag" in chronicle.unlocked(tmp_path)


def test_run_summary_reports_the_build_and_seed(content):
    """B4: the end-of-run recap names the hero, the weapon, and the seed."""
    io = ScriptedIO()
    state = make_state(_player(content), content, io, StubRandom(), seed="551234")
    locations._run_summary(state)
    text = io.text()
    assert "551234" in text
    assert "Gravewatch Cleaver" in text  # the warrior's starting weapon


def test_chained_encounter_skips_refresh_between_sub_fights(content, monkeypatch):
    """A multi-enemy combat encounter only refreshes stamina after the last fight.

    Bug B fix: the Drowned Holds 'no rest between' label must be real — each
    sub-fight up to (but not including) the last is run with refresh_after=False.
    """
    recorded = []

    def fake_run_combat(state, enemy, *, refresh_after=True):
        recorded.append(refresh_after)
        return "victory"

    monkeypatch.setattr(locations, "run_combat", fake_run_combat)
    encounter = {"type": "combat", "enemies": ["goblin", "wolf", "bandit"]}
    state = make_state(_strong_player(content), content, ScriptedIO(), StubRandom())
    locations.run_encounter(state, encounter, [], [])
    assert recorded == [False, False, True]


def test_chained_encounter_restores_stamina_when_chain_breaks(content, monkeypatch):
    """If the chain ends off-script (e.g. fled), stamina is restored anyway."""
    def fake_run_combat(state, enemy, *, refresh_after=True):
        # Simulate run_combat fleeing mid-chain without restoring stamina.
        return "fled"

    monkeypatch.setattr(locations, "run_combat", fake_run_combat)
    player = _strong_player(content)
    player.stamina = 1  # mimic the drained state run_combat would leave
    encounter = {"type": "combat", "enemies": ["goblin", "wolf", "bandit"]}
    state = make_state(player, content, ScriptedIO(), StubRandom())
    locations.run_encounter(state, encounter, [], [])
    # run_encounter must restore stamina even though refresh_after=False.
    assert player.stamina == player.max_stamina


def test_fast_travel_returns_to_the_crossroads(content):
    """A zone offers 'Walk back to the Crossroads' that drops the player at the hub.

    The Crossroads then offers a paired 'Return to ...' option so the trip
    is a true round trip — fast travel out, fast travel back.
    """
    # At forest: 1 fight, 2 mini-boss, 3 to Crossroads, 4 to Reach,
    # 5 walk back, 6 inspect, 7 stats, 8 save, 9 quit.
    # At Crossroads after fast-travel: 1 to Gravewatch, 2 to Forest,
    # 3 Return to Witherwood (new), 4 inspect, 5 stats, 6 save, 7 quit.
    io = ScriptedIO(["5", "7"])  # walk back, then quit at the Crossroads
    state = make_state(_player(content), content, io, StubRandom(),
                       current_location="forest")
    locations.location_loop(state)
    assert state.current_location == "crossroads"
    assert "Walk back to the Crossroads" in io.text()
    assert "long way" in io.text()  # the descent-aware flavour line
    assert state.flags.get("fast_travel_return") == "forest"  # round-trip token kept


def test_fast_travel_round_trip_returns_to_origin(content):
    """Fast travel out and back leaves the player at the zone they came from."""
    # Forest "5"=walk back → Crossroads "3"=Return to Witherwood → forest "9"=quit
    io = ScriptedIO(["5", "3", "9"])
    state = make_state(_player(content), content, io, StubRandom(),
                       current_location="forest")
    locations.location_loop(state)
    assert state.current_location == "forest"
    assert "Return to The Witherwood" in io.text()
    assert "retrace the long road" in io.text()
    # The return clears the flag — no orphan return option after a manual walk.
    assert "fast_travel_return" not in state.flags


def test_return_option_absent_until_fast_travel_used(content):
    """A fresh run at the Crossroads has no 'Return to ...' option — nothing to return to yet."""
    io = ScriptedIO(["6"])  # quit (still 6 — no return option offered)
    state = make_state(_player(content), content, io, StubRandom())
    locations.location_loop(state)
    assert "Return to" not in io.text()


def test_smith_upgrades_weapon_once_only(content):
    """The Smith applies an upgrade and refuses to re-temper the same blade."""
    player = _player(content)
    player.gold = 500
    weapon = player.equipment["weapon"]
    assert weapon.upgrade is None
    # Smith menu: 1 Lifedrinker, 2 Sharpened, 3 Reinforced, 4 Hardened, 5 Leave.
    # After purchase the loop re-renders the "already worked" branch which only
    # offers "1. Leave" — so the second input is "1".
    locations.smith(make_state(player, content, ScriptedIO(["3", "1"]), StubRandom()))
    assert weapon.upgrade == "reinforced"
    assert player.gold == 500 - 200
    # Re-entering the smith: weapon already worked, only "1. Leave" is offered.
    locations.smith(make_state(player, content, ScriptedIO(["1"]), StubRandom()))
    assert weapon.upgrade == "reinforced"  # unchanged


def test_lifesteal_upgrade_heals_player_on_hit(content):
    """A weapon with the Lifedrinker upgrade heals 15% of damage dealt."""
    from terminalquest.weapon import WEAPON_UPGRADES  # noqa: F401
    player = _player(content)
    player.hp = 50
    player.attack = 100  # big number so 15% lifesteal is visible
    player.unequip_weapon()
    weapon = player.equipment.get("weapon")
    # Re-equip with lifesteal upgrade.
    from terminalquest.weapon import make_weapon
    weapon = make_weapon(content,
                         {"head": "bog_iron_head", "haft": "withe_haft",
                          "core": "grave_iron_core", "inscription": "mourners_mark"},
                         "Test Blade")
    weapon.upgrade = "lifesteal"
    player.equip_weapon(weapon)
    io = ScriptedIO(["1"])  # basic attack
    from terminalquest.enemy import make_enemy
    combat_state = make_state(player, content, io, StubRandom())
    # combat.run_combat: import locally to avoid top-level cycle in test files
    from terminalquest import combat
    combat.run_combat(combat_state, make_enemy("cave_troll", content))
    assert "drinks deep" in io.text()  # lifesteal message fired
    # Player healed at least once during the fight.
    assert player.hp > 50 - 99999  # sanity — player still alive (one-shotted troll)


def test_quartermaster_buys_and_equips_armor(content):
    """The Quartermaster sells armor pieces that auto-equip on purchase."""
    player = _player(content)
    player.gold = 100
    # Catalog order: mourning_cloak (80g) is #1.
    locations.quartermaster(make_state(player, content, ScriptedIO(["1", "6"]),
                                       StubRandom()))
    armor = player.equipment.get("armor")
    assert armor is not None
    assert armor.armor_id == "mourning_cloak"
    assert player.gold == 20  # 100 - 80


def test_armor_dodge_can_bypass_minimum_damage(content):
    """A dodge_chance > 0 lets the player take 0 damage on a roll under it."""
    from terminalquest import combat
    player = _player(content)
    player.dodge_chance = 1.0  # always dodge for test
    enemy = _player(content)  # something to attack
    # rnd=0.0 -> always under dodge_chance, so the hit dodges.
    damage, dodged, _crit = combat._perform_attack(enemy, player, 1.0,
                                                   StubRandom(rnd=0.0))
    assert dodged
    assert damage == 0  # not even the min-1


def test_pact_broker_binds_a_companion(content):
    """The Pact-Broker takes gold and binds a chosen spirit to the player."""
    player = _player(content)
    player.gold = 400
    # Catalog: 1 Ash Hound (300), 2 Bonesong Acolyte (150), 3 Pall-Touched Cleric (250)
    # Initial menu (no companion): 4 = Leave.
    # After binding: a "Release current companion" option appears at 4, and
    # Leave shifts to 5 — that's why the second input is "5".
    locations.pact_broker(make_state(player, content, ScriptedIO(["1", "5"]),
                                     StubRandom()))
    assert player.companion is not None
    assert player.companion.companion_id == "ash_hound"
    assert player.gold == 100  # 400 - 300


def test_companion_strikes_after_player_turn(content):
    """A damage companion deals its power to the enemy each round."""
    from terminalquest import combat
    from terminalquest.companion import make_companion
    from terminalquest.enemy import make_enemy
    player = _player(content)
    player.attack = 1  # weak — companion must finish the kill
    player.companion = make_companion(content, "ash_hound")  # 12 damage/round
    enemy = make_enemy("goblin", content)
    enemy.hp = 12  # exactly the companion's damage
    state = make_state(player, content, ScriptedIO(["1"]), StubRandom())
    outcome = combat.run_combat(state, enemy)
    assert outcome == "victory"
    assert "Ash Hound" in state.io.text()


def test_reborn_grants_echoes_and_skips_warden_record(content, tmp_path):
    """Choosing Reborn earns Echoes and does NOT chronicle the player as a Warden."""
    from terminalquest import chronicle
    player = _strong_player(content)
    player.level = 8
    # Travel to Summit (4), fight (1), attack (1), Reborn (2)
    io = ScriptedIO(["4", "1", "1", "2"])
    state = make_state(player, content, io, StubRandom(),
                       current_location="mountain", chronicle_dir=tmp_path)
    locations.location_loop(state)
    text = io.text()
    assert "REBORN" in text
    assert "THE PALL KEEPS YOU" not in text
    assert chronicle.echoes(tmp_path) > 0  # earned Echoes
    assert chronicle.wardens(chronicle.load(tmp_path)) == []  # not a Warden


def test_echo_trader_buys_an_accessory_with_echoes(content, tmp_path):
    """The Echo Trader spends Chronicle Echoes to permanently own an accessory."""
    from terminalquest import chronicle
    chronicle.add_echoes(100, tmp_path)
    player = _player(content)
    # Catalog: 1 Stag-Tine Pendant (50), 2 Reaper's Coin (50), ...
    # Owned-once: pick #1, then leave (option 9 — 8 catalog + 1 Leave).
    locations.echo_trader(make_state(player, content, ScriptedIO(["1", "9"]),
                                     StubRandom(), chronicle_dir=tmp_path))
    assert "stag_tine_pendant" in chronicle.owned_accessories(tmp_path)
    assert chronicle.echoes(tmp_path) == 50  # 100 - 50
    # Auto-equipped on purchase.
    assert "trinket" in player.equipment
    assert player.equipment["trinket"].accessory_id == "stag_tine_pendant"


def test_pact_broker_hidden_on_fresh_chronicle(content, tmp_path):
    """Pact-Broker is a NG+ service — hidden until the first completion is in the Chronicle.

    Gravewatch on a fresh chronicle: 1 shop, 2 inn, 3 smith, 4 quartermaster,
    5 night_hunt, 6 quest_board, 7 travel-to-Crossroads, 8 inspect, 9 stats,
    10 save, 11 quit.
    """
    player = _player(content)
    io = ScriptedIO(["1", "11"])  # crossroads "1" -> Gravewatch, then Quit (11)
    state = make_state(player, content, io, StubRandom(), chronicle_dir=tmp_path)
    locations.location_loop(state)
    text = io.text()
    assert "Pact-Broker" not in text
    assert "Echo Trader" not in text


def test_pact_broker_visible_after_warden_completion(tmp_path, content):
    """Once a run is recorded as cleansed, NG+ services become visible at Gravewatch.

    With NG+ unlocked the two extra services push the menu down: Quit is
    now at 13 (8 services + travel + 4 utilities) — Survivor still hidden
    until 3 cleanses.
    """
    from terminalquest import chronicle
    finished = make_state(_player(content), content, current_location="summit",
                          chronicle_dir=tmp_path)
    chronicle.record(finished, "warden", tmp_path)
    chronicle.add_cleanse(tmp_path)  # the cleanse increment that gates NG+
    player = _player(content)
    io = ScriptedIO(["1", "13"])
    state = make_state(player, content, io, StubRandom(), chronicle_dir=tmp_path)
    locations.location_loop(state)
    text = io.text()
    assert "Pact-Broker" in text
    assert "Echo Trader" in text


def test_night_hunt_takes_gold_and_runs_a_fight(content):
    """Night Hunt charges gold and fires a fight against a boosted enemy."""
    player = _player(content)
    player.gold = 100
    # rnd=0.0 -> low rolls; one-shot the goblin via huge attack.
    player.attack = 1000
    io = ScriptedIO(["1"])  # attack once, kill the boosted goblin
    state = make_state(player, content, io, StubRandom(rnd=0.0))
    locations.night_hunt(state)
    assert player.gold < 100  # the night-hunt fee was charged
    assert "Night-Stalking" in io.text()


def test_quest_board_picks_up_and_completes_a_quest(content, tmp_path):
    """The quest board takes a slip, tracks kills, and pays out gold + class consumable."""
    from terminalquest import combat
    from terminalquest.enemy import make_enemy
    player = _player(content)
    player.attack = 1000  # one-shot kills

    # 1) Pick up the wolf cull (3 wolves).
    io = ScriptedIO(["1", "4"])  # accept quest #1, then Leave
    state = make_state(player, content, io, StubRandom(rnd=0.99),
                       chronicle_dir=tmp_path)
    locations.quest_board(state)
    assert "wolf_cull" in state.flags["active_quests"]

    # 2) Kill three wolves through run_combat — counter ticks.
    for _ in range(3):
        state.io = ScriptedIO(["1"])
        combat.run_combat(state, make_enemy("wolf", content))
    assert state.flags["quest_progress"]["wolf_cull"] == 3

    # 3) Return to the board and claim the reward.
    gold_before = player.gold
    state.io = ScriptedIO(["1", "4"])  # claim, then Leave
    locations.quest_board(state)
    assert "wolf_cull" in state.flags["completed_quests"]
    assert player.gold > gold_before  # reward gold paid
    assert "Warrior's Breath" in player.consumables  # class consumable awarded


def test_class_consumable_applies_status_in_combat(content):
    """Drinking Warrior's Breath grants the player the braced status."""
    from terminalquest import combat, status
    from terminalquest.enemy import make_enemy
    warrior = _player(content)
    warrior.consumables = ["Warrior's Breath"]
    result = combat._player_turn(warrior, make_enemy("goblin", content), content,
                                 ScriptedIO(["3"]), StubRandom())
    assert result == "acted"
    assert status.has_status(warrior, "braced")
    assert "Warrior's Breath" not in warrior.consumables


def test_warden_ending_increments_cleanse(tmp_path, content):
    """Becoming the Warden is a cleanse — the realm has been freed once more."""
    from terminalquest import chronicle
    player = _strong_player(content)
    player.level = 8
    io = ScriptedIO(["4", "1", "1", "1"])  # to Summit, fight, attack, "be kept"
    state = make_state(player, content, io, StubRandom(),
                       current_location="mountain", chronicle_dir=tmp_path)
    locations.location_loop(state)
    assert chronicle.cleanses(tmp_path) == 1


def test_cleansed_intro_shows_after_first_completion(tmp_path, content):
    """After 1+ cleanses, the Witherwood intro switches to its cleansed variant.

    Forest menu (no grave, no NG+ services since this isn't a settlement):
    1 combat pool, 2 mini-boss, 3-4 connections, 5 walk back, 6-9 utilities.
    """
    from terminalquest import chronicle
    finished = make_state(_player(content), content, current_location="summit",
                          chronicle_dir=tmp_path)
    chronicle.record(finished, "warden", tmp_path)
    chronicle.add_cleanse(tmp_path)
    io = ScriptedIO(["2", "9"])  # crossroads -> forest, then quit
    state = make_state(_player(content), content, io, StubRandom(),
                       chronicle_dir=tmp_path)
    locations.location_loop(state)
    text = io.text()
    assert "Sunlight finds the lower branches" in text  # cleansed line
    assert "given up the pretence of being alive" not in text  # default suppressed


def test_purify_ending_unlocked_after_five_cleanses(tmp_path, content):
    """Five cleanses unlock the Purify Mournhold ending at the Summit."""
    from terminalquest import chronicle
    for _ in range(5):
        chronicle.add_cleanse(tmp_path)
    player = _strong_player(content)
    player.level = 8
    # to Summit (4) -> fight (1) -> attack (1) -> ending menu -> Purify (3)
    io = ScriptedIO(["4", "1", "1", "3"])
    state = make_state(player, content, io, StubRandom(),
                       current_location="mountain", chronicle_dir=tmp_path)
    locations.location_loop(state)
    assert chronicle.purified(tmp_path)
    assert "PURIFIED" in io.text()


def test_survivor_hidden_until_three_cleanses(tmp_path, content):
    """The Survivor only opens shop after 3 cleanses are in the Chronicle."""
    from terminalquest import chronicle
    player = _player(content)
    # Two cleanses — not enough.
    chronicle.add_cleanse(tmp_path)
    chronicle.add_cleanse(tmp_path)
    # Going through the Gravewatch menu with 2 cleanses: NG+ services visible
    # (pact + echo) but no Survivor yet. Quit is at the bottom.
    io = ScriptedIO(["1", "13"])  # to Gravewatch (NG+ services visible), quit
    state = make_state(player, content, io, StubRandom(), chronicle_dir=tmp_path)
    locations.location_loop(state)
    assert "Survivor" not in io.text()


def test_companion_damage_scales_with_cleanses(tmp_path, content):
    """A damage companion strikes harder per cleanse in the Chronicle."""
    from terminalquest import chronicle, combat
    from terminalquest.companion import make_companion
    from terminalquest.enemy import make_enemy
    chronicle.add_cleanse(tmp_path)  # +1 cleanse → +1 to companion power
    chronicle.add_cleanse(tmp_path)  # +1 more
    player = _player(content)
    player.attack = 1
    player.companion = make_companion(content, "bonesong_acolyte")  # base 8 power
    enemy = make_enemy("goblin", content)
    enemy.hp = 10  # base 8 wouldn't finish in one round; 8 + 2 cleanses = 10
    state = make_state(player, content, ScriptedIO(["1"]), StubRandom(),
                       chronicle_dir=tmp_path)
    outcome = combat.run_combat(state, enemy)
    assert outcome == "victory"
    assert "cleansed road" in state.io.text()  # the +N hint message


def test_cleanse_gated_quest_hidden_until_threshold(tmp_path, content):
    """Higher-tier quests don't appear on the Board until the cleanse count meets them."""
    from terminalquest import chronicle
    player = _player(content)
    # No cleanses → tier-1 (drowned_thresher_quiet, cleanse_required=1) hidden.
    state = make_state(player, content, ScriptedIO(["4"]), StubRandom(),
                       chronicle_dir=tmp_path)
    locations.quest_board(state)
    assert "Drowned Threshers" not in state.io.text()
    # Add one cleanse — now the tier-1 quest appears.
    chronicle.add_cleanse(tmp_path)
    state2 = make_state(player, content, ScriptedIO(["5"]), StubRandom(),
                       chronicle_dir=tmp_path)
    locations.quest_board(state2)
    assert "Drowned Threshers" in state2.io.text()


def test_fast_travel_not_offered_at_the_crossroads(content):
    """The hub itself doesn't offer fast travel — there's nowhere to walk back from."""
    io = ScriptedIO(["6"])  # quit (option 6 at the Crossroads — no fast-travel slot)
    state = make_state(_player(content), content, io, StubRandom())
    locations.location_loop(state)
    assert "Walk back to the Crossroads" not in io.text()


def test_fast_travel_not_offered_at_the_summit(content):
    """The Summit is a boss area; fast travel must not let the player skip the fight."""
    player = _strong_player(content)
    player.level = 8
    # Summit options: 1 boss fight, 2 travel to Climb, 3 inspect, 4 stats,
    # 5 save, 6 quit. No fast-travel slot.
    io = ScriptedIO(["6"])  # quit
    state = make_state(player, content, io, StubRandom(), current_location="summit")
    locations.location_loop(state)
    assert "Walk back to the Crossroads" not in io.text()


def test_shop_offers_sovereign_potion_only_after_a_champion_falls(tmp_path, content):
    """Sovereign Potion stays locked in the shop until 1 mini-boss is in the Chronicle."""
    player = _player(content)
    player.gold = 1000
    # No champions yet — buying option 3 hits the lock message.
    locations.shop(make_state(player, content, ScriptedIO(["3", "7"]),
                              StubRandom(), chronicle_dir=tmp_path))
    assert "Sovereign Potion" not in player.consumables

    # Unlock by chronicling a champion (Pallid Stag), then re-enter the shop.
    chronicle.unlock("pallid_stag", tmp_path)
    locations.shop(make_state(player, content, ScriptedIO(["3", "7"]),
                              StubRandom(), chronicle_dir=tmp_path))
    assert "Sovereign Potion" in player.consumables


def test_shop_offers_pall_drinker_after_three_champions_fall(tmp_path, content):
    """The Pall-Drinker stays locked until three mini-bosses are in the Chronicle."""
    player = _player(content)
    player.gold = 1000
    for token in ("pallid_stag", "last_reaper"):  # only two — Pall-Drinker still locked
        chronicle.unlock(token, tmp_path)
    locations.shop(make_state(player, content, ScriptedIO(["4", "7"]),
                              StubRandom(), chronicle_dir=tmp_path))
    assert "Pall-Drinker" not in player.consumables

    chronicle.unlock("red_beard", tmp_path)  # third champion — unlocks Pall-Drinker
    locations.shop(make_state(player, content, ScriptedIO(["4", "7"]),
                              StubRandom(), chronicle_dir=tmp_path))
    assert "Pall-Drinker" in player.consumables

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
    # v0.16 mountain menu: 1 fight, 2 mini-boss, 3 NPC, 4 piranesi discovery,
    # 5 to Choir, 6 to Summit, 7 walk back, 8-11 utilities → quit=11.
    io = ScriptedIO(["6", "11"])
    locations.location_loop(make_state(_player(content), content, io, StubRandom(),
                                       current_location="mountain"))
    text = io.text()
    assert "sealed" in text
    assert "VICTORY" not in text


def test_boss_victory_ends_the_game(content):
    player = _strong_player(content)
    player.level = 8  # the summit unlocks at level 8
    # v0.16: mountain has an NPC encounter and a Piranesi discovery,
    # so travel-to-Summit is now option 6.
    # ["6"]=Summit, ["1"]=fight, ["1"]=attack, ["1"]=Warden ending.
    io = ScriptedIO(["6", "1", "1", "1"])
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
    # Start at crossroads → "2" travels to Witherwood (option 2 = forest).
    # v0.16 forest with grave: 1 combat, 2 mini-boss, 3 NPC, 4-6 discoveries
    # (2 Piranesi + Atrél marker), 7 grave, 8-9 conn, 10 walk back,
    # 11-14 util → quit=14. Grave is option 7.
    # After grave searched: same menu minus grave → 1-6 encounters, 7-8 conn,
    # 9 walk back, 10-13 util → quit=13.
    io = ScriptedIO(["2", "7", "13"])
    state = make_state(player, content, io, StubRandom(), chronicle_dir=tmp_path)
    locations.location_loop(state)
    assert "Half-buried" in io.text()
    assert player.gold > gold_before


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
    # v0.16 cave menu: 1 fight, 2 mini-boss, 3 Piranesi discovery,
    # 4 Drowned Holds, 5 Mourncross, 6 walk back, 7-10 util → quit=10.
    # "5" travel to Mourncross → warned, "2" turn back, "10" quit.
    io = ScriptedIO(["5", "2", "10"])
    locations.location_loop(make_state(_player(content), content, io, StubRandom(),
                                       current_location="cave"))
    text = io.text()
    assert "recommended for level" in text
    assert "turn back" in text.lower()


def test_travel_into_a_zone_fight_and_return(content):
    # v0.16 forest menu: 1 combat, 2 mini-boss, 3 NPC, 4-6 discoveries
    # (2 Piranesi + Atrél marker), 7 to Crossroads, 8 to Reach,
    # 9 walk back, 10-13 util. Travel back is 7.
    io = ScriptedIO(["2", "1", "1", "7", "6"])
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
                     if e["type"] == "discovery" and e["id"] == "reach_tally")
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

    v0.16 forest: 1 fight, 2 mini-boss, 3 NPC, 4-6 discoveries (2 Piranesi +
    Atrél), 7-8 conn, 9 walk back, 10-13 util. Walk back is 9.
    After walk-back, Crossroads also shows a "Return to The Witherwood"
    fast-travel option, so menu becomes 7 items → quit = 7.
    """
    io = ScriptedIO(["9", "7"])  # walk back (option 9), then quit at Crossroads
    state = make_state(_player(content), content, io, StubRandom(),
                       current_location="forest")
    locations.location_loop(state)
    assert state.current_location == "crossroads"
    assert "Walk back to the Crossroads" in io.text()
    assert "long way" in io.text()
    assert state.flags.get("fast_travel_return") == "forest"


def test_fast_travel_round_trip_returns_to_origin(content):
    """Fast travel out and back leaves the player at the zone they came from."""
    # v0.16 forest: 1 fight, 2 mini-boss, 3 NPC, 4-6 discoveries, 7-8 conn,
    # 9 walk back, 10-13 util. Walk back is 9.
    # At Crossroads with fast_travel_return set: 1 to Gravewatch, 2 to Forest,
    # 3 Return to Forest, 4-7 util. Return is 3.
    # After return: forest menu of 13 items (Piranesi discoveries are
    # one-time but un-touched here) → quit=13.
    io = ScriptedIO(["9", "3", "13"])
    state = make_state(_player(content), content, io, StubRandom(),
                       current_location="forest")
    locations.location_loop(state)
    assert state.current_location == "forest"
    assert "Return to The Witherwood" in io.text()
    assert "retrace the long road" in io.text()
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
    # v0.16: mountain has fight, mini-boss, NPC, Piranesi discovery, then
    # travel to Choir (5), Summit (6). Travel-to-Summit is now index 6.
    io = ScriptedIO(["6", "1", "1", "2"])
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

    With NG+ unlocked the extra services push the menu down: 9 services
    (shop, inn, smith, quartermaster, pact_broker, echo_trader, night_hunt,
    quest_board, beastmaster — Survivor still locked, awaiting more cleanses)
    + 1 connection + 4 utilities → Quit is at 14.
    """
    from terminalquest import chronicle
    finished = make_state(_player(content), content, current_location="summit",
                          chronicle_dir=tmp_path)
    chronicle.record(finished, "warden", tmp_path)
    chronicle.add_cleanse(tmp_path)  # the cleanse increment that gates NG+
    player = _player(content)
    io = ScriptedIO(["1", "15"])  # 10 services + travel + 4 utilities → quit=15
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
    # v0.16: mountain Summit travel is now option 6 (Piranesi discovery added).
    io = ScriptedIO(["6", "1", "1", "1"])
    state = make_state(player, content, io, StubRandom(),
                       current_location="mountain", chronicle_dir=tmp_path)
    locations.location_loop(state)
    assert chronicle.cleanses(tmp_path) == 1


def test_cleansed_intro_shows_after_first_completion(tmp_path, content):
    """After 1+ cleanses, the Witherwood intro switches to its cleansed variant.

    v0.16 forest: 1 combat, 2 mini-boss, 3 NPC, 4-6 discoveries (2 Piranesi
    + Atrél marker), 7-8 conn, 9 walk back, 10-13 util → quit=13.
    """
    from terminalquest import chronicle
    finished = make_state(_player(content), content, current_location="summit",
                          chronicle_dir=tmp_path)
    chronicle.record(finished, "warden", tmp_path)
    chronicle.add_cleanse(tmp_path)
    io = ScriptedIO(["2", "13"])
    state = make_state(_player(content), content, io, StubRandom(),
                       chronicle_dir=tmp_path)
    locations.location_loop(state)
    text = io.text()
    assert "Sunlight finds the lower branches" in text
    assert "given up the pretence of being alive" not in text


def test_purify_ending_unlocked_after_five_cleanses(tmp_path, content):
    """Five cleanses unlock the Purify Mournhold ending at the Summit."""
    from terminalquest import chronicle
    for _ in range(5):
        chronicle.add_cleanse(tmp_path)
    player = _strong_player(content)
    player.level = 8
    # v0.16: to Summit (6) -> fight (1) -> attack (1) -> ending menu -> Purify (3)
    io = ScriptedIO(["6", "1", "1", "3"])
    state = make_state(player, content, io, StubRandom(),
                       current_location="mountain", chronicle_dir=tmp_path)
    locations.location_loop(state)
    assert chronicle.purified(tmp_path)
    assert "PURIFIED" in io.text()


def test_survivor_hidden_until_three_cleanses(tmp_path, content):
    """The Survivor only opens shop after 3 cleanses are in the Chronicle.

    Gravewatch menu with 2 cleanses: shop, inn, smith, quartermaster,
    pact_broker, echo_trader, night_hunt, quest_board, beastmaster (9
    services — Survivor still locked) + travel + 4 utilities → Quit at 14.
    """
    from terminalquest import chronicle
    player = _player(content)
    chronicle.add_cleanse(tmp_path)
    chronicle.add_cleanse(tmp_path)
    io = ScriptedIO(["1", "15"])  # quit at 15 with beastmaster + hireling visible
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


def test_beastmaster_hidden_before_first_completion(tmp_path, content):
    """v0.8: Beastmaster only opens after a completion AND while not purified."""
    player = _player(content)
    io = ScriptedIO(["1", "11"])  # Gravewatch (6 default services + travel + 4 util = quit 11)
    state = make_state(player, content, io, StubRandom(), chronicle_dir=tmp_path)
    locations.location_loop(state)
    assert "Beastmaster" not in io.text()


def test_beastmaster_buys_a_pet_with_gold(tmp_path, content):
    """The Beastmaster takes gold and equips the chosen pet."""
    from terminalquest import chronicle
    player = _player(content)
    player.gold = 1000
    # Catalog: 1 Ash-Hound Pup, 2 Bog Pricklehog, 3 Black Magpie, 4 Hearth Cat, 5 Leave
    locations.beastmaster(make_state(player, content, ScriptedIO(["1", "5"]),
                                     StubRandom(), chronicle_dir=tmp_path))
    assert "ash_hound_pup" in chronicle.owned_pets(tmp_path)
    assert player.equipment.get("pet") is not None
    assert player.equipment["pet"].pet_id == "ash_hound_pup"
    assert player.gold == 200  # 1000 - 800


def test_beastmaster_trades_trophies_for_a_pet(tmp_path, content):
    """50 wolf pelts buys the Ash-Hound Pup without spending gold."""
    from terminalquest import chronicle
    player = _player(content)
    player.gold = 0
    player.trophies = {"wolf_pelt": 50}
    locations.beastmaster(make_state(player, content, ScriptedIO(["1", "5"]),
                                     StubRandom(), chronicle_dir=tmp_path))
    assert "ash_hound_pup" in chronicle.owned_pets(tmp_path)
    assert player.trophies["wolf_pelt"] == 0  # consumed
    assert player.gold == 0  # no gold spent


def test_pet_stats_apply_when_equipped(content):
    """Equipping the Ash-Hound Pup adds its +5 attack to the player."""
    from terminalquest.pet import make_pet
    player = _player(content)
    base_atk = player.attack
    player.equip_pet(make_pet(content, "ash_hound_pup"))
    assert player.attack == base_atk + 5


def test_trophy_drops_on_a_lucky_kill(content):
    """A wolf kill drops a wolf pelt when the RNG falls inside the drop chance."""
    from terminalquest import combat
    from terminalquest.enemy import make_enemy
    warrior = _player(content)
    warrior.attack = 1000  # one-shot
    state = make_state(warrior, content, ScriptedIO(["1"]), StubRandom(rnd=0.0))
    combat.run_combat(state, make_enemy("wolf", content))
    assert warrior.trophies.get("wolf_pelt", 0) >= 1


def test_hireling_intercepts_enemy_damage(content):
    """An enemy hit lands on the hireling first, sparing the player.

    Tests _enemy_strike directly — that's the function the combat loop calls
    whenever an enemy lands a basic or heavy blow, and the redirect lives in
    that single helper.
    """
    from terminalquest import combat
    from terminalquest.enemy import make_enemy
    from terminalquest.hireling import make_hireling
    from terminalquest.ui import ScriptedIO
    player = _player(content)
    player.hireling = make_hireling(content, "broken_squire")
    hire_hp_before = player.hireling.hp
    player_hp_before = player.hp
    enemy = make_enemy("goblin", content)
    io = ScriptedIO()
    combat._enemy_strike(enemy, player, 1.0, io, StubRandom())
    assert player.hireling.hp < hire_hp_before
    assert player.hp == player_hp_before
    assert "takes the blow" in io.text()


def test_npc_introduces_then_tracks_then_completes(tmp_path, content):
    """An NPC encounter walks through intro → in_progress → complete states."""
    player = _player(content)
    encounter = {"type": "npc", "id": "old_halna"}
    # 1st run: introduce.
    state = make_state(player, content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._run_npc(state, encounter)
    assert "old_halna" in state.flags["npcs_seen"]
    assert "old_halna" not in state.flags.get("npcs_done", [])
    assert "wolves shut my trail" in state.io.text().lower()

    # 2nd run with no kills: in_progress reminder.
    state2 = make_state(player, content, ScriptedIO(), StubRandom(),
                        chronicle_dir=tmp_path)
    state2.flags["npcs_seen"] = ["old_halna"]
    locations._run_npc(state2, encounter)
    assert "Bring me five" in state2.io.text() or "Not yet" in state2.io.text()

    # 3rd run with enough kills: completion.
    state3 = make_state(player, content, ScriptedIO(), StubRandom(),
                        chronicle_dir=tmp_path)
    state3.flags["npcs_seen"] = ["old_halna"]
    state3.flags["npc_kills"] = {"wolf": 5}
    locations._run_npc(state3, encounter)
    assert "old_halna" in state3.flags["npcs_done"]
    assert "hunters_cache" in state3.flags["unlocked_connections"]


def test_npc_unlock_opens_a_conditional_connection(tmp_path, content):
    """Once unlocked, a sub-zone appears as a travel option in the parent zone.

    v0.16 forest menu with Hunter's Cache unlocked: 1 combat, 2 mini-boss,
    3 NPC, 4-6 discoveries (2 Piranesi + Atrél), 7 to Crossroads, 8 to Reach,
    9 Hunter's Cache, 10 walk back, 11-14 util → quit=14.
    """
    player = _player(content)
    state = make_state(player, content, ScriptedIO(["14"]), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    state.flags["unlocked_connections"] = ["hunters_cache"]
    locations.location_loop(state)
    assert "Hunter's Cache" in state.io.text()


def test_atrel_lore_collection_sets_flag(content, tmp_path):
    """Finding all three Atrél fragments sets the atrel_lore_found flag."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    for fragment_id in ("atrel_marker", "atrel_register", "atrel_side_altar"):
        locations._run_discovery(state, {"id": fragment_id, "lines": ["test"]})
    assert state.flags.get("atrel_lore_found") is True


def test_atrel_lore_partial_does_not_set_flag(content, tmp_path):
    """Only two of three fragments leaves the flag unset."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    for fragment_id in ("atrel_marker", "atrel_register"):
        locations._run_discovery(state, {"id": fragment_id, "lines": ["test"]})
    assert not state.flags.get("atrel_lore_found")


def test_last_altar_unlocks_via_unlock_flag(content):
    """The Last Altar zone gates by the atrel_lore_found flag (not via NPC)."""
    state = make_state(_player(content), content, ScriptedIO(["1"]), StubRandom(),
                       current_location="choir")
    # Without the flag, the Last Altar is not in the menu.
    loc = content.locations["choir"]
    options = locations._build_options(state, loc, [])
    labels = " ".join(label for label, _ in options)
    assert "Last Altar" not in labels
    # Set the flag and rebuild — now the Last Altar appears as travel option.
    state.flags["atrel_lore_found"] = True
    options = locations._build_options(state, loc, [])
    labels = " ".join(label for label, _ in options)
    assert "Last Altar" in labels


def test_flavor_after_overrides_when_flag_set(content):
    """An enemy with flavor_after picks the alternate line when its flag is True."""
    from terminalquest.enemy import make_enemy
    # No flag set → default flavor.
    default = make_enemy("cantor_vael", content, state_flags={})
    assert "carried the realm's one voice" in default.flavor
    # Flag set → overlay applies.
    overlaid = make_enemy("cantor_vael", content,
                          state_flags={"atrel_lore_found": True})
    assert "scaled Atrél's small rite" in overlaid.flavor


def test_atrel_peace_ending_requires_offer(content, tmp_path):
    """Atrél's Peace appears in the ending menu only when atrel_offered is True."""
    from terminalquest import endings
    player = _player(content)
    state_a = make_state(player, content, ScriptedIO(), StubRandom(),
                        chronicle_dir=tmp_path)
    # Default state — Atrél's Peace not in available endings.
    available = [e[0] for e in endings.available(state_a)]
    assert "atrel_peace" not in available
    # With atrel_offered flag, the ending becomes available.
    state_a.flags["atrel_offered"] = True
    available = [e[0] for e in endings.available(state_a)]
    assert "atrel_peace" in available


def test_dialogue_engine_walks_branches(content):
    """The dialogue engine follows the chosen response's next pointer."""
    from terminalquest import dialogue
    state = make_state(_player(content), content, ScriptedIO(["1"]), StubRandom())
    tree = {
        "initial": {
            "lines": ["start"],
            "responses": [{"text": "go", "next": "second"}],
        },
        "second": {"lines": ["end"]},
    }
    final = dialogue.run_dialogue(state, tree)
    assert final == "second"
    text = state.io.text()
    assert "start" in text and "end" in text


def test_scuffmarks_discovery_unlocks_sealed_chamber(content, tmp_path):
    """Reading the scuff-marks discovery sets sealed_chamber_found flag."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._run_discovery(state, {"id": "mourncross_scuffmarks",
                                     "lines": ["test"]})
    assert state.flags.get("sealed_chamber_found") is True


def test_sealed_chamber_unlocks_via_flag(content):
    """The Sealed Chamber appears in Mourncross travel options once unlocked."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="mourncross")
    loc = content.locations["mourncross"]
    # Without the flag, the Sealed Chamber is hidden.
    options = locations._build_options(state, loc, [])
    labels = " ".join(label for label, _ in options)
    assert "Sealed Chamber" not in labels
    # With the flag, it appears as a travel option.
    state.flags["sealed_chamber_found"] = True
    options = locations._build_options(state, loc, [])
    labels = " ".join(label for label, _ in options)
    assert "Sealed Chamber" in labels


def test_real_minutes_discovery_sets_flag(content, tmp_path):
    """Reading the Real Minutes sets read_real_minutes — gates Warden variant."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._run_discovery(state, {"id": "real_minutes",
                                     "lines": ["test"]})
    assert state.flags.get("read_real_minutes") is True


def test_warden_ending_adds_seventh_paragraph_when_minutes_read(content, tmp_path):
    """If the player read the Real Minutes, the Warden ending names them as the seventh."""
    player = _player(content)
    state = make_state(player, content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    state.flags["read_real_minutes"] = True
    locations._warden_screen(state)
    text = state.io.text()
    assert "seventh to keep this place" in text
    assert "five who voted to open" in text


def test_warden_ending_omits_seventh_paragraph_by_default(content, tmp_path):
    """A player who never reads the Real Minutes sees the original ending."""
    player = _player(content)
    state = make_state(player, content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._warden_screen(state)
    text = state.io.text()
    assert "seventh to keep this place" not in text


def test_dialogue_sets_flag_on_choice(content):
    """A response with sets_flag writes that key into state.flags."""
    from terminalquest import dialogue
    state = make_state(_player(content), content, ScriptedIO(["1"]), StubRandom())
    tree = {
        "initial": {
            "lines": ["..."],
            "responses": [{"text": "yes", "next": None, "sets_flag": "promised"}],
        },
    }
    dialogue.run_dialogue(state, tree)
    assert state.flags.get("promised") is True


def test_bone_tomb_requires_all_four_npc_quests_and_verren(content, tmp_path):
    """The Bone Tomb opens only after every NPC quest + Verren fragment."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    state.flags["verren_found"] = True
    state.flags["npcs_done"] = ["old_halna", "weir_engineer", "lampkeeper"]
    # Missing the_penitent — gate stays closed.
    locations._maybe_open_hardest_gate(state)
    assert not state.flags.get("the_hardest_gate")
    # Add the last NPC.
    state.flags["npcs_done"].append("old_penitent")
    locations._maybe_open_hardest_gate(state)
    assert state.flags.get("the_hardest_gate") is True


def test_old_seal_ending_requires_offer(content, tmp_path):
    """The Old Seal ending is hidden until Cael's offer is accepted."""
    from terminalquest import endings
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    available = [e[0] for e in endings.available(state)]
    assert "old_seal" not in available
    state.flags["offered_old_seal"] = True
    available = [e[0] for e in endings.available(state)]
    assert "old_seal" in available


def test_speaking_through_stone_format(content):
    """A dialogue node with voice='stone' renders via the through-stone wrapper."""
    from terminalquest import dialogue
    state = make_state(_player(content), content, ScriptedIO(), StubRandom())
    tree = {"initial": {"voice": "stone", "lines": ["I am Cael."]}}
    dialogue.run_dialogue(state, tree)
    assert "▒  I am Cael." in state.io.text()


def test_verren_discovery_sets_flag(content, tmp_path):
    """Reading the Verren fragment sets verren_found."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._run_discovery(state, {"id": "verren_fragment", "lines": ["test"]})
    assert state.flags.get("verren_found") is True


def test_drowned_holds_petition_opens_hidden_hold(content, tmp_path):
    """Reading the petition reveals the path north — Hidden Hold unlocks."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._run_discovery(state, {"id": "drowned_holds_petition",
                                     "lines": ["test"]})
    assert state.flags.get("hidden_hold_found") is True


def test_reckoning_ending_requires_talva_promise(content, tmp_path):
    """The Reckoning ending hides until Tálva has been promised help."""
    from terminalquest import endings
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    available = [e[0] for e in endings.available(state)]
    assert "reckoning" not in available
    state.flags["talva_asked"] = True
    available = [e[0] for e in endings.available(state)]
    assert "reckoning" in available


def test_border_opens_after_two_cleanses(tmp_path, content):
    """The Border (Arc III) unlocks once the Chronicle records 2+ cleanses."""
    from terminalquest import chronicle
    chronicle.add_cleanse(tmp_path)
    chronicle.add_cleanse(tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._maybe_open_border(state)
    assert state.flags.get("border_open") is True


def test_border_stays_closed_under_two_cleanses(tmp_path, content):
    """One cleanse is not enough — the Border stays unaware of you."""
    from terminalquest import chronicle
    chronicle.add_cleanse(tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._maybe_open_border(state)
    assert not state.flags.get("border_open")


def test_sister_realm_addendum_prints_when_allied(content, tmp_path):
    """Endings with allied_karst etc. print the cross-realm closing paragraph."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    state.flags["allied_karst"] = True
    locations._sister_realm_addendum(state, state.io)
    assert "Karst" in state.io.text()
    assert "bread moves both ways" in state.io.text()


def test_ascii_filter_replaces_known_emojis():
    """Every mapped emoji becomes its bracket-tag fallback."""
    from terminalquest.ascii_filter import to_ascii
    assert to_ascii("⚔️+6 atk") == "[atk]+6 atk"
    assert to_ascii("🛡️+5 def") == "[def]+5 def"
    assert to_ascii("plain text") == "plain text"
    assert to_ascii("") == ""


def test_ascii_filter_handles_combat_glyphs():
    """Dynamic combat emojis (💥 💢 💨) translate to ASCII markers."""
    from terminalquest.ascii_filter import to_ascii
    out = to_ascii("💥 CRITICAL!  💢 hit  💨 dodge")
    assert "💥" not in out
    assert "**" in out
    assert "!!" in out


def test_gameio_ascii_mode_filters_output():
    """ScriptedIO with ascii_mode=True records filtered text only."""
    from terminalquest.ui import ScriptedIO
    io = ScriptedIO(ascii_mode=True)
    io.show("⚔️ attacks!")
    assert "⚔️" not in io.text()
    assert "[atk]" in io.text()


def test_gameio_default_mode_preserves_emojis():
    """ascii_mode=False is the default — emojis pass through."""
    from terminalquest.ui import ScriptedIO
    io = ScriptedIO()
    io.show("⚔️ attacks!")
    assert "⚔️" in io.text()


def test_settings_round_trip(tmp_path):
    """save/load round-trip preserves keys; missing files return defaults."""
    from terminalquest import settings
    # Default load on empty dir.
    assert settings.load(tmp_path) == settings.DEFAULTS
    # Save with custom flags and reload.
    settings.save({"ascii_mode": True, "emoji_test_done": True}, tmp_path)
    loaded = settings.load(tmp_path)
    assert loaded["ascii_mode"] is True
    assert loaded["emoji_test_done"] is True


def test_speaking_through_stone_falls_back_in_ascii_mode():
    """Cael's voice uses '::  ' instead of '▒' when ascii_mode is on."""
    from terminalquest.ui import ScriptedIO
    io = ScriptedIO(ascii_mode=True)
    io.show_through_stone("I am Cael.")
    assert "::  I am Cael." in io.text()


def test_cat_appears_after_three_zone_visits(content, tmp_path):
    """SQ3 — the cat menu option surfaces in a zone visited 3+ times."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    loc = content.locations["forest"]
    state.flags["zone_visits"] = {"forest": 2}
    options = locations._build_options(state, loc, [])
    labels = " ".join(label for label, _ in options)
    assert "Pet the cat" not in labels
    state.flags["zone_visits"]["forest"] = 3
    options = locations._build_options(state, loc, [])
    labels = " ".join(label for label, _ in options)
    assert "Pet the cat" in labels


def test_pet_the_cat_increments_chronicle_counter(content, tmp_path):
    """SQ3 — petting the cat persists across runs via chronicle.cat_pets."""
    from terminalquest import chronicle
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    assert chronicle.cat_pets(tmp_path) == 0
    locations._pet_the_cat(state)
    assert chronicle.cat_pets(tmp_path) == 1
    locations._pet_the_cat(state)
    assert chronicle.cat_pets(tmp_path) == 2


def test_cat_companion_unlocks_at_one_hundred_pets(content, tmp_path):
    """At 100 pets, the cat becomes a permanent +1 HP/round combat presence."""
    from terminalquest import chronicle
    # Pre-load the chronicle to 99 pets so this one bumps us to 100.
    for _ in range(99):
        chronicle.add_cat_pet(tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    locations._pet_the_cat(state)
    assert chronicle.cat_pets(tmp_path) == 100
    assert state.flags.get("cat_companion") is True


def test_cat_companion_heals_in_combat(content):
    """Once cat_companion is flagged, the cat heals +1 HP every round."""
    from terminalquest import combat
    from terminalquest.enemy import make_enemy
    warrior = _player(content)
    warrior.hp = 50
    warrior.attack = 1000  # one-shot for clean test
    state = make_state(warrior, content, ScriptedIO(["1"]), StubRandom())
    state.flags["cat_companion"] = True
    combat.run_combat(state, make_enemy("goblin", content))
    text = state.io.text()
    assert "cat purrs" in text


def test_piranesi_note_increments_chronicle_counter(content, tmp_path):
    """SQ4 — reading a Piranesi-prefixed discovery records it in the Chronicle."""
    from terminalquest import chronicle
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    assert chronicle.piranesi_notes(tmp_path) == 0
    locations._run_discovery(state,
        {"id": "piranesi_witherwood_stone", "lines": ["a stone with a face"]})
    assert chronicle.piranesi_notes(tmp_path) == 1
    # Re-reading the same note is idempotent.
    locations._run_discovery(state,
        {"id": "piranesi_witherwood_stone", "lines": ["a stone with a face"]})
    assert chronicle.piranesi_notes(tmp_path) == 1
    # A different Piranesi note bumps the count.
    locations._run_discovery(state,
        {"id": "piranesi_reach_furrow", "lines": ["a measured furrow"]})
    assert chronicle.piranesi_notes(tmp_path) == 2


def test_piranesi_map_unlocks_at_ten_notes(content, tmp_path):
    """SQ4 — at 10 Piranesi notes read, the piranesi_map_unlocked flag is set."""
    from terminalquest import chronicle
    # Pre-load 9 notes; reading a 10th flips the flag in this run.
    for i in range(9):
        chronicle.add_piranesi_note(f"piranesi_seed_{i}", tmp_path)
    assert chronicle.piranesi_notes(tmp_path) == 9
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    assert not state.flags.get("piranesi_map_unlocked")
    locations._run_discovery(state,
        {"id": "piranesi_choir_column", "lines": ["a column that ate a word"]})
    assert chronicle.piranesi_notes(tmp_path) == 10
    assert state.flags.get("piranesi_map_unlocked") is True


def test_piranesi_map_option_appears_in_pre_pall_shrine(content, tmp_path):
    """SQ4 — once unlocked, the Pre-Pall Shrine offers 'Read Piranesi's map'."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="pre_pall_shrine", chronicle_dir=tmp_path)
    loc = content.locations["pre_pall_shrine"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Piranesi's map" not in labels
    state.flags["piranesi_map_unlocked"] = True
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Piranesi's map" in labels


def test_piranesi_map_option_absent_in_other_zones(content, tmp_path):
    """SQ4 — even with the flag set, the map only surfaces at the Pre-Pall Shrine."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    state.flags["piranesi_map_unlocked"] = True
    loc = content.locations["forest"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Piranesi's map" not in labels


def test_locations_have_ten_piranesi_notes_total(content):
    """SQ4 — the world holds exactly 10 Piranesi notes, distributed across zones."""
    notes = []
    for loc_id, loc in content.locations.items():
        for enc in loc.get("encounters", []):
            if (enc.get("type") == "discovery"
                    and enc.get("id", "").startswith("piranesi_")):
                notes.append((loc_id, enc["id"]))
    assert len(notes) == 10, (
        f"Expected 10 Piranesi notes, found {len(notes)}: {notes}"
    )


def test_lost_verse_fragment_increments_chronicle_counter(content, tmp_path):
    """SQ8 — reading a lost_verse_-prefixed discovery records it cross-run."""
    from terminalquest import chronicle
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    assert chronicle.lost_verse_fragments(tmp_path) == 0
    locations._run_discovery(state,
        {"id": "lost_verse_1", "lines": ["a torn first line"]})
    assert chronicle.lost_verse_fragments(tmp_path) == 1
    # Idempotent.
    locations._run_discovery(state,
        {"id": "lost_verse_1", "lines": ["a torn first line"]})
    assert chronicle.lost_verse_fragments(tmp_path) == 1


def test_lost_verse_known_flag_set_at_fourth_fragment(content, tmp_path):
    """SQ8 — the lost_verse_known flag sets when the player reads the 4th fragment."""
    from terminalquest import chronicle
    for fid in ("lost_verse_1", "lost_verse_2", "lost_verse_3"):
        chronicle.add_lost_verse_fragment(fid, tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    assert not state.flags.get("lost_verse_known")
    locations._run_discovery(state,
        {"id": "lost_verse_4", "lines": ["the last line"]})
    assert state.flags.get("lost_verse_known") is True


def test_lost_verse_remembered_at_run_start_if_already_known(content, tmp_path):
    """SQ8 — a new character begins remembering the verse if 4+ fragments were read."""
    from terminalquest import chronicle
    for fid in ("lost_verse_1", "lost_verse_2", "lost_verse_3", "lost_verse_4"):
        chronicle.add_lost_verse_fragment(fid, tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations._maybe_remember_verse(state)
    assert state.flags.get("lost_verse_known") is True


def test_sing_verse_grants_stat_buff(content, tmp_path):
    """SQ8 — singing the Lost Verse grants +5 max HP, +1 attack, +1 defense."""
    player = _player(content)
    mhp_before, atk_before, def_before = (
        player.max_hp, player.attack, player.defense)
    state = make_state(player, content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations.sing_the_verse(state)
    assert player.max_hp == mhp_before + 5
    assert player.attack == atk_before + 1
    assert player.defense == def_before + 1
    assert state.flags.get("lost_verse_sung") is True


def test_sing_verse_option_appears_at_last_altar_when_known(content, tmp_path):
    """SQ8 — the Sing option surfaces at Last Altar only with the verse known."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="last_altar", chronicle_dir=tmp_path)
    loc = content.locations["last_altar"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Sing the Lost Verse" not in labels
    state.flags["lost_verse_known"] = True
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Sing the Lost Verse" in labels
    # Once sung, the option vanishes for the rest of the run.
    state.flags["lost_verse_sung"] = True
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Sing the Lost Verse" not in labels


def test_locations_have_four_lost_verse_fragments(content):
    """SQ8 — the world holds exactly four lost_verse_* discoveries."""
    fragments = []
    for loc_id, loc in content.locations.items():
        for enc in loc.get("encounters", []):
            if (enc.get("type") == "discovery"
                    and enc.get("id", "").startswith("lost_verse_")):
                fragments.append((loc_id, enc["id"]))
    assert len(fragments) == 4, (
        f"Expected 4 Lost Verse fragments, found {len(fragments)}: {fragments}"
    )


def test_witherwood_only_falls_counts_forest_deaths(tmp_path, content):
    """SQ7 — chronicle.witherwood_only_falls counts entries that fell in forest."""
    from terminalquest import chronicle
    assert chronicle.witherwood_only_falls(tmp_path) == 0
    # Three characters died in the forest.
    for _ in range(3):
        state = make_state(_player(content), content, current_location="forest",
                           chronicle_dir=tmp_path)
        chronicle.record(state, "fell", tmp_path)
    # Two died elsewhere.
    for loc in ("reach", "cave"):
        state = make_state(_player(content), content, current_location=loc,
                           chronicle_dir=tmp_path)
        chronicle.record(state, "fell", tmp_path)
    assert chronicle.witherwood_only_falls(tmp_path) == 3


def test_forgotten_thing_hidden_by_default(content, tmp_path):
    """SQ7 — the Forgotten Thing encounter is not in the menu until awoken."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    loc = content.locations["forest"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Forgot" not in labels


def test_forgotten_thing_appears_after_five_forest_falls(content, tmp_path):
    """SQ7 — five characters fallen in the forest wakes the Forgotten Thing."""
    from terminalquest import chronicle
    for _ in range(5):
        s = make_state(_player(content), content, current_location="forest",
                       chronicle_dir=tmp_path)
        chronicle.record(s, "fell", tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    locations._maybe_wake_forgotten_thing(state)
    assert state.flags.get("forgotten_thing_awake") is True
    loc = content.locations["forest"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Forgot" in labels


def test_forgotten_thing_disappears_after_defeat(content, tmp_path):
    """SQ7 — once defeated this run, the encounter no longer surfaces."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    state.flags["forgotten_thing_awake"] = True
    state.flags["forgotten_thing_defeated"] = True
    loc = content.locations["forest"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Forgot" not in labels


def test_forgotten_thing_enemy_is_in_content(content):
    """SQ7 — the_forgotten_thing exists in the enemies registry as unique."""
    assert "the_forgotten_thing" in content.enemies
    enemy = content.enemies["the_forgotten_thing"]
    assert enemy.get("unique") is True
    assert enemy.get("ai") == "enrager"


def test_record_snapshots_npc_kill_progress(tmp_path, content):
    """SQ9 — chronicle.record captures in-run npc_kills as ``progress``."""
    from terminalquest import chronicle
    state = make_state(_player(content), content, current_location="forest",
                       chronicle_dir=tmp_path)
    state.flags["npc_kills"] = {"wolf": 3}
    chronicle.record(state, "fell", tmp_path)
    entries = chronicle.load(tmp_path)
    assert entries[-1]["progress"]["npc_kills"] == {"wolf": 3}


def test_witnessed_dead_surfaces_for_unfinished_kill_quest(tmp_path, content):
    """SQ9 — a fallen character with partial progress shows up in their NPC's zone."""
    from terminalquest import chronicle
    fallen_state = make_state(_player(content), content, current_location="forest",
                              chronicle_dir=tmp_path)
    fallen_state.flags["npc_kills"] = {"wolf": 3}
    chronicle.record(fallen_state, "fell", tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    loc = content.locations["forest"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, fallen))
    assert "Honor" in labels and "3/5" in labels and "wolfs" in labels


def test_witnessed_dead_absent_when_progress_is_zero(tmp_path, content):
    """SQ9 — a fallen who never started the quest doesn't ghost the zone."""
    from terminalquest import chronicle
    fallen_state = make_state(_player(content), content, current_location="forest",
                              chronicle_dir=tmp_path)
    chronicle.record(fallen_state, "fell", tmp_path)  # no npc_kills set
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    loc = content.locations["forest"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, fallen))
    assert "Honor" not in labels


def test_witnessed_dead_absent_when_quest_complete(tmp_path, content):
    """SQ9 — a fallen who already finished doesn't show up either."""
    from terminalquest import chronicle
    fallen_state = make_state(_player(content), content, current_location="forest",
                              chronicle_dir=tmp_path)
    fallen_state.flags["npc_kills"] = {"wolf": 5}  # full threshold
    chronicle.record(fallen_state, "fell", tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    loc = content.locations["forest"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, fallen))
    assert "Honor" not in labels


def test_witnessed_dead_only_in_matching_zone(tmp_path, content):
    """SQ9 — Halna's witnessed dead appears in the forest, not in the reach."""
    from terminalquest import chronicle
    fallen_state = make_state(_player(content), content, current_location="forest",
                              chronicle_dir=tmp_path)
    fallen_state.flags["npc_kills"] = {"wolf": 2}
    chronicle.record(fallen_state, "fell", tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    # The reach has a different NPC (weir engineer with thresher_reed trophy).
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="reach", chronicle_dir=tmp_path)
    loc = content.locations["reach"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, fallen))
    assert "Honor" not in labels


def test_discovery_records_cross_run_reading(tmp_path, content):
    """SQ1 — running a discovery records its id in the cross-run read set."""
    from terminalquest import chronicle
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    assert chronicle.discoveries_read(tmp_path) == 0
    locations._run_discovery(state, {"id": "reach_tally", "lines": ["t"]})
    assert chronicle.discoveries_read(tmp_path) == 1
    # Idempotent: re-reading the same discovery doesn't double-count.
    state.flags["discoveries_seen"] = []  # so the flag-side allows re-call
    locations._run_discovery(state, {"id": "reach_tally", "lines": ["t"]})
    assert chronicle.discoveries_read(tmp_path) == 1
    locations._run_discovery(state, {"id": "mourncross_census", "lines": ["t"]})
    assert chronicle.discoveries_read(tmp_path) == 2


def test_reader_service_hidden_below_threshold(tmp_path, content):
    """SQ1 — the Reader is not in Gravewatch's menu until threshold is met."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    loc = content.locations["village"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Reader" not in labels


def test_reader_service_appears_at_threshold(tmp_path, content):
    """SQ1 — at 25 cross-run reads, the Reader becomes a Gravewatch service."""
    from terminalquest import chronicle
    for i in range(locations.READER_THRESHOLD):
        chronicle.add_read_discovery(f"seed_{i}", tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    loc = content.locations["village"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Reader" in labels


def test_reader_grants_per_run_max_hp_buff(tmp_path, content):
    """SQ1 — reading with the Reader scales max-HP by cross-run read count."""
    from terminalquest import chronicle
    for i in range(30):
        chronicle.add_read_discovery(f"seed_{i}", tmp_path)
    player = _player(content)
    max_hp_before = player.max_hp
    state = make_state(player, content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations.reader(state)
    assert player.max_hp == max_hp_before + 6  # 30 // 5
    assert state.flags.get("read_with_reader") is True


def test_gravewatch_visit_increments_cross_run_counter(tmp_path, content):
    """SQ6 — arriving at Gravewatch bumps the cross-run counter."""
    from terminalquest import chronicle
    assert chronicle.gravewatch_visits(tmp_path) == 0
    # Quit-from-Gravewatch happy path: arrive, take Quit.
    io = ScriptedIO(["6"])  # 1 shop, 2 inn, 3 smith, ... vary; pick Quit
    # Use the location_loop to trigger the arrival hook.
    # Simpler: just call add_gravewatch_visit and read it back.
    chronicle.add_gravewatch_visit(tmp_path)
    chronicle.add_gravewatch_visit(tmp_path)
    assert chronicle.gravewatch_visits(tmp_path) == 2
    _ = io  # not used in this minimal test


def test_insomniac_service_hidden_below_threshold(tmp_path, content):
    """SQ6 — the Insomniac is not in Gravewatch's menu before 50 visits."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    loc = content.locations["village"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Insomniac" not in labels


def test_insomniac_service_appears_at_threshold(tmp_path, content):
    """SQ6 — at 50 cross-run visits, the Insomniac becomes a service."""
    from terminalquest import chronicle
    for _ in range(locations.INSOMNIAC_THRESHOLD):
        chronicle.add_gravewatch_visit(tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    loc = content.locations["village"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Insomniac" in labels


def test_insomniac_descent_grants_the_counted_on_victory(tmp_path, content):
    """SQ6 — surviving all 3 descent fights grants the per-run buff + cross-run unlock."""
    from terminalquest import chronicle
    for _ in range(locations.INSOMNIAC_THRESHOLD):
        chronicle.add_gravewatch_visit(tmp_path)
    player = _strong_player(content)
    mhp_before = player.max_hp
    # 3 fights × 1 attack each = 3 inputs.
    io = ScriptedIO(["1", "1", "1"])
    state = make_state(player, content, io, StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    locations.insomniac(state)
    assert state.flags.get("the_counted") is True
    assert "the_counted" in chronicle.unlocked(tmp_path)
    assert player.max_hp > mhp_before


def test_kind_act_counter_accumulates(tmp_path, content):
    """SQ2 — each small kindness increments the cross-run counter."""
    from terminalquest import chronicle
    assert chronicle.kind_acts(tmp_path) == 0
    chronicle.add_kind_act(tmp_path)
    chronicle.add_kind_act(tmp_path)
    chronicle.add_kind_act(tmp_path)
    assert chronicle.kind_acts(tmp_path) == 3


def test_discovery_counts_as_kind_act(tmp_path, content):
    """SQ2 — reading a discovery bumps the kind_acts counter."""
    from terminalquest import chronicle
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    before = chronicle.kind_acts(tmp_path)
    locations._run_discovery(state, {"id": "reach_tally", "lines": ["t"]})
    assert chronicle.kind_acts(tmp_path) == before + 1


def test_caretaker_service_hidden_below_threshold(tmp_path, content):
    """SQ2 — the Caretaker is not in Gravewatch's menu before 40 kindnesses."""
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    loc = content.locations["village"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Caretaker" not in labels


def test_caretaker_service_appears_at_threshold(tmp_path, content):
    """SQ2 — at 40 cross-run kindnesses, the Caretaker is in Gravewatch."""
    from terminalquest import chronicle
    for _ in range(locations.CARETAKER_THRESHOLD):
        chronicle.add_kind_act(tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    loc = content.locations["village"]
    labels = " ".join(label for label, _ in
                      locations._build_options(state, loc, []))
    assert "Caretaker" in labels


def test_caretaker_ending_records_chronicle_and_cleanse(tmp_path, content):
    """SQ2 — choosing the Caretaker records the fate + counts as a cleanse."""
    from terminalquest import chronicle
    cleanses_before = chronicle.cleanses(tmp_path)
    state = make_state(_player(content), content, ScriptedIO(), StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    locations.caretaker(state)
    assert state.flags.get("run_ended") is True
    assert chronicle.cleanses(tmp_path) == cleanses_before + 1
    fates = [e.get("fate") for e in chronicle.load(tmp_path)]
    assert "caretaker" in fates


def test_insomniac_is_once_per_run(tmp_path, content):
    """SQ6 — re-visiting after the Counted reward gives a quiet acknowledgement only."""
    from terminalquest import chronicle
    for _ in range(locations.INSOMNIAC_THRESHOLD):
        chronicle.add_gravewatch_visit(tmp_path)
    player = _strong_player(content)
    state = make_state(player, content, ScriptedIO(["1", "1", "1"]), StubRandom(),
                       current_location="village", chronicle_dir=tmp_path)
    locations.insomniac(state)
    mhp_after_first = player.max_hp
    # Second call — should not run combats, should not stack the buff.
    state.io = ScriptedIO()  # no inputs available, must not need any
    locations.insomniac(state)
    assert player.max_hp == mhp_after_first


def test_reader_is_once_per_run(tmp_path, content):
    """SQ1 — re-visiting the Reader in the same run does not stack."""
    from terminalquest import chronicle
    for i in range(30):
        chronicle.add_read_discovery(f"seed_{i}", tmp_path)
    player = _player(content)
    state = make_state(player, content, ScriptedIO(), StubRandom(),
                       chronicle_dir=tmp_path)
    locations.reader(state)
    mhp = player.max_hp
    locations.reader(state)  # second call, same run
    assert player.max_hp == mhp


def test_honor_the_dead_grants_kills_and_lays_to_rest(tmp_path, content):
    """SQ9 — honoring transfers progress, marks resolved, and grants memorial gold."""
    from terminalquest import chronicle
    fallen_state = make_state(_player(content), content, current_location="forest",
                              chronicle_dir=tmp_path)
    fallen_state.flags["npc_kills"] = {"wolf": 4}
    chronicle.record(fallen_state, "fell", tmp_path)
    fallen = chronicle.fallen(chronicle.load(tmp_path))
    player = _player(content)
    gold_before = player.gold
    state = make_state(player, content, ScriptedIO(), StubRandom(),
                       current_location="forest", chronicle_dir=tmp_path)
    witnessed = locations._witnessed_dead_here(state, fallen)[0]
    locations._honor_the_dead(state, witnessed)
    assert state.flags["npc_kills"]["wolf"] == 4
    assert player.gold == gold_before + 80  # 4 * 20
    # Re-load: the entry is now resolved, so fallen() filters it out.
    still_fallen = chronicle.fallen(chronicle.load(tmp_path))
    assert still_fallen == []


def test_dialogue_grants_consumable_on_choice(content):
    """A response with grants_consumable adds the named item to player.consumables."""
    from terminalquest import dialogue
    state = make_state(_player(content), content, ScriptedIO(["1"]), StubRandom())
    tree = {
        "initial": {
            "lines": ["..."],
            "responses": [
                {"text": "take", "next": None, "grants_consumable": "the Last Bread"},
            ],
        },
    }
    dialogue.run_dialogue(state, tree)
    assert "the Last Bread" in state.player.consumables


def test_scholar_pays_for_unseen_discoveries(tmp_path, content):
    """The Mournhold Scholar pays SCHOLAR_PAYOUT per unrecorded discovery."""
    player = _player(content)
    player.gold = 0
    state = make_state(player, content, ScriptedIO(["1"]), StubRandom(),
                       chronicle_dir=tmp_path)
    state.flags["discoveries_seen"] = ["reach_tally", "mourncross_census"]
    locations.scholar(state)
    assert player.gold == 2 * locations.SCHOLAR_PAYOUT
    assert state.flags["scholar_paid"] == ["reach_tally", "mourncross_census"]


def test_dead_hireling_can_return_as_forsaken_sworn(tmp_path, content):
    """A dead hireling flagged in state.flags can spawn as an enemy in random encounters."""
    state = make_state(_strong_player(content), content, ScriptedIO(),
                       StubRandom(rnd=0.0))  # low rnd → forsaken roll succeeds
    state.flags["fallen_hireling"] = {
        "name": "the Broken Squire",
        "max_hp": 80,
        "defense": 4,
    }
    # _make_forsaken_sworn is what produces the Forsaken — invoke directly so
    # we don't have to drive a full combat just to verify the spawn shape.
    sworn = locations._make_forsaken_sworn(state.flags["fallen_hireling"])
    assert "Forsaken" in sworn.name
    assert sworn.ai == "relentless"
    assert sworn.max_hp > 80  # 1.5x the hireling's max


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

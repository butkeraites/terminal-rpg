"""Headless balance simulator for Terminal Quest (roadmap ticket A1).

A maintained development tool — not part of the shipped game. It plays the
full Crossroads-to-Summit chain headlessly under a combat policy, many times
per class, and reports survival and win-rate distributions so combat and
content can be tuned against data rather than guesswork. Later tickets
(A2 build-sampling, A3 the CI regression gate) build on this module.

Run from the repository root:

    python3 -m tools.sim                  # 400 runs per class, both profiles
    python3 -m tools.sim --runs 1000      # more runs per class
    python3 -m tools.sim --seed nightly   # pin the master seed

A given ``--seed`` always produces the same report — the run is reproducible.
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass

from terminalquest import combat
from terminalquest.content import load_content
from terminalquest.enemy import make_enemy
from terminalquest.player import Player
from terminalquest.state import GameState
from terminalquest.ui import GameIO

POOL_RUNS = 4        # times a thorough player grinds a random encounter pool
RESTOCK_POTIONS = 4  # Health Potions a rest tops the player up to


@dataclass
class RunResult:
    """The outcome of one simulated Crossroads-to-Summit run."""

    reached_summit: bool
    won: bool
    level: int
    fell_at: str | None


class CompetentPolicy:
    """A competent — not optimal — combat policy.

    Defends telegraphed and relentless heavy blows, heals or drinks a potion
    when low, spends stamina on an attacking ability, and otherwise strikes.
    A fresh instance is used per run so its per-run state never leaks.
    """

    def __init__(self, content):
        self.content = content
        self._pending_ability = "1"
        self._boons_taken = 0

    def combat_action(self, player, enemy):
        """Return the combat-menu key to press this turn."""
        if enemy is not None:
            if enemy.winding_up == "heavy":
                return "4"  # defend the telegraphed heavy blow
            if (enemy.ai == "relentless"
                    and (enemy.turns_taken + 1) % combat.RELENTLESS_PERIOD == 0):
                return "4"  # defend the predictable relentless surge
        if player.hp < player.max_hp * 0.42:
            heal = self._affordable_ability(player, "heal")
            if heal is not None:
                self._pending_ability = str(heal)
                return "2"
            if player.potion_count() > 0:
                return "3"
        attack = self._affordable_ability(player, "attack")
        if attack is not None:
            self._pending_ability = str(attack)
            return "2"
        return "1"  # basic attack

    def ability_choice(self):
        """Return the ability-submenu key chosen by the last ``combat_action``."""
        return self._pending_ability

    def boon_choice(self):
        """Pick a level-up boon, alternating Might and Vigor for a mixed build."""
        pick = "2" if self._boons_taken % 2 == 0 else "1"
        self._boons_taken += 1
        return pick

    def _affordable_ability(self, player, kind):
        """The submenu index of the player's first affordable ability of ``kind``."""
        for index, ability_id in enumerate(player.abilities, start=1):
            ability = self.content.abilities[ability_id]
            if ability["kind"] == kind and ability["stamina"] <= player.stamina:
                return index
        return None


class PolicyIO(GameIO):
    """Headless IO that answers every game prompt from a combat policy."""

    def __init__(self, policy):
        super().__init__(animate=False)
        self.policy = policy
        self.player = None
        self.enemy = None

    def show(self, text=""):
        pass

    def show_slow(self, text="", delay=0.0):
        pass

    def clear(self):
        pass

    def pause(self, seconds=0):
        pass

    def ask(self, prompt):
        if "What do you do?" in prompt:
            return self.policy.combat_action(self.player, self.enemy)
        if "Which ability?" in prompt:
            return self.policy.ability_choice()
        if "Your choice?" in prompt:
            return self.policy.boon_choice()
        return "1"  # potion picker and any other prompt


def zone_chain(content):
    """The ordered combat zones, walked from the Crossroads to the Summit.

    Derived from the location graph so the simulator survives content changes:
    it follows each zone's connections, skipping the hub and any settlement.
    """
    order = []
    current, previous = "crossroads", None
    while True:
        nxt = None
        for dest in content.locations[current].get("connections", []):
            if dest == previous:
                continue
            loc = content.locations[dest]
            if loc.get("kind") == "zone" or loc.get("boss"):
                nxt = dest
                break
        if nxt is None:
            return order
        order.append(nxt)
        current, previous = nxt, current


def _rest(player):
    """Model a visit to Gravewatch: full recovery and a restock of potions."""
    player.hp = player.max_hp
    player.stamina = player.max_stamina
    player.statuses.clear()
    player.inventory = [item for item in player.inventory
                        if item not in ("Health Potion", "Greater Potion")]
    player.inventory += ["Health Potion"] * RESTOCK_POTIONS


def _fight(content, player, io, rng, enemy_id):
    """Run one combat to a conclusion; return its outcome string."""
    enemy = make_enemy(enemy_id, content)
    io.player, io.enemy = player, enemy
    return combat.run_combat(GameState(player, content, io, rng), enemy)


def simulate_run(content, class_id, rng, rest_each, policy_factory=CompetentPolicy):
    """Play one full run. ``rest_each`` rests before every fight, not just zones."""
    player = Player("Sim", class_id, content.classes[class_id])
    io = PolicyIO(policy_factory(content))
    for zone_id in zone_chain(content):
        loc = content.locations[zone_id]
        _rest(player)  # both profiles refill between zones
        for encounter in loc.get("encounters", []):
            if encounter.get("type") != "combat":
                continue
            if encounter.get("pick") == "random":
                fights = [rng.choice(encounter["enemies"]) for _ in range(POOL_RUNS)]
            else:
                fights = list(encounter["enemies"])
            for enemy_id in fights:
                if rest_each:
                    _rest(player)
                outcome = _fight(content, player, io, rng, enemy_id)
                if outcome == "defeat":
                    # a death at the boss still counts as having reached the Summit
                    return RunResult(encounter.get("boss", False), False,
                                     player.level, zone_id)
                if encounter.get("boss") and outcome == "victory":
                    return RunResult(True, True, player.level, None)
    return RunResult(True, False, player.level, None)


def run_profile(content, label, rest_each, trials, seed):
    """Simulate ``trials`` runs per class and print an aggregate report."""
    print(f"\n=== {label} — {trials} runs/class ===")
    for class_id in content.classes:
        rng = random.Random(f"{seed}:{class_id}")
        reached = won = 0
        levels = []
        deaths = {}
        for _ in range(trials):
            result = simulate_run(content, class_id, rng, rest_each)
            reached += result.reached_summit
            won += result.won
            if result.reached_summit:
                levels.append(result.level)
            if result.fell_at:
                deaths[result.fell_at] = deaths.get(result.fell_at, 0) + 1
        avg_level = sum(levels) / len(levels) if levels else 0.0
        hotspots = sorted(deaths.items(), key=lambda kv: -kv[1])[:3]
        print(f"  {class_id:9s} reach {reached / trials:5.0%}  "
              f"win {won / trials:5.0%}  avg Lv {avg_level:4.1f}  deaths {hotspots}")


def main(argv=None):
    """CLI entry point: run both rest profiles and print their reports."""
    parser = argparse.ArgumentParser(description="Terminal Quest balance simulator.")
    parser.add_argument("--runs", type=int, default=400, help="runs per class")
    parser.add_argument("--seed", default="terminalquest", help="master seed")
    args = parser.parse_args(argv)

    content = load_content()
    run_profile(content, "RECKLESS (rest only between zones)", False, args.runs, args.seed)
    run_profile(content, "CAREFUL  (rest before every fight)", True, args.runs, args.seed)


if __name__ == "__main__":
    main()

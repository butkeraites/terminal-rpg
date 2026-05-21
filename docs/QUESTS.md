# Quests in Mournhold — The 2000-Quest Design Document

> *"I need 2000 quests. Get as creative as possible. Only appear on super
> specific conditions or depend on super hard conditions — I want depth."*
> — the brief

This is the framework. Like the README, it describes the *shape* of the
quest system, not the snapshot. It is the durable contract between
storyteller and engineer for the long campaign.

---

## The Mandate

Two thousand kill-counter bounties is not depth — it's volume. Every quest
in Mournhold's catalog must earn its place by being *something that could
not have happened to anyone else, available only to a player who has earned
the right to see it.* The current 6 board-bounties are the **entrance** to
the system, not the system.

## The Ten Quest Types

| # | Type | What it does | Allocation |
|---|---|---|---:|
| 1 | **Bounty** | Kill N of enemy X, cleanse-gated, gold reward. The chore tier; the entrance. | 50 |
| 2 | **Trophy** | Bring N of trophy X. Unlocks services, ledger entries, small consumables. | 100 |
| 3 | **Chain** | Quest A unlocks Quest B unlocks Quest C. The bulk of the kingdom's stories. | 600 |
| 4 | **Discovery** | Triggered by reading a specific lore fragment. Rewards reading. | 250 |
| 5 | **Conditional Combat** | Win without being stunned. Kill without a potion. Defeat with the hireling landing the killing blow. | 200 |
| 6 | **Mark-Gated** | Only visible if specific marks have fired on *this* character. | 200 |
| 7 | **Reborn / Cross-Run** | Only on a 2nd+ character. Triggered by previous characters' presence. | 150 |
| 8 | **Class-Specific** | What only one class can be asked to do (50 per class × 5 classes). | 250 |
| 9 | **Endgame / Ending-Approach** | Late-game, gated by prior endings or high level. Opens new endings. | 100 |
| 10 | **Hidden** | Never appears on a board. Triggered by player action. The rarest tier. | 100 |
|   | | **Total** | **2000** |

## The Quest Schema

Quests live in `terminalquest/data/quests.json`. Each entry is a dict.
**All fields except `name`, `needed`, `reward_gold`, `cleanse_required`,
and (`target_enemy` OR `target_trophy`) are optional.**

```jsonc
{
  "name":              "string — display name",
  "flavor":            "string — short prose blurb",

  // Completion (one of)
  "target_enemy":      "enemy_id from enemies.json",
  "target_trophy":     "trophy_name from any enemy's trophy field",
  "completion_condition": "code-name from the conditions enum, see below",

  "needed":            42,           // int > 0
  "reward_gold":       100,          // int >= 0
  "reward_consumables": ["bread"],   // list of consumable names
  "reward_marks":      ["mark_id"],  // marks that fire on completion
  "reward_chronicle_line": "string — appended to the player's Chronicle entry",
  "reward_ending_unlock":  "ending_id — adds to chronicle.unlocks",

  // Gates (ALL must be satisfied)
  "cleanse_required":  3,            // int >= 0
  "min_level":         5,            // int >= 1
  "requires_flag":     "the_counted",
  "requires_flags":    ["a", "b"],
  "requires_mark":     "summit_almost_turned_back",
  "requires_marks":    ["a", "b"],
  "requires_class":    ["cleric"],
  "requires_ending":   ["atrel_peace"],
  "requires_quest":    ["wolf_cull"],         // must have completed this
  "requires_discovery": ["burned_ledger_p17"],
  "requires_chronicle_entry": {"fell_in_zone": "reach"},

  // Anti-requirements (must NOT be true)
  "denies_quest":      ["bandit_hunt"],       // if you've done this, this branch is gone

  // Chain wiring
  "chain_next":        "next_quest_id",       // auto-posts when this completes

  // Hidden quests
  "hidden":            true,                  // never on the board
  "trigger_action":    {                      // what player action triggers it
    "type": "ate_at_helka_bench",
    "params": {}
  }
}
```

### Completion conditions vocabulary (~20 keys)

Conditional Combat quests pick from this small enum, each backed by a
predicate in `combat.py`:

```
no_stun_during_fight       no_potions_in_zone       no_hireling_death
companion_landed_kill      first_strike_yours       killed_in_one_round
fled_then_returned         no_damage_taken          status_cleared
critical_killing_blow      kept_full_stamina        used_no_abilities
killed_with_thrown         pet_assisted             killed_while_low_hp
killed_after_dodging       killed_during_stun       no_healing_received
unarmed_kill               named_them_at_death
```

(The vocabulary is fixed in code; quests refer to keys.)

## The Voice

The kingdom's voice is the marks' voice. Slow, particular, kind in
unexpected places, careful about its dead. Quests are *small specific
attentions* the kingdom asks of you in return for *small specific
kindnesses*. A quest is never a chore. It is always a request that
someone with a face is making.

Bad quest: *Kill 10 wolves.*
Good quest: *Halna's father, before he died, used to hunt these wolves
with a particular blade. Find the blade. Bring it back to her. She has
not asked anyone before because nobody else would have understood why.*

## Engine Roadmap — 10 Phase-1 Batches

Engine work, in shipping order:

1. **Schema acceptance + validation** *(this commit)* — All new fields parse and validate.
2. **Trophy completion** — `target_trophy` quests read `player.trophies` instead of `quest_progress`.
3. **Chain completion + auto-post** — `chain_next` advances on claim.
4. **Mark / class / level / ending gates** — Board catalog filters reuse the marks-engine eligibility patterns.
5. **Discovery gates** — `requires_discovery` reads `state.flags['discoveries_seen']`.
6. **Completion conditions** — 20-key enum, combat-state watchers.
7. **Hidden quest triggers** — Scanner on `zone_arrival` / `save_action`.
8. **Reward writers** — `reward_marks` fires marks; `reward_chronicle_line` appends; `reward_ending_unlock` adds.
9. **Board UI categorization** — Bounty / Chain / Special tabs.
10. **Chronicle integration** — Completed quests recorded on the player's Chronicle entry.

After Phase 1, **Phase 2** ships quest tooling (`tools/quests` with
validation, chain DAG visualisation, orphan detection), then **Phase 3**
authors the 2000 in batches of 25–40 per release across ~50-60 release
cycles.

## Allocation Rationale

- **Chain (600)** is 30% because it's where lore lives. Every named NPC,
  every grave, every discovery can spawn a chain.
- **Discovery (250)** is 12% because it rewards readers — and the kingdom
  *has* readers. Many discoveries already exist; this routes them.
- **Class-Specific (250)** is 50 per class so every class gets equal
  weight; the kingdom marks the player by who they chose to be.
- **Mark-Gated (200)** + **Conditional (200)** are 10% each — they make
  the run feel observed.
- **Trophy (100)**, **Reborn (150)**, **Endgame (100)**, **Hidden (100)**,
  **Bounty (50)** round out the system at smaller weights.

## A Note for Future Contributors

If you are adding quests, keep the voice (see *The Voice* above), keep
the schema honest (validate locally with `python3 -m pytest`), and keep
the chains coherent. A chain whose first step never spawns is a quest
that does not exist; the validator will catch most of these but the
storyteller has to check the framing reads true.

Two thousand is the figure. We reach it the same way we reached 1000
marks: a few per release, sustained over a long arc, every batch
finishable on its own.

---

*The kingdom does not have 2000 quests yet. It will. Each one is a small
specific attention. Walk well.*

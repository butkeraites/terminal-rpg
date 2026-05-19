# Mournhold — Development Roadmap: The Thousand-Hour Universe

*A build roadmap for the development team. Supersedes the prior strategic roadmap.*
*Prepared by the development board: Creative Director, Game Design Director,*
*Systems Director, Production Director. Baselined on the live build (six-zone*
*journey, 79 tests, CI green).*

---

## Mandate

The owner's goal: **a game an engaged player can sink ~1,000 hours into.** The named
pillars are **combinatorial weapons**, **crafting**, **combinatorial problem-solving**,
**deeper ability systems**, and breadth — *"we need to be a universe."*

> **Interpretation flag — "ability three":** the brief here was voice-transcribed and
> partly garbled. We have read it as **tiered ability progression (Tier I/II/III) plus
> a third *category* of ability** (see Epic E3). If the intent was different —
> a third ability *slot*, a third class archetype, etc. — correct E3 and the rest holds.

## The honest premise

A ~6-hour authored story cannot be 1,000 hours, and **1,000 hours cannot be authored** —
no team writes that much content. 1,000 hours is *generated* by systems. Every game that
reaches that depth ceiling (NetHack, Caves of Qud, Path of Exile, Slay the Spire, Hades)
does it the same way: **combinatorial systems + procedural content + meta-progression +
endless escalation.** This roadmap is that pivot.

It is a genuine identity change — from *a grimdark story* to *a combinatorial roguelike
universe with a grimdark story spine*. We do **not** throw the story away. We adopt the
**spine-and-body** model:

- **The spine** — the authored Mournhold myth, the named mini-bosses, the discovery
  fragments. It stays hand-crafted to the current quality bar ("never filler"). It
  becomes the onboarding campaign and the universe's framing.
- **The body** — the procedural, combinatorial roguelike that hangs off the spine and
  supplies ~85% of the playtime.

Mournhold is already closer to this than it looks: it has **permadeath**, the
**Chronicle** (cross-run meta-progression), and a **data-driven** content pipeline. We
are completing a roguelike, not starting one.

## Where 1,000 hours actually comes from

A roguelike run is 45–75 min. 1,000 hours ≈ ~1,000 runs. ~1,000 runs are sustained by
six compounding loops — none of which is "more authored content":

1. **Build variety** — you have not tried build X yet (weapons × abilities × crafting).
2. **The unlock chase** — the Chronicle gates components, abilities, classes, biomes.
3. **Endless escalation** — the Ascension ladder always goes one tier higher.
4. **Procedural novelty** — every world is a different assembly of zones and affixes.
5. **Mastery & collection** — bestiary, component codex, per-class mastery tracks.
6. **The Warden cycle** — your own dead heroes return as the content.

1,000 hours is a **depth ceiling for the most engaged player**, not an average — exactly
as PoE has 40-hour players and 5,000-hour players. We build the ceiling; players choose
their depth.

---

## Workstream epics

Eight epics. Each names its *combinatorial mechanism* (how it multiplies hours) and its
*data architecture* (the JSON the systems consume — designers extend the universe by
editing data, engineers build the systems that read it).

### E1 — Combinatorial Weapons
*The first depth engine, and the most self-contained — start here.*
- **Mechanism:** a weapon is **assembled from slotted components** — Head (damage &
  type), Haft (speed / stamina / crit profile), Core (a combat *proc* keyword), and
  Inscription (a stat / status synergy). 4 slots × ~15 options ≈ 50k base weapons,
  before rolled affix values → effectively unbounded.
- **Engine:** an equipment layer on `Player`; a `Weapon` object; `_perform_attack`
  consults the weapon for damage mods and procs. Procs hook the **existing** combat
  events (on-hit, on-crit, every-Nth-turn, on-kill) and emit the **existing** status
  effects — the status engine is the substrate, not new tech.
- **Data:** `components.json`.
- **Milestones:** M1 equipment system + `Weapon` model · M2 components + procs wired to
  combat · M3 ~60 components across 4 slots + drop tables.

### E2 — Crafting & Materials
*The combinatorial sink — the reason to grind a build.*
- **Mechanism:** materials drop per biome (bog-iron from the Reach, reliquary-bone from
  the Choir…); the **Forge** crafts components, **salvages** loot back to materials, and
  **reforges/transmutes** to gamble on affixes — the ARPG loot loop.
- **Data:** `materials.json`, `recipes.json`.
- **Milestones:** M1 materials + drop tables · M2 the Forge: craft + salvage · M3
  reforge / reroll / transmute (the gamble loop).

### E3 — Ability Trees & Combos
*Combinatorial problem-solving inside combat.*
- **Mechanism:** each class gets a **tiered tree** (Tier I/II/III, ~15–24 abilities); the
  player builds a **loadout** from what they have unlocked — the loadout is the build.
  Abilities are designed to **combo**: "setup" abilities apply a state, "payoff"
  abilities consume it. Adds a **third ability category** beyond active/passive —
  **Stances** (a sustained mode you toggle, reshaping the turn).
- **Data:** `abilities.json` expanded into trees; `combos.json`.
- **Milestones:** M1 ability-tree model + loadout screen · M2 setup/payoff combo
  keyword layer · M3 full trees for all classes + Stances.

### E4 — The Procedural Universe
*"We need to be a universe" — breadth without hand-authoring it.*
- **Mechanism:** zones become **biome templates**; each seeded run **assembles a world**
  from the pool (a roguelike map/Atlas). The authored spine is injected as guaranteed
  beats; procedural zones fill between. Zone **modifiers** reshape rules per run.
- **Data:** `biomes.json` (zone templates), seed-driven world assembly.
- **Milestones:** M1 seeded runs + procedural world assembly · M2 large biome pool +
  zone modifiers · M3 factions + universe breadth (new acts, expanding myth).

### E5 — The Chronicle Meta-Layer & Endless Ascension
*The engine that turns ~150 hours of systems into 1,000.*
- **Mechanism:** the Chronicle becomes the **meta-progression hub** — persistent
  unlocks (components, abilities, classes, biomes), mastery tracks, a codex/bestiary.
  **Endless Ascension:** after the Summit, the Warden cycle becomes an **infinite
  escalating ladder** (cf. Hades heat / PoE maps / StS ascension) — the home of the
  long tail.
- **Milestones:** M1 Chronicle unlocks + mastery · M2 the Ascension ladder · M3
  collection / codex + offline-verifiable leaderboards.

### E6 — Combinatorial Encounters & Enemy Affixes
*Every fight a fresh problem.*
- **Mechanism:** enemies roll **affixes** (armored, enraged, hexing, swift…); 6 AI
  archetypes × affixes = combinatorial threats. Procedural **multi-solution encounters**
  — combat / stat-check / item / class-ability / sacrifice — extend the discovery system
  into branching puzzles.
- **Data:** `affixes.json`, `encounters.json`.
- **Milestones:** M1 enemy affix system · M2 procedural multi-solution encounters · M3
  elite / nemesis enemies, tied to the Chronicle and the Hollowed.

### E7 — Balance & Simulation Infrastructure
*Non-negotiable, and it ships first.*
- **Mechanism:** combinatorial systems **cannot be hand-balanced** — the space is too
  large. The throwaway Monte-Carlo harness used to tune the six-zone world becomes
  **maintained `tools/` infrastructure**: it samples thousands of build × content
  combinations and reports win-rate distributions, dead builds, and degenerate builds.
- **Every later epic depends on it. It is Year 1, M1.**
- **Milestones:** M1 maintained harness + build sampling · M2 regression dashboards ·
  M3 auto-tuning assists.

### E8 — Distribution & Onboarding
*The parallel enabling track — carried forward from the studio dossier.*
- **Mechanism:** the systems must be tested by real players. PyInstaller binaries (no
  Python needed), an itch.io page, PyPI/`pipx`, a Pyodide "play in browser" demo; a
  first-run tutorial that teaches the *systems*; a Windows-terminal compatibility pass;
  an accessibility mode.
- **Re-sequenced:** no longer the Year-1 headline (the owner redirected to depth), but
  early-access distribution lands in **Year 2** — combinatorial systems need players to
  surface degenerate builds.
- **Milestones:** M1 packaged builds + itch early-access · M2 systems onboarding/tutorial
  · M3 v1.0 launch.

---

## Five-year sequencing

| Year | Theme | Epics in flight | Depth ceiling |
|------|-------|-----------------|---------------|
| 1 | The Combinatorial Foundation | E7, run-loop, equipment, **E1** | ~30–50 h |
| 2 | The Build Game | **E2**, **E3**, E6 (affixes), **E8** early access | ~150 h |
| 3 | The Universe | **E4**, E6 (encounters), factions | ~350 h |
| 4 | The Endless | **E5** Ascension, branching endings, mastery | ~700 h |
| 5 | The Living Universe | modding, daily seeds, Definitive Edition | **1,000 h+** |

**Year 1 — The Combinatorial Foundation.** Stand up E7 (the sim harness) first. Formalise
the **run** as the unit of play (seeded, ends in death/victory, feeds the Chronicle).
Build the equipment layer and ship **E1 Combinatorial Weapons v1**. Scaffold the Chronicle
meta-layer (first unlocks). *Gate G1: a run is a real roguelike run; weapon combinatorics
+ unlocks already pull 30–50 h.*

**Year 2 — The Build Game.** Ship **E2 Crafting** (full loot loop), **E3 Ability Trees &
Combos**, and **E6 enemy affixes**. Ship **E8 early-access** distribution — get players in.
*Gate G2: builds are real and diverse; players are testing; early access is live.*

**Year 3 — The Universe.** Ship **E4** — the seeded procedural world and a large biome
pool — and **E6** procedural multi-solution encounters. Factions begin. *Gate G3: no two
worlds are alike.*

**Year 4 — The Endless.** Ship **E5 Endless Ascension** — the 1,000-hour engine —
branching endings (the myth earns more than one outcome), and mastery/collection.
*Gate G4: the ladder + meta-progression sustain 500 h+.*

**Year 5 — The Living Universe.** Modding via the JSON pipeline (community content =
unbounded hours), localization, daily-seed challenges, the Definitive Edition.
*Gate G5: 1,000 h is reachable; community content extends it indefinitely.*

---

## Deep decisions

- **D1 — The roguelike pivot (spine + body).** Adopt it. Keep the authored Mournhold
  story as the campaign spine; build the combinatorial roguelike as the body. *Rationale:
  1,000 h is impossible to author and proven to generate — and the Chronicle already is
  a roguelike meta-layer.*
- **D2 — Run length.** Target **45–75 min** runs. The current ~2 h linear run is too long
  for a ~1,000-run loop; runs must be tighter, procedural, and self-contained.
- **D3 — Hermetic, stdlib-only engine.** **Keep it.** Every system here is data + logic,
  no graphics — no runtime dependency is needed, and zero-dependency is a real
  differentiator and de-risks distribution. The constraint scales fine to this scope.
- **D4 — Balance philosophy.** With combinatorics you cannot balance every combination.
  Target: **no dominant degenerate build, no dead builds, a wide viable middle.** E7
  enforces it statistically. Accept that build freedom implies some imbalance — that is
  the genre.
- **D5 — Authored vs. procedural ratio.** Named mini-bosses, the myth, and discovery
  fragments stay **hand-authored** to the current bar. Procedural content carries breadth
  — but procedural flavor must be **templated in the Mournhold voice**, never lorem-ipsum.
  Roughly 10–15 % authored spine, 85 % systems/procedural.
- **D6 — Distribution timing.** Early access in **Year 2** — not Year 1 (no player-ready
  build yet), not Year 5 (combinatorial systems need players to break them early).
- **D7 — Permadeath stays.** It is the roguelike core and the Chronicle depends on it.
  The run is the unit. A non-permadeath mode is explicitly *not* on this roadmap.

## Risks

- **Combinatorial balance is combinatorially hard** — E7 is infrastructure, not a
  nice-to-have. Underfunding it sinks the project.
- **Scope discipline** — the team's instinct will be to *author* content; the discipline
  is to build *generators*. Fixed release trains; cut scope, not dates.
- **Identity drift** — the grimdark soul must survive proceduralisation (see D5).
- **The terminal-niche ceiling** still caps the audience (per the studio dossier) — build
  for depth and a cult following, not mass market.
- **Solo / hobby bus factor** — the JSON schemas *are* the moat; document them obsessively.

## Data architecture (designer-facing summary)

New data files the systems will consume — designers extend the universe by editing JSON:
`components.json` · `materials.json` · `recipes.json` · `affixes.json` · `biomes.json` ·
`encounters.json` · `combos.json`; and `abilities.json` grows into class trees. The
existing principle holds: **content is data, systems are code.**

## Year 1 Backlog — The Combinatorial Foundation

Year 1 exists to **prove the combinatorial roguelike loop is fun** before scaling it.
~18 tickets across five workstreams. Definition of done for every ticket: it lands with
tests, and pytest + ruff + CI stay green.

### Workstream A — Balance & Simulation Infrastructure (ships first)

- **A1** — Promote the throwaway sim harness into a maintained `tools/sim` module: a
  headless combat driver with a pluggable policy. *Deps: none. Accept: `python3 -m
  tools.sim` runs and is reproducible by seed.*
- **A2** — Build-sampling: the simulator equips random weapons and reports win-rate
  distributions across builds. *Deps: D1, D3, C2. Accept: flags dead and degenerate builds.*
- **A3** — Balance regression gate in CI: committed win-rate baselines with a tolerance
  check. *Deps: A2. Accept: CI fails when tuning moves a band out of band.*

### Workstream B — The Run (the roguelike loop)

- **B1** — Formalise a `Run`: seeded, begins at character creation, ends at death or
  victory. *Deps: none.*
- **B2** — Make the RNG seed explicit: `run()` accepts or generates a seed, surfaced to
  the player and stored. *Deps: B1.*
- **B3** — The Chronicle becomes the run ledger — entries carry the seed. *Deps: B2.*
- **B4** — End-of-run summary screen: zones cleared, build, seed. *Deps: B3, Workstream D.*

### Workstream C — The Equipment Layer (prerequisite for weapons)

- **C1** — Structured inventory: separate consumables from equipment (today `inventory`
  is a flat potion list). *Deps: none. Accept: potions still work.*
- **C2** — A weapon slot on `Player`, with save round-trip. *Deps: C1, X1.*
- **C3** — Class starting weapons: route combat damage through the equipped weapon and
  retire the implicit flat `attack`. *Deps: C2, D1. Accept: v1 balance unchanged.*

### Workstream D — Combinatorial Weapons v1

- **D1** — `Weapon` model + `components.json`: four slots (Head, Haft, Core, Inscription);
  a weapon is four components plus rolled affixes. *Deps: C2.*
- **D2** — Proc hooks in combat (on-hit, on-crit, every-Nth-turn, on-kill); weapon Cores
  fire the existing status effects. *Deps: D1. Accept: a "bleed on crit" Core is unit-tested.*
- **D3** — Component pool v1: ~12 options per slot (~48), authored in the Mournhold voice.
  *Deps: D1, D2.*
- **D4** — Weapon drops and drop tables. *Deps: D1.*
- **D5** — Equip / inspect menu: compare stats, read component flavor. *Deps: C2, D1.*

### Workstream E — Chronicle Meta-Layer (first slice)

- **E1m** — A persistent unlock store in the Chronicle, corruption-resilient. *Deps: none.*
- **E2m** — First unlock hooks — e.g. a first mini-boss kill unlocks a component into the
  drop pool. *Deps: E1m, D3, D4.*
- **E3m** — A meta-progression screen on the title menu. *Deps: E1m.*

### Cross-cutting

- **X1** — Save schema v3 (equipment + run seed), with migration from v2. Gates C2.
- **X2** — Definition of done: every ticket lands with tests; pytest, ruff and CI green.

### Quarter sequencing

| Quarter | Tickets |
|---------|---------|
| Q1 | A1, B1, B2, B3, C1, X1 |
| Q2 | C2, D1, D2, C3 |
| Q3 | D3, D4, D5, A2 |
| Q4 | E1m, E2m, E3m, A3, B4 |

**Gate G1** — a seeded run with weapon combinatorics and the first unlocks is genuinely
fun and pulls 30–50 hours. **If the loop is not fun at G1, do not start Year 2 — fix the
loop.** Front-loading that judgement is the entire purpose of Year 1.

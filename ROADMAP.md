# Terminal Quest — 5-Year Strategic Roadmap

*Prepared by the executive team (CEO, CTO, Chief Game Officer, Chief Revenue Officer, COO).*
*Status as of 2026-05-18.*

## Executive Summary

Terminal Quest is a ~340-line single-file Python prototype today. The vision is to
evolve it into a **deep, fully offline, hermetic terminal RPG** that installs locally
with zero dependencies, plays without internet, and accepts **optional, signed remote
updates** when the host machine is online.

A note on ambition: "the most compelling RPG ever made" is the north star, but the
honest, achievable goal is **the most compelling _terminal_ RPG** — winning on depth,
emergence, and authored narrative rather than graphics. This is a niche market.
Plan to the **base case (~$80k revenue over 5 years)**, treat it as a lean,
founder-funded passion project, and **never staff ahead of revenue**.

## Strategic Pillars

1. **Hermetic & offline-first** — the game always runs fully offline; the network is
   never required to install or play.
2. **Optional online updates** — a separate, opt-in, cryptographically signed update
   channel delivers patches and paid expansions when internet is available.
3. **Content is the moat** — a data-driven content pipeline lets designers and writers
   add content without engineering, enabling sustained quarterly releases.
4. **Monetize loyalty, not lockdown** — DRM-free, low-priced, expansion-driven. We
   out-friendly piracy rather than fighting it.

## Cross-Cutting Decisions

- **Packaging:** PyInstaller — bundles a CPython runtime so users need no Python install.
- **Architecture:** refactor the single script into an installable package with a central
  event loop, a `GameState` object, and content as JSON/TOML data files.
- **Save system:** schema-versioned JSON in an OS-appropriate user data dir, atomic writes,
  forward-migration. Never pickle.
- **Update integrity:** Ed25519-signed manifests + SHA-256 checks; staged atomic apply with
  auto-rollback; private signing key kept offline.
- **Licensing:** signed offline entitlement tokens — a casual-sharing deterrent, not a wall.
  Lean on store entitlement (Steam/itch) where available.
- **Engineering baseline (Y1, critical path):** pytest, ruff, mypy, GitHub Actions CI matrix
  across Windows/macOS/Linux. None exist today — this is a prerequisite, not optional.
- **Combat bug fix:** the enemy currently retaliates only after the player's "Attack"
  action; using a potion grants a free turn. Fix during the Y1 combat rework — establish a
  clean turn-economy where every player action consumes a turn.

## Year-by-Year Roadmap

### Year 1 — Foundation & MVP
- **Tech:** package refactor, data-driven content loader, save system, config, pytest + CI,
  PyInstaller builds. Fix the combat turn-economy.
- **Game:** combat depth (abilities, stamina, status effects, enemy AI archetypes),
  4–6 classes, convert all hardcoded content to data files. Permadeath as default mode.
- **Ops:** team of 4 (2 engineers, 1 designer/writer, founder-COO). Gates: G1 playable MVP,
  G2 internal alpha with the offline→online→offline update flow proven.
- **Revenue:** prepare a polished v1.0 and a free demo.

### Year 2 — World, Story & Launch
- **Tech:** harden the signed update channel + rollback; offline licensing/entitlement.
- **Game:** authored main narrative arc, 8–12 regions, quest system, factions, first win
  condition.
- **Ops:** grow to ~7 (add engineer, QA lead, community/support). Public Beta channel.
  Gates: G3 v1.0 launch, G4 first paid expansion.
- **Revenue:** **launch v1.0 on itch.io at $7.99** + free demo; open GitHub Sponsors.
  **Steam launch with a wishlist campaign** — this is where real revenue lives.

### Year 3 — Depth & Expansions
- **Tech:** content-expansion engine, modding-friendly data format, opt-in telemetry.
- **Game:** crafting, item identification, skill trees, procedural dungeons, New Game+ via a
  meta-progression "Chronicle".
- **Ops:** grow to ~10; localization for 2 languages; modding API alpha.
- **Revenue:** **Expansion 1** ($3.99–4.99); raise base game to $9.99.

### Year 4 — Emergence & Endings
- **Tech:** platform polish; possible TUI overhaul; DLC content-pack delivery.
- **Game:** advanced enemy AI, 3–4 branching endings, faction warfare, multiclassing,
  daily-seed challenge runs.
- **Ops:** grow to ~13; sustained quarterly cadence; mod marketplace beta.
- **Revenue:** **Expansion 2** + quality-of-life update via the remote-update channel.

### Year 5 — Community Content & Platform
- **Tech:** engine reuse; stable self-serve content tooling.
- **Game:** mod support via the data pipeline, community content packs, expansion arc,
  offline-verifiable leaderboards.
- **Ops:** grow to ~15; major "Definitive Edition" relaunch (G9).
- **Revenue:** "Complete Edition" bundle, seasonal sales; evaluate a second product.

## Revenue Outlook (scenario modelling — not promises)

Net of store fees, lean 1–2 person effective team.

| Year | Conservative | Base | Optimistic |
|------|--------------|------|------------|
| 1    | $2k          | $6k  | $15k       |
| 2    | $8k          | $25k | $70k       |
| 3    | $6k          | $20k | $55k       |
| 4    | $5k          | $15k | $45k       |
| 5    | $4k          | $14k | $40k       |
| **Total** | **~$25k** | **~$80k** | **~$225k** |

Plan against the base case. It funds a passion project and modestly one developer — not
a payroll. Expansions are the revenue engine; a slipped expansion flattens Years 3–5.

## Top Risks

- **Niche market** caps upside even with flawless execution — do not over-invest.
- **Update channel is the long pole** — it gates monetization and all post-launch fixes;
  a signing-key compromise is catastrophic. Harden before the Y2 launch.
- **Save corruption across versions** — versioned schema, migration tests, pre-migration backups.
- **No bug visibility from offline users** — ship an opt-in "export bug report" tool and
  deferred (consent-based) telemetry that uploads on the next online launch.
- **Piracy is structural** in a hermetic offline product — mitigate with pricing and
  goodwill, never DRM that breaks the offline mandate.
- **Scope creep & solo-team bus factor** — fixed quarterly release trains (cut content,
  not dates); documentation gate per milestone; contractors as surge buffer.

## Immediate Next Step

The Year 1 critical path starts with the engineering baseline (package refactor, tests,
CI) and the data-driven content pipeline. Recommend kicking off with the combat
turn-economy fix and the content-pipeline refactor, since all later content velocity
depends on them.

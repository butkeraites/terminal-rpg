# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Mournhold (formerly Terminal Quest) is a grimdark terminal RPG written in pure Python 3
(>= 3.9). It is deliberately
hermetic: **no runtime dependencies** beyond the standard library, and no build step. The
game lives in the `terminalquest/` package; `rpg.py` at the repo root is a thin
compatibility shim kept so the historically documented `python3 rpg.py` still works.

## Running

```bash
python3 rpg.py            # compatibility shim
python3 -m terminalquest  # equivalent — runs terminalquest/__main__.py
```

Both call `terminalquest.game.main()`. Installing the package (`pip install -e .`) also
exposes a `mournhold` console script. The game is interactive and reads from stdin
via `input()`.

## Testing & linting

```bash
pip install -e ".[dev]"   # installs the only dev dependencies: pytest + ruff
python3 -m pytest         # runs the tests/ suite
ruff check .              # lint (line length 100)
```

CI (`.github/workflows/ci.yml`) runs ruff and pytest on every push to `main` and every
pull request, across Linux/macOS/Windows and Python 3.9 / 3.12.

## Architecture

The game is a set of nested input loops — there is no central event loop. `location_loop`
is the main loop: it renders the player's current location from the location graph and
dispatches to services, encounters and travel. All run-state is carried in a single
`GameState` object (`player`, `content`, `io`, `rng`, `current_location`, `flags`) passed
explicitly rather than held in module globals — this is what makes the whole game testable
headlessly.

### Package modules (`terminalquest/`)

- **`game.py`** — title screen, character creation (`choose_class`, `create_character`),
  save loading, and `run()` / `main()`, the entry point. `run()` builds the `GameState`.
- **`state.py`** — `GameState`, the central run-state object: the player, loaded content,
  the IO channel, the RNG, the current location, and a `flags` dict. It is the unit of
  save/load.
- **`locations.py`** — the location graph and `location_loop` (the main loop): renders a
  location's services / encounters / travel routes. Holds `shop`, `run_encounter` (the
  typed-encounter dispatcher), `try_travel` (gating + signpost warnings) and
  `_victory_screen`.
- **`combat.py`** — `run_combat`, a turn-based loop returning an outcome string
  (`'victory'`, `'defeat'`, `'fled'`, `'enemy_fled'`). Every player action consumes a
  turn. Damage and enemy-AI helpers are pure functions of their arguments plus an
  injected `random.Random`.
- **`combatant.py`** — `Combatant`, the base class for `Player` and `Enemy`: HP, defense,
  status effects, the shared `take_damage()` formula.
- **`player.py`** — `Player(Combatant)`: stats, progression (`gain_xp`, `level_up`), and
  `to_dict`/`from_dict` for saving.
- **`enemy.py`** — `Enemy(Combatant)` and `make_enemy()`, built from content data; an
  enemy's `ai` value selects its combat behaviour.
- **`status.py`** — status effects shared by all combatants: damage-over-time (`poison`,
  `burn`, `bleed`) and modifiers (`stun`, `weak`, `vulnerable`, `braced`, `evasive`).
- **`content.py`** — `load_content()` reads and validates the JSON data files into an
  immutable `Content` bundle (`classes`, `abilities`, `enemies`, `locations`).
- **`ui.py`** — the IO abstraction (see below) and `show_stats`.
- **`saves.py`** — versioned JSON save/load to `~/.terminalquest/saves`, written
  atomically, across three slots.

### Data-driven content (`terminalquest/data/`)

Classes, abilities, enemies, and the location graph are **defined in JSON**, not Python:
`classes.json`, `abilities.json`, `enemies.json`, `locations.json`. The world is a graph
of locations, each with `connections` to other locations and (for zones) a list of typed
`encounters`. `content.py` loads the files and `Content.validate()` checks internal
consistency (connections and encounters resolve, every location is reachable from the
crossroads, enemy `ai` values are valid, classes reference real abilities). **To add or
tune game content, edit the JSON — no Python changes needed.** Numeric tuning constants
(XP curve, crit chance, shop prices) are module-level constants in `player.py`,
`combat.py`, and `locations.py`.

### IO abstraction (testability)

`ui.py` defines `GameIO` — talks to a real terminal (`show`, `show_slow`, `ask`, `pause`,
`clear`) — and `ScriptedIO`, a test double that replays a canned list of inputs and
captures all output. IO and the RNG are injected — carried on the `GameState`, or passed
explicitly to combat's internal helpers — so the entire game loop can run headless under
pytest. See `tests/conftest.py` (`StubRandom`, the `make_state` helper, fixtures) and the
existing test files for the pattern.

## Conventions

- Menus are numbered options matched against string input (e.g. `choice == "1"`); invalid
  input prints an error and re-loops.
- Output uses emoji prefixes throughout for visual flavor — keep this style when adding
  messages.
- `GameIO.show_slow()` animates text character-by-character; `GameIO.clear()` prints
  blank lines.
- New locations follow the existing pattern: a function taking `player` and `io` with its
  own menu loop.
- New content (a class, enemy, zone, or ability) goes in the JSON data files; keep
  `Content.validate()` passing and add coverage in `tests/`.
- Keep the game hermetic — no runtime dependencies. `pytest` and `ruff` are dev-only.

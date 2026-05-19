# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Terminal Quest is a single-file, text-based RPG written in pure Python 3 (`rpg.py`). It has no dependencies beyond the standard library (`random`, `time`, `sys`) and no build step.

## Running

```bash
python3 rpg.py
```

The game is interactive and reads from stdin via `input()`. There is no test suite, linter, or CI configured.

## Architecture

The game is a state machine driven by `player.position` and nested input loops. There is no central event loop — control flows by calling location functions that each contain their own `while` loop.

- **`Player` / `Enemy`** — data classes holding stats. Both share a `take_damage()` formula: `max(1, damage - defense)`. `Player` additionally owns progression logic (`gain_xp`, `level_up`, `heal`).
- **Location functions** (`village`, `shop`, `forest`, `cave`, `mountain`) — each renders a numbered menu, loops on `input()`, and mutates the `player` object in place. They are entered from `world_map`, which is the central hub.
- **`world_map(player)`** — the main loop. Runs while `player.hp > 0`, dispatches to locations, and prints the game-over screen when HP drops to zero.
- **`combat(player, enemy)`** — turn-based loop returning `True` (enemy defeated / fled is `False`). Used by `forest`, `cave`, `mountain`. Note: enemy retaliation only happens on the player's "Attack" action, not after using a potion.
- **`main()`** — sets up the `Player` and enters `world_map`.

Progression constants are inline: leveling multiplies `xp_to_level` by 1.5 and adds fixed stat gains; enemy rosters are hardcoded lists inside each location function.

## Conventions

- Menus are numbered options matched against string input (e.g. `choice == "1"`); invalid input prints an error and re-loops.
- `print_slow()` animates text character-by-character; `clear_screen()` just prints blank lines.
- Output uses emoji prefixes throughout for visual flavor — keep this style when adding messages.
- New locations should follow the existing pattern: a function taking `player`, its own menu loop, and setting `player.position = "world"` on exit.

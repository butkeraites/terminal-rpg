# Mournhold

A hermetic, terminal-based grimdark roguelike RPG.

A kingdom is dying because it tried to forget. The Pall came down off the
heights and the land went grey behind it. You are no hero; the heroes died
first. The last road that leads anywhere climbs into the Pall.

The **Chronicle of the Fallen** remembers your dead. Their bones rise as
the Hollowed in the zones where they fell; the hero who breaks the Warden
is kept by the Pall, and faces themselves at the Summit on the next run.

Built in pure Python 3 — no graphics, no runtime dependencies, just text,
ANSI colour, and the writing earning its keep.

## Play

```bash
python3 rpg.py            # the historical entry point
python3 -m terminalquest  # equivalent
```

Python 3.9+ is the only requirement.

## Develop

```bash
pip install -e ".[dev]"           # pytest + ruff
python3 -m pytest                 # run the test suite
ruff check .                      # lint
python3 -m tools.sim              # the balance simulator
python3 -m tools.sim --check      # the CI balance regression gate
```

## Project

- [ROADMAP.md](ROADMAP.md) — the five-year build plan (the "Thousand-Hour Universe").
- [CLAUDE.md](CLAUDE.md) — architecture, conventions, where things live.

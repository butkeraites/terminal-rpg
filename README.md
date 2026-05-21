# Mournhold

A hermetic, terminal-based grimdark roguelike RPG.

A kingdom is dying because it tried to forget. The Pall came down off the
heights and the land went grey behind it. You are no hero; the heroes died
first. The last road that leads anywhere climbs into the Pall.

The **Chronicle of the Fallen** remembers your dead. Their bones rise as
the Hollowed in the zones where they fell; the hero who breaks the Warden
is kept by the Pall, and faces themselves at the Summit on the next run.

The kingdom also **marks** you — 1000 irreversible per-character moments
that fire as you walk, fight, save, and grow. A mark is something that
happens to *this* character (only this character) and cannot be undone:
the smith's thumbprint on your weapon's grip, a grief Atrél held for one
count, a face the Pall took from your memory. Some marks change your
stats. All of them are recorded on the character sheet and persist
through save/load via per-run sidecar files; saving and reloading does
not undo a mark that fired. The next character starts un-marked.

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

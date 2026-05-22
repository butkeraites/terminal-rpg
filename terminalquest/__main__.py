"""Entry point for ``python -m terminalquest``."""

from __future__ import annotations
import argparse

from .game import main


def _parse_args():
    p = argparse.ArgumentParser(prog="terminalquest")
    p.add_argument("--no-audio", action="store_true",
                   help="disable ambient audio for this session (overrides settings)")
    p.add_argument("--tui", action="store_true",
                   help="EXPERIMENTAL: render with curses panels")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(no_audio=args.no_audio, tui=args.tui)

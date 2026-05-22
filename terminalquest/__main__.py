"""Entry point for ``python -m terminalquest``."""
import argparse

from .game import main


def _parse_args():
    p = argparse.ArgumentParser(prog="terminalquest")
    p.add_argument("--no-audio", action="store_true",
                   help="disable ambient audio for this session (overrides settings)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(no_audio=args.no_audio)

#!/usr/bin/env python3
"""Compatibility shim: the game now lives in the ``terminalquest`` package.

Kept so the historically documented ``python3 rpg.py`` still works.
"""
from terminalquest.game import main

if __name__ == "__main__":
    main()

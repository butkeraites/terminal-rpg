"""Optional ANSI colour, applied only when writing to a real terminal.

When stdout is not a TTY — under pytest, or when piped — every helper
returns its input unchanged, so captured output stays plain text.
"""

from __future__ import annotations
import sys

ENABLED = sys.stdout.isatty()

_CODES = {
    "red": "31",
    "green": "32",
    "yellow": "33",
    "cyan": "36",
    "dim": "2",
    "bold": "1",
}


def paint(text, style):
    """Wrap ``text`` in an ANSI style, or return it plain when colour is off."""
    if not ENABLED or style not in _CODES:
        return text
    return f"\033[{_CODES[style]}m{text}\033[0m"

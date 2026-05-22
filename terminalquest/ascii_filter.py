"""Emoji → ASCII bracket-tag fallback for terminals without glyph support.

Activated when ``GameIO.ascii_mode`` is True. Output goes through
``to_ascii(text)`` which replaces every known emoji with a short bracket
tag. The labels next to stat numbers (added in v0.6) carry most of the
meaning either way; this is the belt-and-braces option for terminals so
old they show '?' even with UTF-8 forced on.
"""
from __future__ import annotations


# Order matters: variant-selectors first, so "⚔️" matches before "⚔".
ASCII_FALLBACKS = (
    # Combat / stats
    ("⚔️", "[atk]"), ("⚔", "[atk]"),
    ("🛡️", "[def]"), ("🛡", "[def]"),
    ("❤️", "[hp]"),  ("❤", "[hp]"),
    ("⚡", "[sta]"),
    ("🎯", "[crit]"),
    ("💨", "[dodge]"),
    ("💥", "**"),
    ("💢", "!!"),
    ("✨", "*"),
    ("🌀", "~"),
    ("💚", "+"),
    ("💉", "+heal"),
    ("🩹", "+heal"),
    ("💀", "[dead]"),
    ("🥀", "[wilted]"),
    ("🌅", "[dawn]"),
    ("☠️", "[skull]"), ("☠", "[skull]"),
    # HUD
    ("💰", "[gold]"),
    ("🎒", "[pack]"),
    # Locations & terrain
    ("🛤️", "[road]"), ("🛤", "[road]"),
    ("🏚️", "[ruin]"), ("🏚", "[ruin]"),
    ("🌲", "[tree]"),
    ("🌊", "[water]"),
    ("🕳️", "[hole]"), ("🕳", "[hole]"),
    ("🏛️", "[city]"), ("🏛", "[city]"),
    ("⛪", "[church]"),
    ("⛰️", "[peak]"), ("⛰", "[peak]"),
    ("☁️", "[cloud]"), ("☁", "[cloud]"),
    ("🪵", "[wood]"),
    ("🪜", "[steps]"),
    ("🪨", "[stone]"),
    ("📿", "[prayer]"),
    ("🪦", "[grave]"),
    ("🌐", "[border]"),
    ("🗺️", "[map]"), ("🗺", "[map]"),
    # Services and NPCs
    ("🏪", "[shop]"),
    ("😴", "[inn]"),
    ("⚒", "[smith]"),
    ("🐺", "[pact]"),
    ("🕯️", "[lamp]"), ("🕯", "[lamp]"),
    ("🌑", "[night]"),
    ("📜", "[scroll]"),
    ("🐾", "[paw]"),
    ("🕊️", "[dove]"), ("🕊", "[dove]"),
    ("📚", "[books]"),
    ("🐦", "[bird]"),
    ("🦔", "[hog]"),
    ("🐈", "[cat]"),
    ("🍞", "[bread]"),
    ("🗝️", "[key]"), ("🗝", "[key]"),
    ("⚖️", "[scale]"), ("⚖", "[scale]"),
    # Menu / system
    ("🎓", "[skill]"),
    ("🔒", "[locked]"),
    ("✅", "[ok]"),
    ("❌", "[x]"),
    ("✓", "v"),
    ("📍", "[here]"),
    ("👑", "[crown]"),
    ("👋", "(wave)"),
    ("🎲", "[seed]"),
    ("🎉", "[!]"),
    ("📖", "[book]"),
    ("💫", "[stun]"),
    ("⚠️", "[!]"), ("⚠", "[!]"),
    ("💾", "[save]"),
    ("🗡️", "[sword]"), ("🗡", "[sword]"),
    ("🔧", "[tool]"),
    # Combat verbs
    ("🏃", "[flee]"),
    ("😡", "[rage]"),
    # SQ content (v0.15+ side quests)
    ("🪶", "[note]"),    # SQ4 Piranesi
    ("🎼", "[verse]"),   # SQ8 Lost Verse
    ("🌳", "[tree]"),    # SQ7 Forgotten Thing
)


def to_ascii(text):
    """Replace every known emoji in ``text`` with its ASCII bracket-tag form."""
    if not text:
        return text
    for emoji, ascii_form in ASCII_FALLBACKS:
        if emoji in text:
            text = text.replace(emoji, ascii_form)
    return text

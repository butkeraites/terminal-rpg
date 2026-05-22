"""Endings registry — pluggable run-completion screens.

The Summit victory screen used to be three branches hard-coded in
``locations._victory_screen``. Each new arc the brother asks for adds a
new ending. Hard-coding more branches stops scaling.

Instead, every ending registers a render function + a ``requires``
predicate. The dispatcher prints a shared lead-in, lists the endings whose
``requires`` is True (in registration order), and renders the one the
player picks.

Endings register themselves in ``locations.py`` at module load — they live
where their render functions live. ``endings.choose_and_render`` is what
``_victory_screen`` calls.
"""
from __future__ import annotations


# Each entry: (id, menu_label, render_fn, requires_predicate)
_ENDINGS = []


def register(ending_id, label, render, requires):
    """Register a new ending. Called at module load from locations.py."""
    _ENDINGS.append((ending_id, label, render, requires))


def available(state):
    """Endings whose ``requires`` predicate is True for this state."""
    return [e for e in _ENDINGS if e[3](state)]


def choose_and_render(state, lead_in):
    """Print the lead-in, list available endings, render the chosen one.

    ``lead_in`` is a list of strings shown before the menu — the canonical
    Shadow Warden falls preamble. The renderer chosen drives the rest of
    the screen (and records the appropriate Chronicle fate).
    """
    io = state.io
    io.clear()
    for line in lead_in:
        io.show_slow(line)
    io.pause(1)
    endings = available(state)
    while True:
        for index, (_eid, label, _render, _req) in enumerate(endings, start=1):
            io.show(f"{index}. {label}")
        choice = io.ask("\nYour choice? ")
        if choice.isdigit() and 1 <= int(choice) <= len(endings):
            endings[int(choice) - 1][2](state)
            return
        io.show("\n❌ Invalid choice!")


def reset_registry():
    """For tests: clear the registry between assertions."""
    _ENDINGS.clear()

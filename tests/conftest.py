"""Shared pytest fixtures and a deterministic RNG stub."""
import tempfile

import pytest

from terminalquest.content import load_content
from terminalquest.player import Player
from terminalquest.state import GameState
from terminalquest.ui import ScriptedIO


class StubRandom:
    """Deterministic stand-in for ``random.Random`` used by combat tests.

    ``rnd`` is returned by ``random()``, ``ri`` by ``randint()``. With the
    defaults, probability rolls fail and attack variance is zero, making
    combat fully predictable.
    """

    def __init__(self, rnd=0.9, ri=0, choice_index=0):
        self._rnd = rnd
        self._ri = ri
        self._choice_index = choice_index

    def random(self):
        return self._rnd

    def randint(self, a, b):
        return self._ri

    def choice(self, seq):
        return list(seq)[self._choice_index]


@pytest.fixture
def content():
    return load_content()


@pytest.fixture
def warrior(content):
    return Player("Hero", "warrior", content.classes["warrior"], content)


def make_state(player, content, io=None, rng=None,
               current_location="crossroads", chronicle_dir=None):
    """Build a GameState for tests, defaulting io/rng to test doubles.

    ``chronicle_dir`` defaults to a fresh temp dir so tests never touch
    or depend on the real ~/.terminalquest chronicle.
    """
    return GameState(
        player, content,
        io if io is not None else ScriptedIO(),
        rng if rng is not None else StubRandom(),
        current_location=current_location,
        chronicle_dir=chronicle_dir or tempfile.mkdtemp(),
    )

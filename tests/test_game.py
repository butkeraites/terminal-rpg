"""Title-screen flows."""
import random

from terminalquest import chronicle, game
from terminalquest.ui import ScriptedIO


def test_chronicle_screen_renders(tmp_path, content):
    """E3m: the Chronicle screen reports the fallen and the salvage they unlocked."""
    chronicle.unlock("pallid_stag", tmp_path)  # gates the Bleeding-Edge Core
    io = ScriptedIO()
    game.chronicle_screen(io, content, tmp_path)
    text = io.text()
    assert "Chronicle" in text
    assert "Bleeding-Edge Core" in text


def test_title_screen_shows_after_images_for_reached_endings(tmp_path, content):
    """v1.8 — Mournhold's title screen shows an after-image per reached ending."""
    chronicle.add_ending_seen("purify", tmp_path)
    chronicle.add_ending_seen("caretaker", tmp_path)
    # Pick Quit from the title menu so run() returns.
    io = ScriptedIO(["5"])
    game.run(io=io, content=content, rng=random.Random(0),
             chronicle_dir=tmp_path, seed=42)
    text = io.text()
    assert "Mournhold remembers" in text
    # The two reached endings appear as their after-images.
    assert "child in what was Brackmere" in text
    assert "Climbers come back to a warm cup" in text
    # Endings not yet reached are absent.
    assert "Mournhold is unmade" not in text  # reckoning's image


def test_title_screen_omits_after_section_with_no_endings_reached(
        tmp_path, content):
    """v1.8 — the After section is silent for a player who has reached none yet."""
    io = ScriptedIO(["5"])
    game.run(io=io, content=content, rng=random.Random(0),
             chronicle_dir=tmp_path, seed=42)
    text = io.text()
    assert "Mournhold remembers" not in text

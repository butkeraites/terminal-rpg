"""Title-screen flows."""
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

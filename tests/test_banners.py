"""Banner module — keyed by location id, plus title/death/new_run."""
from terminalquest import banners
from terminalquest.ui import ScriptedIO


SPECIAL_KEYS = {"title", "death", "new_run"}


def test_every_location_has_a_banner(content):
    """Adding a new location without a banner shouldn't be silent — assert
    coverage so banner authoring stays in lockstep with the world."""
    missing = [loc_id for loc_id in content.locations
               if loc_id not in banners.BANNERS]
    assert missing == [], f"locations without banners: {missing}"


def test_special_keys_present():
    assert SPECIAL_KEYS.issubset(banners.BANNERS.keys())


def test_print_banner_is_silent_for_unknown_key():
    io = ScriptedIO()
    banners.print_banner(io, "no_such_banner_qjxz")
    assert io.text() == ""


def test_print_banner_outputs_banner_text():
    io = ScriptedIO()
    banners.print_banner(io, "title")
    text = io.text()
    assert "MOURNHOLD" in text or "M    O    U    R    N    H    O    L    D" in text
    assert "the kingdom that ended" in text


def test_print_banner_prepends_and_appends_blank_lines():
    """Spacing matters — the banner shouldn't slam into surrounding text."""
    io = ScriptedIO()
    banners.print_banner(io, "death")
    lines = io.output
    assert lines[0] == ""
    assert lines[-1] == ""


def test_ascii_mode_substitutes_box_drawing():
    """Unicode box chars become readable ASCII so old terminals don't show tofu."""
    io = ScriptedIO(ascii_mode=True)
    banners.print_banner(io, "title")
    text = io.text()
    # the title uses ▒; should be replaced by # in ascii mode
    assert "▒" not in text
    assert "#" in text


def test_no_ascii_substitution_when_unicode_ok():
    io = ScriptedIO(ascii_mode=False)
    banners.print_banner(io, "title")
    text = io.text()
    assert "▒" in text


def test_zone_banner_names_the_zone():
    """A spot check that each zone's banner mentions the zone."""
    # Pick a handful with distinctive words
    cases = [
        ("crossroads", "CROSSROADS"),
        ("village",    "GRAVEWATCH"),
        ("forest",     "WITHERWOOD"),
        ("mourncross", "MOURNCROSS"),
        ("bone_tomb",  "BONE"),
    ]
    for key, needle in cases:
        io = ScriptedIO()
        banners.print_banner(io, key)
        # banners use spaced letters: M O U R N C R O S S
        assert any(needle in line.replace(" ", "") for line in io.output), \
            f"{key} banner missing {needle}"

"""map_panel — pure renderer, easy to test without curses."""
from terminalquest import map_panel


def test_render_returns_lines():
    lines = map_panel.render()
    assert isinstance(lines, list)
    assert all(isinstance(line, str) for line in lines)
    assert len(lines) > 10


def test_render_includes_kingdom_landmarks():
    text = "\n".join(map_panel.render())
    for needle in ("Summit", "Mourncross", "Crossroads", "Gravewatch",
                   "Witherwood", "Bone Tomb", "Border"):
        assert needle in text, f"map missing {needle}"


def test_current_location_marked_with_arrow():
    text = "\n".join(map_panel.render(current_loc_id="mourncross"))
    assert "►Mourncross" in text


def test_ghost_marker_at_fall_location():
    text = "\n".join(map_panel.render(ghost_locs=["bone_tomb"]))
    assert "Bone Tomb†" in text


def test_current_and_ghost_can_coincide():
    """Standing at a place where someone fell: both markers should show."""
    text = "\n".join(map_panel.render(
        current_loc_id="mourncross", ghost_locs=["mourncross"]))
    assert "►Mourncross†" in text


def test_unknown_location_does_not_break():
    """A current location that isn't in LABELS just renders no arrow."""
    lines = map_panel.render(current_loc_id="atlantis")
    text = "\n".join(lines)
    assert "►" not in text
    assert "Mournhold" in text  # title line still present


def test_ascii_mode_substitutes_unicode():
    text = "\n".join(map_panel.render(
        current_loc_id="mourncross",
        ghost_locs=["bone_tomb"],
        ascii_mode=True))
    assert "►" not in text
    assert "│" not in text
    assert "─" not in text
    assert "†" not in text
    # ASCII fallbacks landed
    assert ">Mourncross" in text
    assert "Bone Tomb+" in text


def test_every_zone_has_a_label(content):
    """A new location in content/ should be added to LABELS too — otherwise
    the player visits a place that doesn't appear on their own map."""
    missing = [loc_id for loc_id in content.locations
               if loc_id not in map_panel.LABELS]
    assert missing == [], f"locations missing from map_panel.LABELS: {missing}"


# ── CursesIO set_location integration ───────────────────────────────────


def test_set_location_updates_internal_state():
    from terminalquest.curses_io import CursesIO
    io = CursesIO()
    io.set_location("mourncross", ["bone_tomb"])
    assert io._current_loc == "mourncross"
    assert io._ghost_locs == ["bone_tomb"]


def test_set_location_default_on_game_io():
    """GameIO.set_location is a no-op so callers can blindly call it."""
    from terminalquest.ui import GameIO
    io = GameIO()
    # Must not raise.
    io.set_location("mourncross", ["bone_tomb"])

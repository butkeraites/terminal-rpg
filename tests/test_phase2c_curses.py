"""Phase 2c: curses_io.py — drive every branch through a mocked curses."""
import time
from unittest.mock import MagicMock, patch


from terminalquest import curses_io
from terminalquest.curses_io import CursesIO


# ── Fake curses primitives ─────────────────────────────────────────────


class _FakeWin:
    """Stand-in for a curses window — records calls, no real rendering."""

    def __init__(self, h=20, w=100):
        self._size = (h, w)
        self.calls = []

    def getmaxyx(self):
        return self._size

    def erase(self):
        self.calls.append(("erase",))

    def addnstr(self, *args, **kwargs):
        self.calls.append(("addnstr", args, kwargs))

    def addstr(self, *args, **kwargs):
        self.calls.append(("addstr", args, kwargs))

    def scrollok(self, flag):
        self.calls.append(("scrollok", flag))

    def idlok(self, flag):
        self.calls.append(("idlok", flag))

    def noutrefresh(self):
        self.calls.append(("noutrefresh",))

    def refresh(self):
        self.calls.append(("refresh",))

    def getstr(self, y, x, n):
        self.calls.append(("getstr", y, x, n))
        return b"answer"


class _FakeStdscr(_FakeWin):
    """stdscr behaves like a regular window plus a couple extras."""

    def keypad(self, flag):
        self.calls.append(("keypad", flag))


def _mock_curses(monkeypatch, stdscr=None, wide=True):
    """Patch curses module functions for the duration of a test.

    Returns a (mock_curses_module, stdscr) tuple. ``wide`` controls the
    terminal size — affects whether the map panel is built.
    """
    import curses
    monkeypatch.setattr(curses, "curs_set", lambda *_a: None)
    monkeypatch.setattr(curses, "echo", lambda: None)
    monkeypatch.setattr(curses, "noecho", lambda: None)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(curses, "resize_term", lambda *_a: None)

    new_windows = []

    def fake_newwin(h, w, y, x):
        win = _FakeWin(h=h, w=w)
        new_windows.append(win)
        return win

    monkeypatch.setattr(curses, "newwin", fake_newwin)

    if stdscr is None:
        stdscr = _FakeStdscr(h=30, w=120 if wide else 60)
    return curses, stdscr, new_windows


# ── start + _build_windows ─────────────────────────────────────────────


class TestStartAndLayout:
    def test_start_builds_windows_wide(self, monkeypatch):
        _curses, stdscr, wins = _mock_curses(monkeypatch, wide=True)
        io = CursesIO()
        io.start(stdscr)
        # status_win + map_win + log_win + input_win = 4 windows
        assert len(wins) == 4
        assert io.map_win is not None
        assert io.log_win is not None
        assert io._last_size == (30, 120)

    def test_start_builds_windows_narrow_skips_map(self, monkeypatch):
        _curses, stdscr, wins = _mock_curses(monkeypatch, wide=False)
        io = CursesIO()
        io.start(stdscr)
        # status_win + log_win + input_win = 3 windows; no map
        assert len(wins) == 3
        assert io.map_win is None
        assert io.log_win is not None

    def test_start_handles_curs_set_exception(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)

        import curses
        monkeypatch.setattr(curses, "curs_set",
                            MagicMock(side_effect=Exception("nope")))
        io = CursesIO()
        io.start(stdscr)  # must not raise

    def test_start_handles_keypad_exception(self, monkeypatch):
        _curses, _stdscr, _wins = _mock_curses(monkeypatch)
        stdscr = _FakeStdscr(h=30, w=120)
        stdscr.keypad = MagicMock(side_effect=Exception("nope"))
        io = CursesIO()
        io.start(stdscr)  # must not raise


# ── _check_resize ──────────────────────────────────────────────────────


class TestCheckResize:
    def test_no_op_before_start(self):
        io = CursesIO()
        io._check_resize()  # no stdscr → no-op

    def test_same_size_no_rebuild(self, monkeypatch):
        _curses, stdscr, wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        before = len(wins)
        io._check_resize()
        assert len(wins) == before  # no new windows

    def test_size_change_rebuilds_windows(self, monkeypatch):
        _curses, stdscr, wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        before = len(wins)
        # Simulate a resize by changing stdscr size
        stdscr._size = (40, 100)
        io._check_resize()
        assert len(wins) > before
        assert io._last_size == (40, 100)

    def test_resize_term_exception_does_not_block_rebuild(self, monkeypatch):
        _curses, stdscr, wins = _mock_curses(monkeypatch)
        import curses
        monkeypatch.setattr(curses, "resize_term",
                            MagicMock(side_effect=Exception("nope")))
        io = CursesIO()
        io.start(stdscr)
        before = len(wins)
        stdscr._size = (40, 100)
        io._check_resize()
        assert len(wins) > before  # still rebuilt


# ── set_status / _draw_status ──────────────────────────────────────────


class TestStatusDrawing:
    def test_draw_status_noop_before_start(self):
        io = CursesIO()
        io._draw_status()  # no-op

    def test_set_status_writes_to_status_win(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        io.set_status("Hero · Lv7 · Mourncross")
        # addnstr was called on the status window
        addnstr_calls = [c for c in io.status_win.calls
                         if c[0] == "addnstr"]
        assert any("Mourncross" in str(c) for c in addnstr_calls)

    def test_set_status_default_text_when_empty(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        io.set_status("")
        # Default text "MOURNHOLD" should appear
        addnstr_calls = [c for c in io.status_win.calls
                         if c[0] == "addnstr"]
        assert any("MOURNHOLD" in str(c) for c in addnstr_calls)


# ── set_location / _draw_map ──────────────────────────────────────────


class TestMapDrawing:
    def test_draw_map_noop_when_no_map_win(self):
        io = CursesIO()  # never started
        io.set_location("village", ["bone_tomb"])
        # No exception, internal state updated
        assert io._current_loc == "village"
        assert io._ghost_locs == ["bone_tomb"]

    def test_draw_map_writes_to_map_win(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch, wide=True)
        io = CursesIO()
        io.start(stdscr)
        io.set_location("mourncross", ["bone_tomb"])
        addnstr_calls = [c for c in io.map_win.calls
                         if c[0] == "addnstr"]
        assert len(addnstr_calls) > 0
        # current location marker should appear in the output
        all_text = "\n".join(str(c) for c in addnstr_calls)
        assert "Mourncross" in all_text or "►" in all_text

    def test_draw_map_skips_lines_beyond_window_height(self, monkeypatch):
        """Force a narrow window; map renderer produces many lines."""
        _curses, _stdscr, _wins = _mock_curses(monkeypatch, wide=True)
        # Replace the stdscr with one that's tall enough to have a map_win
        # but force the map_win to be tiny by patching _build_windows
        stdscr = _FakeStdscr(h=5, w=120)  # very short
        io = CursesIO()
        io.start(stdscr)
        # map_win will have h ~= 2 → render bails fast
        io.set_location("mourncross")
        # No exception is the point


# ── show / show_slow / show_through_stone / clear ──────────────────────


class TestOutputMethods:
    def test_show_before_start_uses_print(self, capsys):
        CursesIO().show("hi")
        assert "hi" in capsys.readouterr().out

    def test_show_after_start_writes_to_log_win(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        io.show("multi\nline")
        addstr_calls = [c for c in io.log_win.calls if c[0] == "addstr"]
        # Two lines written
        assert len(addstr_calls) >= 2

    def test_show_handles_addstr_exception(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        io.log_win.addstr = MagicMock(side_effect=Exception("too wide"))
        io.show("text")  # must not raise

    def test_show_slow_with_animate_sleeps(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO(animate=True)
        io.start(stdscr)
        with patch.object(time, "sleep") as sleep:
            io.show_slow("hello", delay=0.001)
        sleep.assert_called_once()

    def test_show_slow_no_animate_no_sleep(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO(animate=False)
        io.start(stdscr)
        with patch.object(time, "sleep") as sleep:
            io.show_slow("hello")
        sleep.assert_not_called()

    def test_show_through_stone_prefixes(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        io.show_through_stone("speaking")
        all_text = "".join(str(c) for c in io.log_win.calls)
        assert "▒" in all_text or "::" in all_text

    def test_show_through_stone_ascii_mode(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO(ascii_mode=True)
        io.start(stdscr)
        io.show_through_stone("plain")
        all_text = "".join(str(c) for c in io.log_win.calls)
        assert "::" in all_text

    def test_clear_before_start_noop(self):
        CursesIO().clear()  # no-op

    def test_clear_erases_log_win(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        prior_calls = list(io.log_win.calls)
        io.clear()
        assert ("erase",) in io.log_win.calls[len(prior_calls):]

    def test_clear_handles_erase_exception(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        io.log_win.erase = MagicMock(side_effect=Exception("nope"))
        io.clear()  # must not raise


# ── ask ────────────────────────────────────────────────────────────────


class TestAsk:
    def test_ask_before_start_uses_input(self):
        io = CursesIO()
        with patch("builtins.input", return_value=" yes "):
            assert io.ask("Q? ") == "yes"

    def test_ask_after_start_reads_from_input_win(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        assert io.ask("Q? ") == "answer"

    def test_ask_getstr_exception_returns_empty(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        io.input_win.getstr = MagicMock(side_effect=Exception("nope"))
        assert io.ask("Q? ") == ""

    def test_ask_echoes_into_log(self, monkeypatch):
        _curses, stdscr, _wins = _mock_curses(monkeypatch)
        io = CursesIO()
        io.start(stdscr)
        io.ask("Q? ")
        # The "> answer" echo line should appear in the log
        all_text = "".join(str(c) for c in io.log_win.calls)
        assert "answer" in all_text


# ── pause ──────────────────────────────────────────────────────────────


def test_pause_calls_sleep():
    with patch.object(time, "sleep") as sleep:
        CursesIO().pause(0.3)
    sleep.assert_called_once_with(0.3)


# ── run_with_tui ──────────────────────────────────────────────────────


def test_run_with_tui_delegates_to_curses_wrapper():
    import curses
    with patch.object(curses, "wrapper") as wrapper, \
         patch.object(curses_io, "CursesIO"):
        curses_io.run_with_tui(no_audio=True)
    wrapper.assert_called_once()

"""CursesIO — only the no-curses graceful-degradation path is testable
headlessly. Full curses behaviour requires a TTY and is left to manual
smoke testing under ``--tui``."""
from terminalquest.curses_io import CursesIO
from terminalquest.ui import GameIO


def test_curses_io_constructs_without_curses_init():
    """Constructing the class must not touch curses — that only happens in
    start(). This is what makes the import safe in test runs."""
    io = CursesIO()
    assert io.log_win is None
    assert io.status_win is None
    assert io.input_win is None


def test_is_a_game_io():
    """The class must remain substitutable for GameIO so every existing
    call site that expects GameIO keeps working under --tui."""
    io = CursesIO()
    assert isinstance(io, GameIO)


def test_show_without_start_falls_through_to_print(capsys):
    """Before start() is called, show() degrades to print so the class is
    safe to construct and use in test environments."""
    io = CursesIO()
    io.show("hearth")
    captured = capsys.readouterr()
    assert "hearth" in captured.out


def test_clear_without_start_is_noop():
    """clear() must not crash before start() — used by show_stats etc."""
    io = CursesIO()
    io.clear()


def test_set_status_without_start_is_noop():
    io = CursesIO()
    io.set_status("Lv 7  ❤ 42/52")

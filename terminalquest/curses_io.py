"""Curses TUI — EXPERIMENTAL scaffold opt-in via the ``--tui`` flag.

What this v2 establishes:

  * a 1-line status bar at the top of the screen
  * a map panel on the left (if terminal width >= 90 cols) showing the
    kingdom graph with current location ► and ghost markers † at zones
    where past characters fell
  * a scrolling hearth log on the right (or full width if no map)
  * a 2-line input area at the bottom

What this v2 still does NOT do — follow-up PRs:

  * dedicated character / marks panel beside the log
  * char-by-char ``show_slow`` animation (curses + per-char refresh is slow;
    v2 prints the full line at once)
  * resize handling (a SIGWINCH redraw would re-layout the windows)
  * colour pairs (curses.start_color)

The default game (``python -m terminalquest`` with no flags) is unchanged.
``ScriptedIO`` is unaffected — only ``--tui`` constructs ``CursesIO``.
"""
import time

from . import map_panel
from .ui import GameIO


MAP_WIDTH = 52    # columns reserved for the left map panel when shown
MIN_WIDTH_FOR_MAP = 90  # narrower terminals get the log full-width


class CursesIO(GameIO):
    """``GameIO`` backed by a curses screen with three windows.

    Construct, then call ``start(stdscr)`` inside ``curses.wrapper`` to lay
    out the windows. Before ``start`` is called the IO degrades gracefully
    to plain ``print``/``input`` so the class is safe to construct in tests.
    """

    def __init__(self, animate=True, ascii_mode=False):
        super().__init__(animate=animate, ascii_mode=ascii_mode)
        self.stdscr = None
        self.status_win = None
        self.map_win = None
        self.log_win = None
        self.input_win = None
        # The caller (game loop) updates this through set_status to put HP /
        # stamina / location into the top bar. Empty default just shows
        # the kingdom name so the bar isn't blank.
        self.status_text = ""
        # Current map state — updated by set_location, redrawn from here.
        self._current_loc = None
        self._ghost_locs = []
        # Terminal size at last layout. Compared on every op to detect resize;
        # on mismatch, windows are rebuilt and status/map redraw from state.
        self._last_size = None

    def start(self, stdscr):
        """Bind to a curses ``stdscr`` and build the three windows."""
        import curses
        self.stdscr = stdscr
        try:
            curses.curs_set(0)
        except Exception:
            pass
        try:
            stdscr.keypad(True)
        except Exception:
            pass
        self._build_windows()

    # ── layout ─────────────────────────────────────────────────────────

    def _build_windows(self):
        import curses
        h, w = self.stdscr.getmaxyx()
        self.status_win = curses.newwin(1, w, 0, 0)
        middle_h = max(1, h - 3)
        if w >= MIN_WIDTH_FOR_MAP:
            self.map_win = curses.newwin(middle_h, MAP_WIDTH, 1, 0)
            log_x = MAP_WIDTH
            log_w = w - MAP_WIDTH
        else:
            self.map_win = None
            log_x = 0
            log_w = w
        self.log_win = curses.newwin(middle_h, log_w, 1, log_x)
        self.log_win.scrollok(True)
        self.log_win.idlok(True)
        self.input_win = curses.newwin(2, w, h - 2, 0)
        self._last_size = (h, w)
        self._draw_status()
        self._draw_map()

    def _check_resize(self):
        """If the terminal was resized, rebuild windows and redraw what we
        can. Log content scrolled-off is lost (rebuilt empty); status and
        map redraw from internal state."""
        if self.stdscr is None or self._last_size is None:
            return
        try:
            import curses
            h, w = self.stdscr.getmaxyx()
            if (h, w) == self._last_size:
                return
            try:
                curses.resize_term(h, w)
            except Exception:
                pass
            self._build_windows()
        except Exception:
            pass

    def _draw_status(self):
        if self.status_win is None:
            return
        try:
            import curses
            self.status_win.erase()
            text = self._filter(self.status_text or "MOURNHOLD")
            _, w = self.status_win.getmaxyx()
            self.status_win.addnstr(0, 0, text, w - 1)
            self.status_win.noutrefresh()
            curses.doupdate()
        except Exception:
            pass

    def set_status(self, text):
        """Set the top-bar text (HP / stamina / current zone)."""
        self.status_text = text
        self._check_resize()
        self._draw_status()

    def _draw_map(self):
        if self.map_win is None:
            return
        try:
            import curses
            self.map_win.erase()
            h, w = self.map_win.getmaxyx()
            lines = map_panel.render(
                self._current_loc, self._ghost_locs, ascii_mode=self.ascii_mode)
            for i, line in enumerate(lines):
                if i >= h - 1:
                    break
                try:
                    self.map_win.addnstr(i, 0, line, w - 1)
                except Exception:
                    pass
            self.map_win.noutrefresh()
            curses.doupdate()
        except Exception:
            pass

    def set_location(self, loc_id, ghost_locs=None):
        """Update the map panel — call on every zone arrival."""
        self._current_loc = loc_id
        if ghost_locs is not None:
            self._ghost_locs = list(ghost_locs)
        self._check_resize()
        self._draw_map()

    # ── GameIO contract ────────────────────────────────────────────────

    def show(self, text=""):
        if self.log_win is None:
            print(self._filter(text))
            return
        self._check_resize()
        try:
            import curses
            for line in self._filter(str(text)).split("\n"):
                try:
                    self.log_win.addstr(line + "\n")
                except Exception:
                    # text wider than the window — best-effort, drop the
                    # overflow rather than crash
                    pass
            self.log_win.noutrefresh()
            curses.doupdate()
        except Exception:
            pass

    def show_slow(self, text, delay=0.02):
        """Per-line cadence — full line lands at once, then a brief pause
        proportional to length. Per-char refresh in curses costs ~100x what
        print does; lumping the delay after the line keeps the slow-text
        feel without the redraw bill. Capped so long monologues don't drag.
        """
        self.show(text)
        if self.animate and text:
            time.sleep(min(delay * len(str(text)), 0.6))

    def show_through_stone(self, text):
        prefix = "::  " if self.ascii_mode else "▒  "
        self.show(prefix + str(text))

    def ask(self, prompt):
        if self.input_win is None:
            return input(self._filter(prompt)).strip()
        self._check_resize()
        try:
            import curses
            self.input_win.erase()
            self.input_win.addstr(0, 0, self._filter(prompt))
            self.input_win.refresh()
            curses.echo()
            try:
                curses.curs_set(1)
            except Exception:
                pass
            try:
                raw = self.input_win.getstr(1, 0, 256)
            finally:
                curses.noecho()
                try:
                    curses.curs_set(0)
                except Exception:
                    pass
            text = raw.decode("utf-8", errors="replace").strip()
        except Exception:
            text = ""
        # Echo into the log so the conversation history survives.
        self.show(f"> {text}")
        return text

    def pause(self, seconds=1.0):
        time.sleep(seconds)

    def clear(self):
        if self.log_win is None:
            return
        try:
            import curses
            self.log_win.erase()
            self.log_win.noutrefresh()
            curses.doupdate()
        except Exception:
            pass


def run_with_tui(no_audio=False):
    """Curses-wrapped entry point. Called only when ``--tui`` is passed."""
    import curses

    from .game import run

    def _inside(stdscr):
        io = CursesIO()
        io.start(stdscr)
        run(io=io, no_audio=no_audio)

    curses.wrapper(_inside)

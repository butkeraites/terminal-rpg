"""Terminal input/output, abstracted so the game can be driven by tests.

``GameIO`` talks to a real terminal. ``ScriptedIO`` feeds canned input and
captures output, letting the whole game loop run headless under pytest.

``ascii_mode`` swaps every known emoji for an ASCII bracket-tag at output
time — set by the first-launch smoke test for users whose terminals can't
render emoji glyphs at all.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING, Iterable

from . import ascii_filter, color, status

if TYPE_CHECKING:
    from .content import Content
    from .player import Player


class GameIO:
    """Real-terminal input/output."""

    animate: bool
    ascii_mode: bool

    def __init__(self, animate: bool = True, ascii_mode: bool = False) -> None:
        self.animate = animate
        self.ascii_mode = ascii_mode

    def _filter(self, text: str) -> str:
        """Strip emoji glyphs to ASCII bracket-tags when ascii_mode is on."""
        if not self.ascii_mode:
            return text
        return ascii_filter.to_ascii(text)

    def show(self, text: str = "") -> None:
        print(self._filter(text))

    def show_slow(self, text: str, delay: float = 0.02) -> None:
        """Print text character-by-character for dramatic effect."""
        text = self._filter(text)
        if not self.animate:
            print(text)
            return
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(delay)
        print()

    def ask(self, prompt: str) -> str:
        return input(self._filter(prompt)).strip()

    def pause(self, seconds: float = 1.0) -> None:
        time.sleep(seconds)

    def clear(self) -> None:
        print("\n" * 2)

    def set_location(
        self,
        loc_id: str,
        ghost_locs: Iterable[str] | None = None,
    ) -> None:
        """Hook for TUIs to redraw a map panel. Default is no-op.

        The line-based GameIO has no map to update; CursesIO (and any
        future TUI) overrides this to refresh its side panel.
        """
        pass

    def set_status(self, text: str) -> None:
        """Hook for TUIs to update a status bar. Default is no-op.

        The line-based GameIO prints the hud inline every iteration, so it
        has no separate bar to update.
        """
        pass

    def show_through_stone(self, text: str) -> None:
        """Render a line as if spoken through ossified stone — Cael's voice.

        v0.12 Arc V mechanic: Cael's mouth is full of stone. Her words come
        through anyway. Each line is prefixed with ▒ and rendered slowly,
        with a fractional pause between characters — the stone modulates.
        """
        text = self._filter(text)
        prefix = "::  " if self.ascii_mode else "▒  "
        if not self.animate:
            print(prefix + text)
            return
        sys.stdout.write(prefix)
        sys.stdout.flush()
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(0.04)  # slower than normal show_slow
        print()


class ScriptedIO(GameIO):
    """Test double: replays a list of inputs and records all output."""

    inputs: list[str]
    output: list[str]

    def __init__(
        self,
        inputs: Iterable[str] | None = None,
        ascii_mode: bool = False,
    ) -> None:
        super().__init__(animate=False, ascii_mode=ascii_mode)
        self.inputs = list(inputs or [])
        self.output = []

    def show(self, text: str = "") -> None:
        self.output.append(self._filter(str(text)))

    def show_slow(self, text: str, delay: float = 0.02) -> None:
        self.output.append(self._filter(str(text)))

    def show_through_stone(self, text: str) -> None:
        prefix = "::  " if self.ascii_mode else "▒  "
        self.output.append(prefix + self._filter(str(text)))

    def ask(self, prompt: str) -> str:
        if not self.inputs:
            raise AssertionError("ScriptedIO ran out of inputs")
        return self.inputs.pop(0)

    def pause(self, seconds: float = 1.0) -> None:
        pass

    def clear(self) -> None:
        pass

    def text(self) -> str:
        """All captured output joined into a single string."""
        return "\n".join(self.output)


def hud(player: Player) -> str:
    """A compact one-line status bar shown across the game's screens."""
    hp = f"{player.hp}/{player.max_hp}"
    if player.hp <= player.max_hp * 0.3:
        hp = color.paint(hp, "red")
    elif player.hp >= player.max_hp * 0.7:
        hp = color.paint(hp, "green")
    return (f"Lv{player.level}  ❤️ {hp}  ⚡ {player.stamina}/{player.max_stamina}"
            f"  💰 {player.gold}  🎒 {player.potion_count()}")


def show_stats(
    io: GameIO,
    player: Player,
    content: Content | None = None,
) -> None:
    """Render the player's full stat sheet.

    v1.51 — if a content bundle is provided AND the player carries any marks,
    a Marks section is rendered after the standard stats. Each fired mark's
    first line is shown — a small list of the irreversible things the
    kingdom has done to this character this run.
    """
    io.show("\n" + "=" * 50)
    io.show(f"⚔️  {player.name} the {player.class_name} | Level {player.level}")
    io.show(f"❤️  HP: {player.hp}/{player.max_hp}")
    io.show(f"⚡ Stamina: {player.stamina}/{player.max_stamina}")
    io.show(f"⚔️  Attack: {player.attack} | 🛡️  Defense: {player.defense}")
    io.show(f"✨ XP: {player.xp}/{player.xp_to_level} | 💰 Gold: {player.gold}")
    io.show(f"🎒 Potions: {player.potion_count()}")
    effects = status.describe(player)
    if effects:
        io.show(f"Status: {effects}")
    # v1.51 — Marks section: the kingdom's irreversible record of this
    # character. Only shown when content is available and the player has
    # accumulated at least one mark. The list is short by intent — one
    # line per mark, the mark's own first line.
    marks_list = getattr(player, "marks", None)
    if marks_list and content is not None:
        pool = getattr(content, "marks", None)
        if pool:
            from . import marks as _marks
            lines = _marks.describe(player, pool)
            if lines:
                io.show("")
                io.show(f"⊕ Marked by {len(marks_list)} small things:")
                for line in lines:
                    io.show(line)
    io.show("=" * 50 + "\n")

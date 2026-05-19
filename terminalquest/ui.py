"""Terminal input/output, abstracted so the game can be driven by tests.

``GameIO`` talks to a real terminal. ``ScriptedIO`` feeds canned input and
captures output, letting the whole game loop run headless under pytest.
"""
import sys
import time

from . import status


class GameIO:
    """Real-terminal input/output."""

    def __init__(self, animate=True):
        self.animate = animate

    def show(self, text=""):
        print(text)

    def show_slow(self, text, delay=0.03):
        """Print text character-by-character for dramatic effect."""
        if not self.animate:
            print(text)
            return
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(delay)
        print()

    def ask(self, prompt):
        return input(prompt).strip()

    def pause(self, seconds=1.0):
        time.sleep(seconds)

    def clear(self):
        print("\n" * 2)


class ScriptedIO(GameIO):
    """Test double: replays a list of inputs and records all output."""

    def __init__(self, inputs=None):
        super().__init__(animate=False)
        self.inputs = list(inputs or [])
        self.output = []

    def show(self, text=""):
        self.output.append(str(text))

    def show_slow(self, text, delay=0.03):
        self.output.append(str(text))

    def ask(self, prompt):
        if not self.inputs:
            raise AssertionError("ScriptedIO ran out of inputs")
        return self.inputs.pop(0)

    def pause(self, seconds=1.0):
        pass

    def clear(self):
        pass

    def text(self):
        """All captured output joined into a single string."""
        return "\n".join(self.output)


def show_stats(io, player):
    """Render the player's full stat sheet."""
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
    io.show("=" * 50 + "\n")

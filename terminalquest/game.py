"""Game bootstrap: title screen, character creation, and the entry point."""
import random

from . import __version__, saves
from .content import load_content
from .locations import location_loop
from .player import Player
from .state import GameState
from .ui import GameIO


def choose_class(content, io):
    """Prompt the player to pick a class. Returns ``(class_id, class_def)``."""
    class_ids = list(content.classes)
    while True:
        io.show("\nChoose your class:\n")
        for index, class_id in enumerate(class_ids, start=1):
            cls = content.classes[class_id]
            io.show(f"{index}. {cls['name']} — {cls['description']}")
            io.show(f"   HP {cls['max_hp']} | Attack {cls['attack']} | "
                    f"Defense {cls['defense']} | Stamina {cls['max_stamina']}")
        choice = io.ask("\nYour choice? ")
        if choice.isdigit() and 1 <= int(choice) <= len(class_ids):
            class_id = class_ids[int(choice) - 1]
            return class_id, content.classes[class_id]
        io.show("\n❌ Invalid choice!")


def create_character(content, io):
    """Run new-game character creation and return a fresh Player."""
    name = io.ask("\nEnter your hero's name: ") or "Hero"
    class_id, class_def = choose_class(content, io)
    player = Player(name, class_id, class_def)
    io.clear()
    io.show_slow(f"Welcome, {player.name} the {player.class_name}!")
    io.show_slow("Your adventure begins...\n")
    io.pause(2)
    return player


def load_menu(content, io, rng):
    """Show occupied save slots and return a loaded GameState, or None to cancel."""
    saved = saves.list_saves()
    if not saved:
        io.show("\n❌ No saved games found.")
        io.pause(1)
        return None
    io.show("\nSaved games:")
    for slot, summary in saved.items():
        io.show(f"{slot}. {summary}")
    io.show("4. Cancel")
    choice = io.ask("\nLoad which slot? ")
    if choice in ("1", "2", "3") and int(choice) in saved:
        return saves.load_game(int(choice), content, io, rng)
    return None


def run(io=None, content=None, rng=None):
    """Run the game from the title screen. Arguments are injectable for tests."""
    io = io or GameIO()
    content = content or load_content()
    rng = rng or random.Random()

    io.clear()
    io.show_slow("=" * 50)
    io.show_slow("⚔️  TERMINAL QUEST ⚔️", delay=0.05)
    io.show_slow("=" * 50)
    io.show(f"v{__version__}\n")

    while True:
        io.show("1. New Game")
        io.show("2. Continue")
        io.show("3. Quit")
        choice = io.ask("\nYour choice? ")

        if choice == "1":
            player = create_character(content, io)
            location_loop(GameState(player, content, io, rng))
            return
        elif choice == "2":
            state = load_menu(content, io, rng)
            if state is not None:
                location_loop(state)
                return
        elif choice == "3":
            io.show("\n👋 Farewell, adventurer!")
            return
        else:
            io.show("\n❌ Invalid choice!")


def main():
    run()


if __name__ == "__main__":
    main()

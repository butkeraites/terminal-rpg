"""Game bootstrap: title screen, character creation, and the entry point."""
import random

from . import __version__, chronicle, saves
from .content import load_content
from .locations import location_loop
from .player import Player
from .state import GameState
from .ui import GameIO


def _new_seed():
    """A short, shareable seed for a fresh run."""
    return str(random.Random().randint(100000, 999999))


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


def _name_the_fallen(io, content, entries):
    """Tell the new hero of the characters who walked the road before."""
    if not entries:
        return
    io.show_slow("\nOthers walked this road before you. Mournhold keeps their names:")
    for entry in entries[-6:]:
        p = entry["player"]
        loc = content.locations.get(entry.get("location", ""), {})
        place = loc.get("name", "the dark")
        if entry.get("fate") == "warden":
            io.show(f"  👑 {p['name']} the {p['class_name']} — took the Summit, "
                    f"and the Pall took them. They keep it still.")
        elif entry.get("resolved"):
            io.show(f"  🕯️  {p['name']} the {p['class_name']} — fell in {place}, "
                    f"and was laid to rest.")
        else:
            io.show(f"  🪦 {p['name']} the {p['class_name']} — fell at level "
                    f"{p['level']} in {place}.")
    io.show_slow("It will keep yours the same way.\n")


def create_character(content, io, chronicle_dir):
    """Run new-game character creation and return a fresh Player."""
    name = io.ask("\nEnter your hero's name: ") or "Hero"
    class_id, class_def = choose_class(content, io)
    player = Player(name, class_id, class_def, content)
    io.clear()
    io.show_slow(f"{player.name} the {player.class_name}.")
    io.show_slow("The realm of Mournhold has been dying for three winters now.")
    io.show_slow("The Pall came down off the heights and the land went grey behind it —")
    io.show_slow("crops, then cattle, then people, all turned hollow and hungry.")
    io.show_slow("You are no hero; the heroes died first. You are only still breathing —")
    io.show_slow("and the last road that leads anywhere climbs toward the Pall's heart.\n")
    _name_the_fallen(io, content, chronicle.load(chronicle_dir))
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
        try:
            return saves.load_game(int(choice), content, io, rng)
        except saves.SaveError:
            io.show("\n❌ That save is corrupt and cannot be loaded.")
            io.pause(1)
    return None


def settings_menu(io):
    """Toggle display settings from the title screen."""
    while True:
        state = "ON" if io.animate else "OFF"
        io.show(f"\n1. Text animation: {state}")
        io.show("2. Back")
        choice = io.ask("\nYour choice? ")
        if choice == "1":
            io.animate = not io.animate
        elif choice == "2":
            return
        else:
            io.show("\n❌ Invalid choice!")


def chronicle_screen(io, content, chronicle_dir):
    """Show the cross-run Chronicle: who fell, who was kept, what they unlocked."""
    entries = chronicle.load(chronicle_dir)
    held = chronicle.unlocked(chronicle_dir)
    io.clear()
    io.show("📖 The Chronicle of the Fallen\n")
    io.show(f"   {len(entries)} have walked the road into Mournhold.")
    io.show(f"   {len(chronicle.fallen(entries))} lie unquiet still; "
            f"{len(chronicle.wardens(entries))} broke the Pall and were kept by it.")
    earned = [comp["name"]
              for slot in content.components.values()
              for comp in slot.values()
              if comp.get("unlock") in held]
    if earned:
        io.show("\n   Salvage their deeds have unlocked:")
        for name in earned:
            io.show(f"     ⚒  {name}")
    else:
        io.show("\n   Their deeds have unlocked no salvage yet.")
    io.pause(2)


def run(io=None, content=None, rng=None, chronicle_dir=None, seed=None):
    """Run the game from the title screen. Arguments are injectable for tests."""
    io = io or GameIO()
    content = content or load_content()
    if seed is None:
        seed = _new_seed()
    rng = rng or random.Random(seed)
    chronicle_dir = chronicle_dir or chronicle.DEFAULT_DIR

    io.clear()
    io.show_slow("=" * 50)
    io.show_slow("⚔️  TERMINAL QUEST ⚔️", delay=0.05)
    io.show_slow("=" * 50)
    io.show(f"v{__version__}\n")

    while True:
        io.show("1. New Game")
        io.show("2. Continue")
        io.show("3. The Chronicle")
        io.show("4. Settings")
        io.show("5. Quit")
        choice = io.ask("\nYour choice? ")

        if choice == "1":
            player = create_character(content, io, chronicle_dir)
            io.show(f"\n🎲 This run is seeded: {seed}")
            location_loop(GameState(player, content, io, rng,
                                    chronicle_dir=chronicle_dir, seed=seed))
            return
        elif choice == "2":
            state = load_menu(content, io, rng)
            if state is not None:
                if state.seed:
                    io.show(f"\n🎲 This run is seeded: {state.seed}")
                location_loop(state)
                return
        elif choice == "3":
            chronicle_screen(io, content, chronicle_dir)
        elif choice == "4":
            settings_menu(io)
        elif choice == "5":
            io.show("\n👋 Farewell, adventurer!")
            return
        else:
            io.show("\n❌ Invalid choice!")


def main():
    run()


if __name__ == "__main__":
    main()

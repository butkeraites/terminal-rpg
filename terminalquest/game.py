"""Game bootstrap: title screen, character creation, and the entry point."""
import os
import random
import sys

from . import __version__, chronicle, saves, settings
from .content import load_content
from .locations import location_loop
from .player import Player
from .state import GameState
from .ui import GameIO


def _emoji_smoke_test(io, prefs):
    """First-launch test: can the user's terminal render an emoji glyph?

    If they answer no, ascii_mode is set and persisted so every future
    launch on this machine renders the game in bracket-text. Either way
    the test only runs once — the flag emoji_test_done locks it.
    """
    if prefs["emoji_test_done"]:
        return
    print()
    print("=" * 50)
    print("Quick check before we start:")
    print()
    print("This is the sword character:  ⚔️")
    print()
    print("If you see a sword (or a small icon), say YES.")
    print("If you see a blank square, '?', or anything other than a sword,")
    print("say NO and the game will switch to text-only mode.")
    try:
        answer = input("\nDid you see a sword clearly? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "y"
    if answer in ("n", "no", "nao", "não"):
        prefs["ascii_mode"] = True
        io.ascii_mode = True
        print("\nSwitched to text-only mode. Emojis will render as [bracket-tags].")
        print("You can re-run the test by deleting ~/.terminalquest/settings.json.")
    else:
        print("\nGreat. Continuing with the full glyphs.")
    prefs["emoji_test_done"] = True
    settings.save(prefs)
    print("=" * 50)


def _configure_console_for_unicode():
    """Make the terminal render the game's emoji glyphs.

    Windows cmd.exe defaults to a legacy code page (cp1252/cp437) that cannot
    encode emoji bytes — the encoder substitutes them with '?'. We force UTF-8
    on stdout/stderr, and on Windows also switch the console code page to 65001
    (UTF-8). Font support is a separate concern: if the terminal font lacks an
    emoji glyph, the user will see a tofu box rather than a '?' — readable and
    obviously a font issue, not garbled output.
    """
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    if sys.platform == "win32":
        try:
            os.system("chcp 65001 > nul")
        except OSError:
            pass


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


MIRROR_CLIMB_THRESHOLD = 3  # SQ5: distinct endings needed to unlock the Mirror Climb


# v1.8 — One after-image per ending the player has reached, shown quietly on
# the title screen. Mournhold remembers its own aftermaths between runs.
_AFTER_IMAGES = {
    "warden":
        ("Someone climbed. Someone won. The Pall kept that climber too.",
         "The Witherwood still has its wolves. The road still climbs."),
    "reborn":
        ("Someone climbed. Someone refused. The Echo Trader has new things",
         "on her counter. They were made by hands that did not finish climbing."),
    "purify":
        ("The kingdom is named again. A child in what was Brackmere",
         "learned to write her name this winter. She learned it from a Karst woman."),
    "atrel_peace":
        ("In the Choir's south aisle, a small altar holds a fresh flower every month.",
         "Whoever leaves it does not know why. It is the right size for them."),
    "old_seal":
        ("Under the mountain, someone sits in stone. They are saying names.",
         "Mournhold lives, and does not know it lives because of them."),
    "reckoning":
        ("Mournhold is unmade. The Hidden Hold is the only hold left.",
         "They bake for travellers, who are sometimes strangers, who they let in."),
    "caretaker":
        ("Someone in Gravewatch keeps the small things now.",
         "Climbers come back to a warm cup, set out before they ask."),
    "other_mournhold":
        ("Somewhere, in a kingdom that never grew a Pall, the gates open every morning.",
         "A child carries water without knowing what they have been spared."),
}


def create_character(content, io, chronicle_dir):
    """Run new-game character creation and return (player, starting_flags).

    SQ5 — if the Chronicle has at least ``MIRROR_CLIMB_THRESHOLD`` distinct
    endings reached, the player is offered a Mirror Climb: the same world,
    but the climb is the climb of someone who has done it as several others
    already and remembers them all.
    """
    name = io.ask("\nEnter your hero's name: ") or "Hero"
    class_id, class_def = choose_class(content, io)
    player = Player(name, class_id, class_def, content)
    flags = {}
    # v1.63 — mark a run that follows previous successful characters so marks
    # tied to "what the kingdom kept for you from before" can fire only for
    # players who actually have a previous-character history.
    if chronicle.cleanses(chronicle_dir) > 0:
        flags["is_reborn"] = True
    if len(chronicle.endings_seen(chronicle_dir)) >= MIRROR_CLIMB_THRESHOLD:
        io.show("\n🪞 You have climbed Mournhold as several others. There is")
        io.show("   a path back through your own steps. The Mirror Climb opens")
        io.show("   the Summit's hardest ending — and only that one — to whoever")
        io.show("   has paid for it as someone else.")
        answer = io.ask("\nClimb the Mirror? [y/N] ").strip().lower()
        if answer == "y":
            flags["mirror_run"] = True
    io.clear()
    first = chronicle.first_line(chronicle_dir)
    if first:
        # SQ10 — every new character begins by reading the line a past player
        # wrote into the Chronicle's first page at the Crossroads.
        io.show_slow(f"📖 {first}")
        io.show("")
        io.pause(1)
    if flags.get("mirror_run"):
        io.show_slow(f"🪞 {player.name} the {player.class_name}. Again.")
        io.show_slow("You have stood at the road's start before, under another name.")
        io.show_slow("Mournhold does not know you are back. You know.")
        io.show_slow("The Witherwood looks like itself. You look at it like an old")
        io.show_slow("friend's face that does not, yet, recognise you.\n")
    else:
        io.show_slow(f"{player.name} the {player.class_name}.")
        io.show_slow("The realm of Mournhold has been dying for three winters now.")
        io.show_slow("The Pall came down off the heights and the land went grey behind it —")
        io.show_slow("crops, then cattle, then people, all turned hollow and hungry.")
        io.show_slow("You are no hero; the heroes died first. You are only still breathing —")
        io.show_slow("and the last road that leads anywhere climbs toward the Pall's heart.\n")
    _name_the_fallen(io, content, chronicle.load(chronicle_dir))
    io.pause(2)
    return player, flags


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
    cleanses = chronicle.cleanses(chronicle_dir)
    echoes = chronicle.echoes(chronicle_dir)
    io.clear()
    io.show("📖 The Chronicle of the Fallen\n")
    io.show(f"   {len(entries)} have walked the road into Mournhold.")
    io.show(f"   {len(chronicle.fallen(entries))} lie unquiet still; "
            f"{len(chronicle.wardens(entries))} broke the Pall and were kept by it.")
    if cleanses:
        suffix = " — Mournhold lies PURIFIED." if chronicle.purified(chronicle_dir) else ""
        io.show(f"\n   Cleanses: {cleanses}{suffix}")
    if echoes:
        io.show(f"   Echoes: {echoes}")
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
    if io is None:
        prefs = settings.load()
        io = GameIO(ascii_mode=prefs["ascii_mode"])
        _emoji_smoke_test(io, prefs)
    content = content or load_content()
    if seed is None:
        seed = _new_seed()
    rng = rng or random.Random(seed)
    chronicle_dir = chronicle_dir or chronicle.DEFAULT_DIR

    io.clear()
    io.show_slow("=" * 50)
    io.show_slow("⚔️  MOURNHOLD ⚔️", delay=0.05)
    io.show_slow("=" * 50)
    io.show(f"v{__version__}\n")

    # v1.8 — show after-images for endings the player has reached. The
    # kingdom remembers between runs; the title screen is where it speaks.
    seen_endings = chronicle.endings_seen(chronicle_dir)
    after_lines = [
        lines for eid, lines in _AFTER_IMAGES.items() if eid in seen_endings
    ]
    if after_lines:
        io.show("Mournhold remembers:")
        for lines in after_lines:
            io.show("")
            for line in lines:
                io.show_slow(f"  {line}", delay=0.01)
        io.show("")

    while True:
        io.show("1. New Game")
        io.show("2. Continue")
        io.show("3. The Chronicle")
        io.show("4. Settings")
        io.show("5. Quit")
        choice = io.ask("\nYour choice? ")

        if choice == "1":
            player, starting_flags = create_character(content, io, chronicle_dir)
            io.show(f"\n🎲 This run is seeded: {seed}")
            location_loop(GameState(player, content, io, rng,
                                    chronicle_dir=chronicle_dir, seed=seed,
                                    flags=starting_flags))
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
    _configure_console_for_unicode()
    run()
    # On Windows, a PyInstaller --onefile binary closes its console window
    # the moment the Python process exits — so the final screen (victory,
    # Reborn, defeat summary) flashes by unread. Hold the window open until
    # the player presses Enter. macOS/Linux terminals don't have this problem.
    if sys.platform == "win32":
        try:
            input("\nPress Enter to close.")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    main()

"""Ending screens for Mournhold — the seven canonical endings + their helpers.

Each ``_*_screen(state)`` function:

  * Records the ending in the Chronicle (via ``chronicle.add_ending_seen``)
  * Increments the cleanse count (via ``chronicle.add_cleanse``)
  * Renders the ending's narrative through ``state.io``
  * Calls :func:`_run_summary` for the end-of-run recap

The seven endings register themselves with the ``endings`` module at
import time — importing this module IS the registration, so the
``endings`` registry is populated as soon as anything imports
``endings_screens`` (or ``locations``, which re-exports from here).

This file was extracted from ``locations.py`` during the v2.3 quality
audit. ``locations.py`` re-exports every name defined here for
backwards compatibility with code (and tests) that referenced
``locations._warden_screen`` and friends directly.
"""

from __future__ import annotations
from . import chronicle, endings, marks


# ── Tuning constants (Reborn echoes, Purify gate) ──────────────────────

REBORN_ECHO_BASE = 30           # baseline Echo for a Reborn
REBORN_ECHO_PER_LEVEL = 3
REBORN_ECHO_PER_UNLOCK = 5
PURIFY_CLEANSES_REQUIRED = 5    # cleanses needed before Purify unlocks


# ── End-of-run recap (shared with death flow in locations.py) ──────────


def _run_summary(state):
    """The end-of-run recap — the hero, the build they carried, and the seed."""
    player, io = state.player, state.io
    place = state.content.locations[state.current_location]["name"]
    weapon = player.equipment.get("weapon")
    io.show("\n" + "─" * 50)
    io.show(f"  {player.name} the {player.class_name}, level {player.level}")
    io.show(f"  Last stood in {place}, with {player.gold} gold.")
    if weapon is not None:
        io.show(f"  Wielding {weapon.name} — {weapon.summary()}")
    if state.seed:
        io.show(f"  This run was seeded: {state.seed}")
    io.show("─" * 50)


# ── Victory dispatcher ─────────────────────────────────────────────────


_VICTORY_LEAD_IN = [
    "The Shadow Warden comes apart like wet ash. The Pall, finding",
    "itself without a Warden, turns to the soul still standing on",
    "the Summit. It reaches.\n",
]


def _victory_screen(state):
    """Dispatch to the player's chosen ending via the endings registry."""
    endings.choose_and_render(state, _VICTORY_LEAD_IN)


# ── The seven ending screens ───────────────────────────────────────────


def _warden_screen(state):
    """The canonical ending: the Pall keeps the victor as the next Warden.

    If the player has read the Real Minutes (Arc I), the ending names the
    full council vote — they are the seventh to keep this place, fully
    informed of what they inherit.
    """
    player, io = state.player, state.io
    chronicle.record(state, "warden", state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("warden", state.chronicle_dir)
    # v1.51 — the character is done; their marks die with them.
    marks.clear_sidecar(state.chronicle_dir, state.player.run_id)
    io.clear()
    io.show("=" * 50)
    io.show("🥀  THE PALL KEEPS YOU")
    io.show(f"{player.name} the {player.class_name} — Warden of the Shrouded Summit")
    io.show("\nYou will not climb down. You will wait here, wearing your own")
    io.show("face, until the next soul reaches the Summit to break you —")
    io.show("as you broke the one before.")
    if state.flags.get("read_real_minutes"):
        io.show("")
        io.show("You know the names of the six who voted to seal the gates.")
        io.show("You know the names of the five who voted to open them, and were silenced.")
        io.show("You know which side the Chairman sat on, and what he did to the five.")
        io.show("You knew all of this and you let the Pall take you anyway.")
        io.show("You are the seventh to keep this place. You are the first to keep it knowing.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _sister_realm_addendum(state, io):
    """Print a closing paragraph naming the sister-realm alliance, if any.

    v0.14 adds these flavour-only addenda — they do not alter the Chronicle.
    They confirm to the player that what they did at the Border carried.
    """
    if state.flags.get("allied_karst"):
        io.show("")
        io.show("In Karst, the bread moves both ways across the border again,")
        io.show("slowly, with a long winter to teach the merchants not to forget.")
    if state.flags.get("allied_wynne"):
        io.show("")
        io.show("In Wynne, the Devoured Captain lies in a grave with her name on it.")
        io.show("The Chancellor's chancellery burns the year after. No one is surprised.")
    if state.flags.get("opposed_margrave"):
        io.show("")
        io.show("On the Margrave's side of the border, three small graves are dug,")
        io.show("and the monument's lie is sanded off the stone, one letter at a time.")


def _reborn_screen(state):
    """The Reborn ending — earn Echoes (Chronicle currency) and end this run."""
    player, io = state.player, state.io
    unlock_count = len(chronicle.unlocked(state.chronicle_dir))
    echoes_earned = (REBORN_ECHO_BASE
                     + player.level * REBORN_ECHO_PER_LEVEL
                     + unlock_count * REBORN_ECHO_PER_UNLOCK)
    chronicle.add_echoes(echoes_earned, state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("reborn", state.chronicle_dir)
    # The Reborn hero is NOT chronicled as a Warden — they refused the Pall.
    io.clear()
    io.show_slow("You turn the Pall's reach aside. The Summit empties of you,")
    io.show_slow("the road empties of you, the kingdom forgets you — almost.")
    io.show_slow("Only the Echoes follow you back. The dead remember coin.\n")
    io.show("=" * 50)
    io.show("💀  REBORN")
    io.show(f"{player.name} the {player.class_name} — refused.")
    io.show(f"\nEchoes earned this run: {echoes_earned}")
    io.show(f"Echoes total: {chronicle.echoes(state.chronicle_dir)}")
    owned = chronicle.owned_accessories(state.chronicle_dir)
    if owned:
        io.show(f"\nAccessories you carry across the dark: {len(owned)}")
    _sister_realm_addendum(state, io)
    io.show("=" * 50)
    io.show("\nStart a new run from the title screen — visit the Echo Trader")
    io.show("at Gravewatch to spend what you earned.")
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _reckoning_screen(state):
    """The 8th ending — help Tálva. Mournhold is unmade for what it did to the holds.

    Requires ``talva_asked`` flag — you promised Tálva at the Hidden Hold.
    Records the Chronicle as 'reckoning'. Not a clean ending. Not meant to be.
    """
    player, io = state.player, state.io
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("reckoning", state.chronicle_dir)
    io.clear()
    io.show_slow("You break the Warden. The Pall reaches.")
    io.show_slow("You do not let it take you. You do not bring the rite back to Atrél.")
    io.show_slow("You do not sit at Cael's feet. You walk down.")
    io.show_slow("You walk down past the Pre-Pall Shrine. You take a hammer to the iron tablet.")
    io.show_slow("The vow under the mountain breaks. The hunger comes up. It comes up steadily.\n")
    io.pause(1)
    io.show_slow("It eats Mournhold's name first. Then the names of every councilor who voted to seal.")
    io.show_slow("Then it turns on the rite of unremembering — eaten by what the rite was meant to forget.")
    io.show_slow("Last: the holds that died inside the gates. Their names are safe. The kingdom did not have them.")
    io.show_slow("Their names are at the Hidden Hold. Tálva has them. She kept them.\n")
    io.pause(1)
    io.show_slow("Mournhold is unwritten. The roads bend wrong again — but they bend toward the holds.")
    io.show_slow("You walk down to the Hidden Hold. Tálva nods at you. Kerris bakes you a loaf.")
    io.show_slow("Ondrek says nothing. The Small Un asks why your hands are shaking.")
    io.show_slow("You stay. You become the kingdom's last historian. You write what was, and what wasn't.\n")
    io.pause(2)
    io.show("=" * 50)
    io.show("⚖️  THE RECKONING")
    io.show(f"{player.name} the {player.class_name} — who broke the kingdom that broke the holds.")
    io.show("\nMournhold is unmade. The Pall is undone with it.")
    io.show("Future climbers will find a country that ate itself, and a Hidden Hold that did not.")
    io.show("Symmetry. The hardest thing the holds had left to ask for.")
    io.show("\nThe Chronicle records: reckoning. The Pall is gone. So is the kingdom that fed it.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _old_seal_screen(state):
    """The seventh ending — take Cael's place as the seal beneath the mountain.

    Requires ``offered_old_seal`` (player accepted Cael's offer). Records
    'old_seal_taken' in the Chronicle. Mournhold lives without knowing.
    The hunger is sealed, not undone — the player IS the seal now.
    """
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)  # the realm survives, after all
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("old_seal", state.chronicle_dir)
    io.clear()
    io.show_slow("You break the Warden. The Pall reaches for you.")
    io.show_slow("You walk past its reaching. You walk down — past the Choir,")
    io.show_slow("past Mourncross, past the Reach, past the Witherwood, past the road.")
    io.show_slow("You walk down the stair below the Pre-Pall Shrine.\n")
    io.pause(1)
    io.show_slow("Cael stands. The stone lets her stand. Her mouth empties of names.")
    io.show_slow("She passes them to you, name by name, until you can say them all.")
    io.show_slow("Then she lies down. The stone takes her, gently, like a sheet pulled up.")
    io.show_slow("She rests.\n")
    io.pause(1)
    io.show_slow("You sit where she sat. The stone closes over your mouth, and your hands,")
    io.show_slow("and your name. You begin to say the names she taught you.")
    io.show_slow("Quietly. The Pall above ground unmakes itself in silence —")
    io.show_slow("the hunger has its mouth back, and the mouth is yours now.\n")
    io.pause(2)
    io.show("=" * 50)
    io.show("🪨  THE OLD SEAL")
    io.show(f"{player.name} the {player.class_name} — the next seal under the mountain.")
    io.show("\nThe Pall is undone. The Warden is no more. Mournhold lives, and does not know.")
    io.show("You will not climb back up. You will say names. You will say them quietly.")
    io.show("Centuries from now, when the seal is tired again, someone will sit at your feet")
    io.show("and you will teach them the names — yours among them — and lie down.")
    io.show("\nThe Chronicle records: purified. The smallest, oldest, hardest ending.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _atrel_peace_screen(state):
    """The quiet ending — return the rite to Atrél; both god and Pall end together.

    Available only when ``atrel_offered`` is True (player promised Atrél to
    bring the rite back). Marks the Chronicle purified, but the screen
    deliberately does NOT name the player as the one who said the names —
    Atrél's small ending is unwitnessed by design.
    """
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("atrel_peace", state.chronicle_dir)
    io.clear()
    io.show_slow("You do not climb back to the Summit to say the names.")
    io.show_slow("You climb back down. To the Choir. To the south aisle. To Atrél.")
    io.show_slow("He is waiting. He has been waiting since you left.\n")
    io.pause(1)
    io.show_slow("You set the rite down at his altar. Not the kingdom-scale. The altar-scale.")
    io.show_slow("Atrél takes it. His hands close around it like someone receiving a wound back.")
    io.show_slow("He says: 'Thank you.' He says it small. It is the right size.")
    io.show_slow("He dies. The altar does not. Someone will set down a small grief here, one day.\n")
    io.pause(1)
    io.show_slow("And the Pall — the Pall has nothing left to be made of.")
    io.show_slow("It unmakes itself in silence. No crescendo. No witness.")
    io.show_slow("The grey goes thin. The road brightens. Nobody knows you did it.\n")
    io.pause(2)
    io.show("=" * 50)
    io.show("📿  ATRÉL'S PEACE")
    io.show(f"{player.name} the {player.class_name} — who brought the rite back.")
    io.show("\nThe Pall is undone. The Warden is no more. Atrél is dead.")
    io.show("Mournhold lives. It does not know it owes anyone a debt.")
    io.show("\nThe Chronicle records: purified, quietly. The smaller ending.")
    io.show("Future climbers will find a kingdom — and a side-altar")
    io.show("where small griefs can be set down again, the way they used to.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _purify_screen(state):
    """The mythic ending — the Pall is undone permanently."""
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("purify", state.chronicle_dir)
    io.clear()
    io.show_slow("You do not let the Pall take you, and you do not refuse it,")
    io.show_slow("and you do not climb back down. You stand still, and you")
    io.show_slow("speak — every name the kingdom forgot, from the first sealed gate")
    io.show_slow("to the last hold under the silt. You speak them all. Aloud. In order.\n")
    io.pause(1)
    io.show_slow("The Pall stops, the way a wound stops. The summit goes quiet,")
    io.show_slow("the way a long-held breath goes quiet. The grey thins, and is gone.")
    io.show_slow("The road behind you is bright, all the way down. The kingdom remembers itself.\n")
    io.pause(2)
    io.show("=" * 50)
    io.show("🌅  MOURNHOLD IS PURIFIED")
    io.show(f"{player.name} the {player.class_name} — who said the names back.")
    io.show("\nThe Pall is undone. The Warden is no more. The road is only road.")
    io.show("Future climbers will find a kingdom, not a kingdom's grave.")
    io.show("\nThe Chronicle remembers — you will see, on every next run,")
    io.show("that Mournhold lies PURIFIED. The cycle is broken.")
    _sister_realm_addendum(state, io)
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


def _other_mournhold_screen(state):
    """SQ5 — The Other Mournhold.

    Only available in a Mirror Climb. The player, standing on a Summit
    they have stood on as someone else many times, undoes the original
    wrong: not the rite, not the famine, not the gates — the act of
    forgetting itself, taken back to its first moment. The kingdom that
    remembers is the kingdom that did not need a Pall.
    """
    player, io = state.player, state.io
    chronicle.mark_purified(state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("other_mournhold", state.chronicle_dir)
    chronicle.unlock("the_other_mournhold", state.chronicle_dir)
    io.clear()
    io.show_slow("You have stood at this Summit as someone else, several times.")
    io.show_slow("You know what every ending costs. You have paid each cost yourself.")
    io.show_slow("The Pall reaches; you do not let it reach you.")
    io.show("")
    io.show_slow("Instead you step back through your own steps, and the kingdom's.")
    io.show_slow("Through the famine winter. Through the council vote. Through the rite.")
    io.show_slow("You arrive in a chamber where the rite has not yet been said.")
    io.show_slow("Twelve councilors at a long table. They have not voted.")
    io.show_slow("They look up at you the way you have looked up at every grave.")
    io.show("")
    io.show_slow("You tell them what unremembering will become if they perform it.")
    io.show_slow("You tell them about Atrél, broken. About Cael, who will swallow the last line.")
    io.show_slow("You tell them about every name you have seen — Tálva, Renan, Eldris, Paipel, the rest.")
    io.show("")
    io.show_slow("They listen. They are afraid. They vote. The rite is not performed.")
    io.show_slow("There is still a famine. There is still a hard winter. Many die.")
    io.show_slow("But the holds are fed, and remembered, and the kingdom does not learn to forget.")
    io.pause(2)
    io.show("=" * 50)
    io.show("🪞  THE OTHER MOURNHOLD")
    io.show(f"{player.name} the {player.class_name} — who undid the first wrong.")
    io.show("\nThis kingdom is not the kingdom you climbed in. It never grew a Pall,")
    io.show("because it never forgot what it owed. Both the Pall and the climb")
    io.show("never were. You remember them; you alone, here, do.")
    io.show("\nThe Chronicle records: the_other_mournhold. The mirror ending.")
    io.show("=" * 50)
    _run_summary(state)
    io.show("\nThank you for playing Mournhold.")


# ── Registry (executed at module import — populates the endings menu) ──
# Order in this list is order in the menu.

endings.register(
    "warden",
    "Be kept by the Pall  (end the run, become the Warden)",
    _warden_screen,
    lambda s: True,
)
endings.register(
    "reborn",
    "Reborn               (end this hero — earn Echoes — start again)",
    _reborn_screen,
    lambda s: True,
)
endings.register(
    "purify",
    "🌅 Purify Mournhold  (end the cycle — the Pall is undone)",
    _purify_screen,
    lambda s: chronicle.cleanses(s.chronicle_dir) >= PURIFY_CLEANSES_REQUIRED,
)
endings.register(
    "atrel_peace",
    "📿 Bring the rite back to Atrél  (the quiet end — none will know)",
    _atrel_peace_screen,
    lambda s: s.flags.get("atrel_offered", False),
)
endings.register(
    "old_seal",
    "🪨 Take Cael's place  (the oldest end — you become the seal)",
    _old_seal_screen,
    lambda s: s.flags.get("offered_old_seal", False),
)
endings.register(
    "reckoning",
    "⚖️  Honour Tálva's reckoning  (unmake Mournhold — the holds are kept)",
    _reckoning_screen,
    lambda s: s.flags.get("talva_asked", False),
)
endings.register(
    "other_mournhold",
    "🪞 The Other Mournhold  (undo the first wrong — only on a Mirror Climb)",
    _other_mournhold_screen,
    lambda s: s.flags.get("mirror_run", False),
)

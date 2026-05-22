"""Side-quest services — recurring player actions tied to cross-run progress.

Each function here is a service the player invokes from a location: pet the
cat, read Piranesi's map, write a line in the hearth-keeper's book, etc.
They're grouped because they share the same shape (small, IO-driven,
cross-run-aware via the Chronicle) and because pulling them out of
``locations.py`` shrinks the central module without changing behaviour.

The two private helpers ``_maybe_open_border`` / ``_maybe_wake_forgotten_thing``
/ ``_maybe_remember_verse`` flip per-run flags based on cross-run thresholds;
they're called from the main game loop on zone arrival. ``sing_the_verse`` is
the Last Altar service unlocked by ``lost_verse_known``.

Extracted from locations.py during the v2.3 quality audit. Every name is
re-exported from locations.py so existing callers (and tests) keep working.
"""
from . import chronicle, marks


# ── Cross-run thresholds (used here and by location_loop visibility code) ──

READER_THRESHOLD = 25         # SQ1: lore-discoveries to surface the Reader
INSOMNIAC_THRESHOLD = 50      # SQ6: Gravewatch visits to surface the Insomniac
CARETAKER_THRESHOLD = 40      # SQ2: kind acts to unlock the Caretaker ending

# SQ3 — the recurring cat
CAT_ZONE_VISITS_REQUIRED = 3  # cat shows up after N visits to a zone this run
CAT_PET_HEAL = 5
CAT_PET_STAMINA = 1


# ── SQ3 · The Recurring Cat ───────────────────────────────────────────


def _pet_the_cat(state):
    """SQ3 — pet the recurring cat.

    Small heal + stamina, increments the cross-run cat_pets counter. At
    fixed thresholds (10/25/50/100), the cat says something. At 100, the
    Chronicle marks cat_companion = True and the cat joins the player as
    a permanent +1 HP/round combat presence.
    """
    player, io = state.player, state.io
    chronicle.add_cat_pet(state.chronicle_dir)
    chronicle.add_kind_act(state.chronicle_dir)  # SQ2: a kindness
    count = chronicle.cat_pets(state.chronicle_dir)
    player.heal(CAT_PET_HEAL)
    player.restore_stamina(CAT_PET_STAMINA)
    io.show("")
    io.show_slow("🐈 The cat presses its head into your hand. You count "
                 "the small bones in its skull.")
    io.show(f"   +{CAT_PET_HEAL} HP  +{CAT_PET_STAMINA} stamina  "
            f"(cat-pets so far: {count})")
    if count == 10:
        io.show_slow("\nThe cat looks at you. 'I have been counting your runs.'")
        io.show_slow("'There are more than you remember.'")
    elif count == 25:
        # Name a fallen character if possible — it knows them.
        fallen_entries = chronicle.fallen(chronicle.load(state.chronicle_dir))
        if fallen_entries:
            name = fallen_entries[0]["player"]["name"]
            io.show_slow(f"\nThe cat says: 'I knew {name}. {name} fed me twice. "
                         f"I have not forgotten {name}.'")
        else:
            io.show_slow("\nThe cat says: 'I knew the ones who died before you "
                         "knew them. I have not forgotten.'")
    elif count == 50:
        io.show_slow("\nThe cat stands. Walks. You follow because you must.")
        io.show_slow("In a small room you have never seen, every name from your "
                     "Chronicle is on the wall.")
        io.show_slow("'I remembered them so you would not have to remember all of them.'")
    elif count == 100:
        io.show_slow("\nThe cat curls against your ankle and does not leave.")
        io.show_slow("It will walk with you, now. It will keep walking with you.")
        io.show_slow("It will mend you, a little, every round you fight.")
        io.show_slow("It will never die. The Pall does not know its name.")
        state.flags["cat_companion"] = True
    io.pause(2)


# ── SQ9 · The Witnessed Dead ───────────────────────────────────────────


def _witnessed_dead_here(state, fallen):
    """SQ9 — find a fallen character with unfinished NPC kill-quest progress
    in the CURRENT zone (matched by which NPC lives here).

    Returns a list of ``(entry, npc_id, npc, partial, needed)`` tuples — usually
    zero or one. ``partial`` is how many kills the dead one notched; ``needed``
    is the threshold. Already-resolved entries are skipped.
    """
    loc = state.content.locations[state.current_location]
    npcs_here = [e["id"] for e in loc.get("encounters", []) if e.get("type") == "npc"]
    if not npcs_here:
        return []
    results = []
    for entry in fallen:
        if entry.get("resolved"):
            continue
        progress = entry.get("progress", {})
        kills = progress.get("npc_kills", {}) if isinstance(progress, dict) else {}
        if not kills:
            continue
        for npc_id in npcs_here:
            npc = state.content.npcs.get(npc_id)
            if not npc:
                continue
            target = npc.get("target_enemy")
            if not target:
                continue
            partial = kills.get(target, 0)
            needed = npc.get("needed", 0)
            if 0 < partial < needed:
                results.append((entry, npc_id, npc, partial, needed))
                break  # one Witnessed Dead per fallen-zone pair is enough
    return results


def _honor_the_dead(state, witnessed):
    """SQ9 — take up a fallen character's unfinished work.

    Their kill-progress carries into your run as a head start; they are
    laid to rest in the Chronicle; a small memorial gold reward is given.
    """
    entry, _npc_id, npc, partial, needed = witnessed
    player, io = state.player, state.io
    dead_name = entry.get("player", {}).get("name", "a stranger")
    target = npc["target_enemy"]
    io.clear()
    io.show_slow(f"🕯️  '{dead_name} was here before you. They had counted "
                 f"{partial}/{needed} of the {target}s'")
    io.show_slow("'before the trees took them. Their tally is honest.'")
    io.show_slow(f"'Take their work. Start where {dead_name} left off.'")
    npc_kills = state.flags.setdefault("npc_kills", {})
    npc_kills[target] = max(npc_kills.get(target, 0), partial)
    memorial = 20 * partial
    player.gold += memorial
    io.show(f"\n   You take up {dead_name}'s work. Their {partial}/{needed} "
            f"is now yours.")
    io.show(f"   +{memorial} gold (memorial offering)")
    chronicle.lay_to_rest(entry, state.chronicle_dir)
    chronicle.add_kind_act(state.chronicle_dir)  # SQ2: honoring is kindness
    chronicle.unlock("witness_honored", state.chronicle_dir)  # SQ9 completion mark
    io.pause(2)


# ── SQ4 · Piranesi's Map ───────────────────────────────────────────────


def _read_piranesi_map(state):
    """SQ4 — read Piranesi's map.

    Once every Piranesi note has been read (cross-run), a folded square of
    vellum waits in the Pre-Pall Shrine. The map is a quiet hand-drawing of
    the ten small things the watcher kept track of. It can be re-read.
    """
    io = state.io
    io.clear()
    io.show_slow("🪶 You unfold the vellum. The older hand. The same hand that wrote")
    io.show_slow("on the stone, the lintel, the side of the water-butt, the column.")
    io.show("")
    io.show("                           .")
    io.show("                          /|\\         the summit, which he did not draw")
    io.show("                         / | \\")
    io.show("                        /  *  \\       a patch of slope with no ash")
    io.show("                       /   |   \\")
    io.show("                      /  __|__  \\     a column that ate the word 'name'")
    io.show("                     /  |     |  \\")
    io.show("                    /   |  o  |   \\   a square that holds one hour of light")
    io.show("                   /    |_____|    \\")
    io.show("                  /        |        \\")
    io.show("                 /     ___ * ___     \\  a stone with no lichen")
    io.show("                /     /         \\     \\")
    io.show("               /     /  *     *  \\    \\ a doorpost re-marked, a tally")
    io.show("              /     /  *       *  \\    \\ a furrow, a column of birds")
    io.show("             /     /     *           \\  \\ a tree climbed, a stone with a face")
    io.show("            /     /                    \\  \\")
    io.show("           /     /        ^             \\  \\ the hidden hold, a path")
    io.show("          /_____/_________|________________\\__\\")
    io.show("                          |")
    io.show("                     the crossroads")
    io.show("")
    io.show_slow("Below the drawing, in a smaller, later hand — yours, you realise:")
    io.show_slow("'I have walked this. I have seen what was kind. I have written it down.'")
    io.show_slow("'I do not know who will read this. I am glad of them.'")
    io.pause(2)


# ── SQ1 · The Reader Who Watches Back ──────────────────────────────────


def reader(state):
    """SQ1 — The Reader Who Watches Back.

    A presence in Gravewatch that surfaces once the player has read
    ``READER_THRESHOLD`` unique lore fragments across runs. The Reader
    has been reading along with the player from the start and finally
    introduces themselves. Once-per-run reward: a small max-HP boost
    scaling with how much the player has actually read.
    """
    player, io = state.player, state.io
    if state.flags.get("read_with_reader"):
        io.clear()
        io.show_slow("📖 The Reader is already with you, today. They look up, smile,")
        io.show_slow("close the book, and gesture for you to climb on.")
        io.pause(2)
        return
    read = chronicle.discoveries_read(state.chronicle_dir)
    io.clear()
    io.show_slow("📖 A figure at a desk in the corner of Gravewatch's hall.")
    io.show_slow("They are reading. They have been reading since you first came in,")
    io.show_slow("but they have not looked up before. They look up now.")
    io.show("")
    io.show_slow("'I am the Reader. I have read what you have read, when you read it.'")
    io.show_slow(f"'You have brought me — let me count — {read} fragments of the'")
    io.show_slow("'kingdom's lost selves. I have read each one with you.'")
    io.show_slow("'Sit. Read one more with me, the one of your own climb.'")
    io.show("")
    io.show_slow("They open their book. The page is blank, then is not blank.")
    io.show_slow("They are reading you, now. The way you have read everyone else.")
    bonus = max(2, read // 5)  # 25 reads → +5, 50 → +10, capped softly
    player.max_hp += bonus
    player.hp = min(player.hp + bonus, player.max_hp)
    state.flags["read_with_reader"] = True
    io.show(f"\n   +{bonus} max HP — the Reader has read you in.")
    io.pause(2)


# ── Hearth book ────────────────────────────────────────────────────────


def write_hearth_line(state):
    """v1.40 — A small Gravewatch service. Add a single line to the
    hearth-keeper's book. Cross-run: every future character will read
    what every previous character left, when they read the book.

    The hearth-keeper does not look up. She is letting you write.
    """
    io = state.io
    io.clear()
    io.show_slow("📝 The hearth-keeper does not look up. The pencil is on the mantel.")
    io.show_slow("Beside the pencil, the leather book is open to a fresh page.")
    io.show_slow("Below the page, the marks of previous lines. They are short. Most are.")
    io.show("")
    io.show_slow("Write a line. One. It does not have to be about you. It often is not.")
    io.show_slow("(Leave blank to step back and not write anything today.)")
    line = io.ask("\n> ").strip()
    if not line:
        io.show_slow("\nYou set the pencil back on the mantel. The hearth-keeper")
        io.show_slow("does not look up. The book is still open. You may come back.")
        io.pause(2)
        return
    chronicle.add_hearth_line(line, state.chronicle_dir)
    # v1.36 — keeping the small rite alive in the village is a kindness.
    chronicle.add_kind_act(state.chronicle_dir)
    io.show("")
    io.show_slow("You write the line. You set the pencil back. The hearth-keeper")
    io.show_slow("does not look up. The book stays open on the page. The next climber")
    io.show_slow("who picks it up will read what you wrote, and the lines before yours.")
    io.pause(2)


# ── SQ10 · The Hidden Final Truth ─────────────────────────────────────


def _write_first_line(state):
    """SQ10 — The Hidden Final Truth. A child at the Crossroads with a book.

    Surfaces once every other side-quest has been completed across runs.
    Speaking to the child lets the player write the first line of the
    Chronicle — the line every future new character will read at the
    moment of their creation, before anything else Mournhold can say.

    The player can refuse; the option will be there the next time they
    come back.
    """
    io = state.io
    io.clear()
    io.show_slow("📖 At the Crossroads, where there was no one before, there is a child.")
    io.show_slow("They are perhaps eight winters old. They have a book in their lap.")
    io.show_slow("It is the oldest thing in the kingdom, and the newest. It is the Chronicle.")
    io.show("")
    io.show_slow("'I have been keeping this for you,' the child says.")
    io.show_slow("'You have read the names. You have sat with the cat. You have remembered the verse.'")
    io.show_slow("'You have honoured a stranger's unfinished work. You have stood the climb")
    io.show_slow("'as several others. You have done all the small kindnesses Mournhold knew of.'")
    io.show("")
    io.show_slow("They open the book to the first page. The page is blank.")
    io.show_slow("'Someone has to write the first line. It will be the first line of")
    io.show_slow("'every Chronicle from this one on. Every climber who comes after you")
    io.show_slow("'will read it before they read anything else. Will you?'")
    io.show("")
    io.show("1. Yes — write the first line")
    io.show("2. Not today")
    choice = io.ask("\nYour choice? ").strip()
    if choice != "1":
        io.show_slow("\n'I will be here,' the child says. 'I have been here.'")
        io.pause(2)
        return
    io.show("")
    io.show_slow("The child hands you the book. The page is still blank.")
    io.show_slow("Write the line for whoever comes after.")
    line = io.ask("\n> ").strip()
    if not line:
        io.show_slow("\nYou hand the book back. 'Not yet,' you say. The child nods.")
        io.pause(2)
        return
    chronicle.set_first_line(line, state.chronicle_dir)
    chronicle.add_ending_seen("hidden_truth", state.chronicle_dir)
    io.show("")
    io.show_slow("The child reads what you have written. Then closes the book.")
    io.show_slow("'It is in the book now. Every new climber will read it first.'")
    io.show_slow("'It will be the first thing Mournhold says.'")
    io.show("")
    io.show_slow("                  — THE HIDDEN FINAL TRUTH —")
    io.show_slow("       You wrote the first line. There is no climb left to do.")
    io.show_slow("           Mournhold is yours, now. Be gentle with it.")
    io.pause(3)


# ── SQ2 · The Caretaker Ending ────────────────────────────────────────


def caretaker(state):
    """SQ2 — The Long Daily Ritual. The Caretaker ending.

    Surfaces in Gravewatch only after the player has accumulated 40 small
    kindnesses across all runs (discoveries read, cats petted, Hollowed
    laid to rest, fallen honored, verses sung).

    Choosing this ending ends the run differently: the player does not
    climb. They become the keeper of the kingdom's small kindnesses,
    here in Gravewatch — naming the dead, setting flowers at the graves,
    feeding the cat. The world keeps ending. They keep doing this.

    Recorded as a Caretaker fate in the Chronicle; counts as a cleanse.
    """
    io = state.io
    acts = chronicle.kind_acts(state.chronicle_dir)
    io.clear()
    io.show_slow("🌹 You sit down in Gravewatch's hall and do not stand up again.")
    io.show_slow("There is a basket of small flowers by the door. There always was.")
    io.show_slow(f"You have done {acts} small kindnesses in this kingdom — read")
    io.show_slow("its names back, knelt by its stones, fed its cat, sung its verse.")
    io.show("")
    io.show_slow("The climb is for others. Most of them will not finish it.")
    io.show_slow("The kingdom needs both — a climber, and someone here for them")
    io.show_slow("when they come back down. Or do not come back. You will be that one.")
    io.show("")
    io.show_slow("The cat finds your lap. The Insomniac, if she is here, nods.")
    io.show_slow("Someone has left a fresh lamp by the basket. You light it.")
    io.show("")
    io.show_slow("                  — THE CARETAKER —")
    io.show_slow("    You did not climb. You stayed, and you kept the small things.")
    io.show_slow("        Mournhold is harder to forget, while you are here.")
    io.pause(2)
    chronicle.record(state, "caretaker", state.chronicle_dir)
    chronicle.add_cleanse(state.chronicle_dir)
    chronicle.add_ending_seen("caretaker", state.chronicle_dir)
    # v1.51 — the character has chosen to stay; their marks die with them.
    marks.clear_sidecar(state.chronicle_dir, state.player.run_id)
    state.flags["run_ended"] = True


# ── SQ6 · The Insomniac ───────────────────────────────────────────────


def insomniac(state):
    """SQ6 — the Insomniac of Gravewatch.

    Someone who couldn't sleep, so they kept count. After 50 cross-run
    arrivals at Gravewatch, they introduce themselves and lead the player
    down to a cellar that has been growing — three rooms of stuff the
    village forgot. Once per run, on win, the player is the Counted.
    """
    player, io, content, rng = state.player, state.io, state.content, state.rng
    if state.flags.get("the_counted"):
        io.clear()
        io.show_slow("🕯️  The Insomniac nods at you. 'I have counted you, today.'")
        io.show_slow("'You came back. Most do not. Rest a while. The cellar will keep.'")
        io.pause(2)
        return
    visits = chronicle.gravewatch_visits(state.chronicle_dir)
    io.clear()
    io.show_slow("🕯️  An old woman by the cold hearth. Lamp on her knee, not lit.")
    io.show_slow("'I have not slept since the gates closed. I have counted instead.'")
    io.show_slow(f"'You have come back to Gravewatch {visits} times. I know your step.'")
    io.show_slow("'I know the way you stand at the door before you come in.'")
    io.show_slow("'There is a cellar under this room. It is full of what we forgot.'")
    io.show_slow("'I have been keeping a door for whoever was counted enough. Down.'")
    io.pause(2)
    # The descent — three escalating combats, no rest between, randomized.
    descent_pool = ["wolf", "bandit", "goblin", "drowned_thresher", "silt_drowner",
                    "gutter_wretch", "hollow_procession"]
    sampled = rng.sample(descent_pool, k=3) if hasattr(rng, "sample") else descent_pool[:3]
    io.show("")
    io.show_slow("🪨 The stairs are deeper than the room above them ought to allow.")
    io.show_slow("Three doors at the bottom. The Insomniac counts you in.")
    io.pause(1)
    from terminalquest import combat
    from terminalquest.enemy import make_enemy
    for i, enemy_id in enumerate(sampled, start=1):
        io.show(f"\n— Door {i} of 3 —")
        is_last = (i == len(sampled))
        enemy = make_enemy(enemy_id, content, state.flags)
        outcome = combat.run_combat(state, enemy, refresh_after=is_last)
        if outcome != "victory":
            io.show_slow("\n🕯️  The Insomniac is still there, when you come back up.")
            io.show_slow("'Most of you do not finish. I do not count you less for it.'")
            io.pause(2)
            return
    # All three down → grant the Counted reward.
    bonus = max(5, visits // 10)
    player.max_hp += bonus
    player.hp = min(player.hp + bonus, player.max_hp)
    state.flags["the_counted"] = True
    chronicle.unlock("the_counted", state.chronicle_dir)
    io.show("")
    io.show_slow("🕯️  The Insomniac is at the top of the stairs when you come back.")
    io.show_slow("She does not look up. She is counting again.")
    io.show_slow("'You are one of the Counted, now. There are not many.'")
    io.show_slow("'I will know your step better. Sleep, if you can.'")
    io.show(f"\n   +{bonus} max HP — you are the Counted.")
    io.pause(2)


# ── Per-arrival flag setters (Border, Forgotten Thing, Lost Verse) ────


def _maybe_open_border(state):
    """The Border opens after 2 cleanses — Arc III's gating signal."""
    if state.flags.get("border_open"):
        return
    if chronicle.cleanses(state.chronicle_dir) >= 2:
        state.flags["border_open"] = True


def _maybe_wake_forgotten_thing(state):
    """SQ7 — five characters have died in Witherwood. The thing the Pall
    forgot has been there all along. In this run, it surfaces.
    """
    if state.flags.get("forgotten_thing_awake"):
        return
    if chronicle.witherwood_only_falls(state.chronicle_dir) >= 5:
        state.flags["forgotten_thing_awake"] = True


def _maybe_remember_verse(state):
    """SQ8 — if all 4 Lost Verse fragments are already known cross-run,
    a new character begins with the verse remembered. The flag enables the
    Sing-the-Verse service at the Last Altar of Atrél.
    """
    if state.flags.get("lost_verse_known"):
        return
    if chronicle.lost_verse_fragments(state.chronicle_dir) >= 4:
        state.flags["lost_verse_known"] = True


# ── SQ8 · Sing the Lost Verse ─────────────────────────────────────────


def sing_the_verse(state):
    """SQ8 — sing the Lost Verse at the Last Altar of Atrél.

    Per-run reward: +1 to all stats (max_hp, attack, defense). Once sung in a
    run, the option goes quiet — the Pall un-remembers each verse you sing.
    Each new character climbs again carrying the verse in their throat.
    """
    player, io = state.player, state.io
    io.clear()
    io.show_slow("🎼 You stand at Atrél's altar and breathe in.")
    io.show_slow("The verse is in your throat. It has been there all the climb.")
    io.show_slow("You sing it. Not loudly. The altar is small. The verse is small.")
    io.show("")
    io.show_slow("  'We remember the holds. We remember the gates.'")
    io.show_slow("  'We remember the names. We remember the rain.'")
    io.show_slow("  'We remember the bread we did not give.'")
    io.show_slow("  'We remember. We remember. We remember.'")
    io.show("")
    io.show_slow("Something in the altar settles. Atrél, perhaps, accepting it.")
    io.show_slow("Something in you settles too — straighter, surer, kinder.")
    player.max_hp += 5
    player.hp = min(player.hp + 5, player.max_hp)
    player.attack += 1
    player.defense += 1
    io.show(f"\n   +5 max HP  +1 attack  +1 defense  ({player.name} remembers)")
    state.flags["lost_verse_sung"] = True
    chronicle.add_kind_act(state.chronicle_dir)  # SQ2: singing is kindness
    io.pause(2)

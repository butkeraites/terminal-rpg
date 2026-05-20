"""The Chronicle of the Fallen — a local record of past characters.

When a run ends — the player falls, or breaks the Warden and is kept by
the Pall as the next one — that character is appended to ``chronicle.json``,
so later runs can feel them: named at character creation, found as graves
where they fell, risen as the Hollowed, or faced at the Summit as the
Shadow Warden they became.

The chronicle is a keepsake, never load-bearing: a missing or corrupt
file simply reads as no past characters, and a failed write is swallowed.
"""
import json
import os
import tempfile
from pathlib import Path

CHRONICLE_VERSION = 1
DEFAULT_DIR = Path.home() / ".terminalquest"
_FILENAME = "chronicle.json"


def _path(chronicle_dir):
    return Path(chronicle_dir) / _FILENAME


def _load_raw(chronicle_dir):
    """Return the whole chronicle. Adds Echo currency, owned accessories,
    cleanse count, a 'purified' flag, owned pets, and side-quest counters.
    Never raises.
    """
    try:
        data = json.loads(_path(chronicle_dir).read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        unlocks = data.get("unlocks", [])
        owned = data.get("owned_accessories", [])
        owned_pets = data.get("owned_pets", [])
        echoes = data.get("echoes", 0)
        cleanses = data.get("cleanses", 0)
        purified = data.get("purified", False)
        cat_pets = data.get("cat_pets", 0)
        piranesi_ids = data.get("piranesi_notes_seen_ids", [])
        verse_ids = data.get("lost_verse_fragments_seen_ids", [])
        return {
            "entries": list(entries) if isinstance(entries, list) else [],
            "unlocks": list(unlocks) if isinstance(unlocks, list) else [],
            "owned_accessories": list(owned) if isinstance(owned, list) else [],
            "owned_pets": list(owned_pets) if isinstance(owned_pets, list) else [],
            "echoes": int(echoes) if isinstance(echoes, (int, float)) else 0,
            "cleanses": int(cleanses) if isinstance(cleanses, (int, float)) else 0,
            "purified": bool(purified),
            "cat_pets": int(cat_pets) if isinstance(cat_pets, (int, float)) else 0,
            "piranesi_notes_seen_ids": (list(piranesi_ids)
                                        if isinstance(piranesi_ids, list) else []),
            "piranesi_notes_seen": (len(piranesi_ids)
                                    if isinstance(piranesi_ids, list) else 0),
            "lost_verse_fragments_seen_ids": (list(verse_ids)
                                              if isinstance(verse_ids, list) else []),
        }
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return {"entries": [], "unlocks": [], "owned_accessories": [],
                "owned_pets": [], "echoes": 0, "cleanses": 0, "purified": False,
                "cat_pets": 0, "piranesi_notes_seen_ids": [],
                "piranesi_notes_seen": 0,
                "lost_verse_fragments_seen_ids": []}


def load(chronicle_dir=DEFAULT_DIR):
    """Return recorded characters, oldest first. Never raises."""
    return _load_raw(chronicle_dir)["entries"]


def unlocked(chronicle_dir=DEFAULT_DIR):
    """Return the set of tokens permanently unlocked across runs. Never raises."""
    return set(_load_raw(chronicle_dir)["unlocks"])


def _write(payload, chronicle_dir):
    """Atomically write the chronicle. Any failure is swallowed."""
    try:
        cdir = Path(chronicle_dir)
        cdir.mkdir(parents=True, exist_ok=True)
        handle, tmp = tempfile.mkstemp(dir=cdir, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, _path(cdir))
        except OSError:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError:
        pass


def _save(raw, chronicle_dir):
    """Atomically write the whole chronicle (entries + unlocks + Reborn store
    + the v0.7 progression layer + the v0.8 pet roster + side-quest counters)."""
    _write({
        "version": CHRONICLE_VERSION,
        "entries": raw["entries"],
        "unlocks": raw["unlocks"],
        "owned_accessories": raw["owned_accessories"],
        "owned_pets": raw["owned_pets"],
        "echoes": raw["echoes"],
        "cleanses": raw["cleanses"],
        "purified": raw["purified"],
        "cat_pets": raw["cat_pets"],
        "piranesi_notes_seen_ids": raw.get("piranesi_notes_seen_ids", []),
        "lost_verse_fragments_seen_ids":
            raw.get("lost_verse_fragments_seen_ids", []),
    }, chronicle_dir)


def record(state, fate, chronicle_dir=DEFAULT_DIR):
    """Append the current character to the chronicle.

    ``fate`` is 'fell' (died) or 'warden' (broke the Warden and was kept
    by the Pall as the next one). The write is atomic; failure is swallowed.

    SQ9 — also snapshot a tiny slice of in-run flags so a later character
    can take up a fallen one's unfinished work. ``npc_kills`` is the only
    one we capture today; the schema is extensible.
    """
    raw = _load_raw(chronicle_dir)
    raw["entries"].append({
        "fate": fate,
        "location": state.current_location,
        "seed": state.seed,
        "player": state.player.to_dict(),
        "progress": {
            "npc_kills": dict(state.flags.get("npc_kills", {})),
        },
    })
    _save(raw, chronicle_dir)


def lay_to_rest(entry, chronicle_dir=DEFAULT_DIR):
    """Mark a fallen character as freed — they no longer rise as the Hollowed."""
    raw = _load_raw(chronicle_dir)
    for stored in raw["entries"]:
        if stored == entry:
            stored["resolved"] = True
    _save(raw, chronicle_dir)


def unlock(token, chronicle_dir=DEFAULT_DIR):
    """Permanently unlock ``token`` across all future runs. Idempotent."""
    raw = _load_raw(chronicle_dir)
    if token not in raw["unlocks"]:
        raw["unlocks"].append(token)
        _save(raw, chronicle_dir)


def fallen(entries):
    """Characters who died and have not yet been laid to rest."""
    return [e for e in entries
            if e.get("fate") == "fell" and not e.get("resolved")]


def wardens(entries):
    """Characters the Pall kept — past victors, now the Shadow Warden."""
    return [e for e in entries if e.get("fate") == "warden"]


def has_completed_run(chronicle_dir=DEFAULT_DIR):
    """True if the Chronicle has a record of any completed boss run.

    Either fate counts: a Warden ending (kept by the Pall), a Reborn ending
    (refused), or a Purify ending (the cycle ended). The cleanse counter
    increments on every completion, so it is the canonical signal here.
    """
    return cleanses(chronicle_dir) > 0


def echoes(chronicle_dir=DEFAULT_DIR):
    """The Echo currency balance (earned via Reborn, spent on accessories)."""
    return _load_raw(chronicle_dir)["echoes"]


def add_echoes(amount, chronicle_dir=DEFAULT_DIR):
    """Grant Echo currency to the player. Used by the Reborn flow."""
    raw = _load_raw(chronicle_dir)
    raw["echoes"] += amount
    _save(raw, chronicle_dir)


def spend_echoes(amount, chronicle_dir=DEFAULT_DIR):
    """Subtract Echo from the balance. Returns True if affordable, False otherwise."""
    raw = _load_raw(chronicle_dir)
    if raw["echoes"] < amount:
        return False
    raw["echoes"] -= amount
    _save(raw, chronicle_dir)
    return True


def owned_accessories(chronicle_dir=DEFAULT_DIR):
    """Set of accessory ids the player has permanently bought across all runs."""
    return set(_load_raw(chronicle_dir)["owned_accessories"])


def own_accessory(accessory_id, chronicle_dir=DEFAULT_DIR):
    """Record that the player permanently owns this accessory. Idempotent."""
    raw = _load_raw(chronicle_dir)
    if accessory_id not in raw["owned_accessories"]:
        raw["owned_accessories"].append(accessory_id)
        _save(raw, chronicle_dir)


def cleanses(chronicle_dir=DEFAULT_DIR):
    """How many completed runs have purged a measure of the Pall from the realm.

    A 'cleanse' is any completed run — Warden or Reborn. Drives the v0.7
    multi-run progression: per-zone intro variants, the Survivor NPC at
    Gravewatch, scaling companions, gated quests, and the Purify ending.
    """
    return _load_raw(chronicle_dir)["cleanses"]


def add_cleanse(chronicle_dir=DEFAULT_DIR):
    """Record that another run has been completed. Called by both endings."""
    raw = _load_raw(chronicle_dir)
    raw["cleanses"] += 1
    _save(raw, chronicle_dir)


def purified(chronicle_dir=DEFAULT_DIR):
    """True once the player has chosen the Purify Mournhold ending."""
    return _load_raw(chronicle_dir)["purified"]


def mark_purified(chronicle_dir=DEFAULT_DIR):
    """Permanently mark this Chronicle as having seen the Purify ending."""
    raw = _load_raw(chronicle_dir)
    raw["purified"] = True
    _save(raw, chronicle_dir)


def owned_pets(chronicle_dir=DEFAULT_DIR):
    """Set of pet ids the player has bought (gold or trophy) across all runs."""
    return set(_load_raw(chronicle_dir)["owned_pets"])


def own_pet(pet_id, chronicle_dir=DEFAULT_DIR):
    """Record that the player permanently owns this pet. Idempotent."""
    raw = _load_raw(chronicle_dir)
    if pet_id not in raw["owned_pets"]:
        raw["owned_pets"].append(pet_id)
        _save(raw, chronicle_dir)


def cat_pets(chronicle_dir=DEFAULT_DIR):
    """How many times the player has petted the recurring cat (cross-run).

    SQ3 — the cat thresholds are 10/25/50/100 pets. At 100 the cat becomes
    a passive +1 HP/round companion that cannot die.
    """
    return _load_raw(chronicle_dir)["cat_pets"]


def add_cat_pet(chronicle_dir=DEFAULT_DIR):
    """Record one more cat-pet — used by the SQ3 menu action."""
    raw = _load_raw(chronicle_dir)
    raw["cat_pets"] += 1
    _save(raw, chronicle_dir)


def piranesi_notes(chronicle_dir=DEFAULT_DIR):
    """How many of Piranesi's notes the player has found (cross-run).

    SQ4 — Piranesi the Mapper. Notes are gentle observational discoveries
    scattered across the kingdom. At 10 found, a map appears.
    """
    raw = _load_raw(chronicle_dir)
    return raw.get("piranesi_notes_seen", 0)


def add_piranesi_note(note_id, chronicle_dir=DEFAULT_DIR):
    """Record that this specific Piranesi note has been read. Idempotent."""
    raw = _load_raw(chronicle_dir)
    seen = raw.setdefault("piranesi_notes_seen_ids", [])
    if note_id not in seen:
        seen.append(note_id)
        raw["piranesi_notes_seen"] = len(seen)
        _save(raw, chronicle_dir)


def lost_verse_fragments(chronicle_dir=DEFAULT_DIR):
    """How many fragments of the Lost Verse the player has read (cross-run).

    SQ8 — the Lost Verse. There are four fragments scattered across the
    deep zones. At 4 found, the verse is known; the player can Sing it at
    the Last Altar of Atrél for a per-run +1 to all stats.
    """
    return len(_load_raw(chronicle_dir).get("lost_verse_fragments_seen_ids", []))


def add_lost_verse_fragment(fragment_id, chronicle_dir=DEFAULT_DIR):
    """Record that this fragment of the Lost Verse has been read. Idempotent."""
    raw = _load_raw(chronicle_dir)
    seen = raw.setdefault("lost_verse_fragments_seen_ids", [])
    if fragment_id not in seen:
        seen.append(fragment_id)
        _save(raw, chronicle_dir)


def witherwood_only_falls(chronicle_dir=DEFAULT_DIR):
    """How many past characters died without leaving the Witherwood.

    SQ7 — the Boss the Pall Forgot. A creature so completely forgotten by
    the Pall that the Pall does not know it is there. It waits in the
    Witherwood for whoever has buried enough characters there to see it.
    Threshold: five falls in the forest. The boss surfaces in run six.
    """
    entries = _load_raw(chronicle_dir).get("entries", [])
    return sum(1 for e in entries
               if isinstance(e, dict)
               and e.get("fate") == "fell"
               and e.get("location") == "forest")

# Mournhold Content Audit — *Why the Reading Feels Stuck*

**Date:** 2026-05-22
**Trigger:** Player feedback — *"the writing repeats itself in different ways without adding detail; the reading feels stuck."*
**Status:** Research only. Nothing in `terminalquest/` has been touched. This document is for review before any edits.

---

## Executive summary

You were right, and the diagnosis is more specific than it felt:

| Surface | Volume | Repetition rate | Worst pattern |
|---|---|---|---|
| **Quests** (`data/quests.json`) | 2,242 entries, ~390 KB text | **60% formulaic**, 9% strong | 999 quests share *literally one sentence* with different nouns |
| **Marks** (`data/marks.json`) | 1,001 entries, ~315 KB text | **46% open with "Tonight…"** | Three-beat scene → negation → permanent-claim closer everywhere |
| **Zone intros + banners** (`data/locations.json`, `banners.py`) | 22 zones × up to 9 variants | **7 of 9 main zones** print their banner tag-line again as intro line 2-3 | Verbatim duplication fires every arrival |

**The reading feels stuck because in any given 10 lines of game text, the player is reading the same beat 4-6 times. Not the same lore — the same *sentence-shape*.** Tightening it doesn't mean cutting lore. It means killing the tics.

---

## 1. Quests — the boilerplate problem

### What the audit found

- **999 quests (44.6%) use a verbatim template**: `<quest name>. The kingdom marks it. Take them.` These are in the `b62_*` through `b85_*` ID blocks — 25 batches of 40, mechanically generated padding. The "flavor" field is literally the quest name repeated with seven boilerplate words.
- **40 more (b61_\*)** use a sister template: `<X>. The kingdom marks the moment. Take them; the mark holds.`
- **880 quests (39.3%)** end with `End them./him/her/it.`, and **273 of those** use the closer shape `End X. The Y will stay/hold/come back.`
- **1,225 quests (54.6%)** open with one of: a number word ("Three…", "Four…"), "Once you", "Across runs,", "Your sworn", or an enumerated ("A Second…", "A Third…").
- **The word "kingdom" appears in 1,122 quests (50%)** — it has lost meaning.
- Adjective stacking is **not** a major problem here (only 4 cases). The bloat is structural, not ornamental.

### Buckets

| Quality | Count | % |
|---|---|---|
| **Strong as-is** | ~200 | ~9% |
| **Mildly bloated, worth tightening** | ~670 | ~30% |
| **Genuinely repetitive / boilerplate** | ~1,370 | ~60% |

### The contrast

**Bad** (`b62_38_petmagpiewarnedyouat`): *"Magpie Warned Three Times. The kingdom marks it. Take them."*

**Good** (`bandit_hunt`): *"Three farms have gone silent this month."*

**Good** (`hidden_the_reach_remembers`): *"The first time you set foot in the silt, one drowner turned its head toward you. It has been waiting since."*

The good ones give a **concrete image** (silent farms, a drowner turning its head) and ground the lore. The bad ones acknowledge bookkeeping.

### Recommendation

**Template detection + bulk regeneration in two passes — NOT hand-edit.**

Hand-editing 1,039 boilerplate quests would burn weeks and still leave structural sameness. Better:

1. **Pass 1 — the b-block (1,039 quests, 46% of file).** Define ~12 mini-templates seeded from the 70 best non-formulaic flavors (the `engineer_a_read_the_plans` / `pallid_stag_thrice` voice). Auto-fill from each quest's `name + target_enemy + requires_mark`, producing flavors that *say something concrete about the enemy or the mark* instead of acknowledging the bookkeeping.
2. **Pass 2 — the mid-band (880 quests).** Cluster by closer-shape; pick the best 1-in-4; rewrite or delete the rest. Surgical, ~600 quests, feasible by hand.
3. **Leave alone** — the 363 clean quests.

**Net result:** from 999 identical sentences down to ~12 voice patterns; from ~273 *"End them. The Y holds"* closers down to ~60.

---

## 2. Marks — the "Tonight" tic

### What the audit found

The user's instinct was right but mis-targeted: **Atrél is not the problem.**

- **Atrél appears in only 101/1,001 marks (10%)** and is the canonical closer only inside the `forgetting` category (32 marks, ~10 with the altar closer). At 10%, that's actually well-paced.
- **462 marks (46%) open with "Tonight at/in/on/you…"** — including 52-59% of the five biggest categories. **This is the real tic.**
- **187 marks (19%) follow "Tonight…" with a "you did not / will not" second line** — the Hemingway negation becomes a mannerism.
- **165 marks (16%) end on some form of "You will [carry/not/know/remember/see]…"** turning the moment into a permanent declaration. This is the **true "collapsing the moment into a closer" problem.**
- Hedge-words everywhere: **"small" in 27%** of marks, "a small" in 16%, "quietly" 4%, "briefly" 5%, "for one count" 5%. When every grimdark beat is "a small particular," they cease to feel particular.

### Category breakdown

| Category | n | Dominant template | % adherence |
|---|---|---|---|
| **bond** | 205 | "Tonight at [place] — [recognition] — small permanent claim" | 52% |
| **found** | 158 | "Tonight [NPC] gave/left/offered — you took — it is yours now" | 53% |
| **half_truth** | 145 | "Tonight in [place] — uncanny event — you will not know / Atrél files it" | 48% |
| **mind** | 127 | "Tonight [thought/dream] — you realize X — you will, from now on, Y" | 52% |
| **promise_kept** | 126 | "Tonight at [place] — small kindness — kingdom keeps it / from now on" | 59% |
| **body** | 83 | "[Body part] has changed. It will/will not Y. You will adapt." | 25% — physical anchor saves these |
| **broken** | 61 | "[Bad thing]. You did not stop it. You will not, in this run." | 26% |
| **lost** | 36 | "The Pall took X. You will not know which. You will feel its absence." | 36% |
| **forgetting** | 32 | "You [sit/touch]. Cannot remember X. Atrél has it now." | 16% — fine |
| **promise_broken** | 28 | "You meant to. You did not. The kingdom noticed." | 25% |

### The contrast

**Bad** (`weapon_grew_an_edge_you_did_not_grind`):
> *"Your weapon has an edge today that you did not put there. You did not grind it. You did not sharpen it. The edge is there. It is sharper than your weapon should be. Some weapons do this. Yours has decided to. You will not ask why."*

Three identical negations in 4 sentences. Filler.

**Good** (`knuckles_set_into_a_shape`): two sentences, pure physical observation, ends on *"They will return to it without being asked."* The body becomes the closer. No "from now on," no negation chain.

**Good** (`reach_helka_set_a_bench_for_you`): truncates mid-sentence on *"You sit a moment. You"*. The only mark that ends on a fragment, and it works. Helka dragged a bench because she knew. That's all.

### Recommendation

**Surgical, in priority order:**

1. **Strip ~80 worst closers, don't rewrite the whole line.** The "from now on" / "you will, in this run" / "in a small way" tail can be cut from ~80 marks without losing the image. **Single highest-ROI edit.** ~3 hours of work.
2. **Diversify openers — cap "Tonight" at ~25%.** Convert ~200 "Tonight at the [X]" to "At the [X], today" / "Today" / "After" / cold opens. Makes the prose feel less liturgical.
3. **Don't drop the Atrél closer.** At 10% it's well-paced and canonically the `forgetting` signature.
4. **Don't shorten across the board.** The 22 two-line marks are some of the strongest. Forced brevity reveals which marks have a real image and which were padding.

**Useful rule for revision:** every mark must justify its third line. If line 3 doesn't add an image, cut it.

**Estimate:** ~150 marks need real editing; ~50 need ground-up rewrites (the "negation triplets"); ~800 are fine and just need less-templated neighbors.

---

## 3. Zone intros + banners — the highest-frequency surface

### What the audit found

Every zone arrival fires a banner + 1-3 intro lines. With 22 locations and ~10-50 arrivals per playthrough, this is the most-repeated text in the game.

### Per-zone grades

| Zone | Grade | Note |
|---|---|---|
| **margrave_monument** | A | Strongest intro in the game — five lines, five separate jobs |
| **hunters_cache** | A | Three crisp lines, each a new beat |
| **karst_outpost** | A | Three causal lines, no filigree |
| **pre_pall_shrine** | A | Three lines, three jobs (room, flame, figure) |
| **choir** | A | Each variant tracks a distinct stage of the kingdom's grief |
| **forest** (Witherwood) | A | Three variants each do different work |
| **mourncross** | A- | Three crisp beats, different work per variant |
| **last_dyke** | A- | Three new beats, no filler |
| **burned_library** | A- | "Half ash / half not / half-they-tried-hardest" — sharp |
| **reach** | A- | "Knows you the way a river learns a person" — best single line |
| **wynne_camp** | A- | "Column of pine snapped off six feet up" — precise |
| **last_altar** | B+ | Four crisp short lines |
| **crossroads** | B+ | Strong specifics; familiar variant adds a physical detail |
| **village** | B | Strong but familiar re-quotes "do not ask your name" |
| **summit** | B | Two variants only; cleansed line is the best in the game |
| **mountain** | B | "Grey snow never snow" is good; rest is even |
| **cave** | B- | Two of three lean on "throat of the kingdom" |
| **the_border** | B | Two lines overlap with banner |
| **hidden_hold** | B | Lines 3-5 each say "from holds Mournhold sealed" differently |
| **bone_tomb** | B- | Six lines, three of which re-state "she is the seal" |
| **drowned_holds** | C+ | Intro/familiar/cleansed all hammer "doors-are-still-doors / water-is-grief" |
| **sealed_chamber** | C | Six lines, lines 4-6 all paraphrase "they wrote what they wanted remembered" |

### The single worst pattern — banner-to-flavor verbatim duplication

The banner already prints the zone name and a tag-line. **Seven of nine main zones then re-state the tag-line in intro line 2 or 3:**

| Zone | Banner tag-line | Repeated in intro |
|---|---|---|
| forest | "the grey blew in here first, and thinnest" | Verbatim |
| reach | "like a thing trying to apologise and not knowing how" | Verbatim |
| drowned_holds | "the streets are still streets / the dead are still in the rooms" | Verbatim |
| mourncross | "every door stands open / every hearth is cold / every name is gone" | Verbatim |
| choir | "what knelt for absolution rose up as the Pall" | Verbatim |
| cave | "the kingdom's own throat" | Paraphrase |
| mountain | "what lived here did not die, only forgot the difference" | Paraphrase |

**This is the single biggest source of stickiness.** Banner does its job; flavor reads back the same line. Fires every arrival.

### Atmospheric crutches across zones

Phrases / structures in 2+ zones:

1. **"still ___ing"** (still streets, still in the rooms, still holding, still ringing, still sitting, still writing, still guards, still asking) — **~25 occurrences, pervasive**. Worst single tic.
2. **"X is the kingdom's Y"** (throat, hunger, forgetting, hand) — Reach, Gullet, Mourncross, banners.
3. **"what knelt / what was / what stayed when X went"** — Choir, Reach, Mountain, Witherwood.
4. **"you know which ___"** (familiar variants) — Witherwood, Reach, Gullet, Mourncross, Mountain, Choir.
5. **"the rite"** — Choir, Mourncross, Last Altar, Pre-Pall Shrine, Bone Tomb.
6. **"small / smaller / smallest"** (especially of grief / god / loss) — Choir, Last Altar, Bone Tomb, Hidden Hold.

### Endings cinematic audit (`endings_screens.py`)

| Lines | Issue |
|---|---|
| 281-284 (`_purify_screen`) | Three "the way X" similes back to back + "thins, and thins" doubling |
| 209-210 (`_old_seal_screen`) | "She rests. She has rested. She is resting." — three tenses, drags after preceding paragraphs |
| 213-215 (`_old_seal_screen`) | "Quietly. Quietly. The Pall above ground unmakes itself…" — doubles the previous beat |
| 168-170 (`_reckoning_screen`) | Three consecutive "Then…" sentences |
| 327-328 (`_other_mournhold_screen`) | Five "You tell them…" sequential lines; could collapse to three |

### Enemy flavor — brief

38 enemies, one flavor line each. **~12/38 use the same "still ___ing" template:**
- Doorshut: "still holding the door"
- Pall-Sworn Magistrate: "still passing sentence"
- Hollow Bellward: "rings it yet"
- Reliquary Golem: "guards the empty box"
- Grave Sentinel: "still guards"
- Dyke Warden: "still holding it"
- Library Warden: "trying since"
- (more)

The template **is** the lore — every grimdark enemy is a person who couldn't stop the thing that killed their world. But used 12 times, it stops carrying weight.

### Recommendation

**Four-stage, in priority order:**

1. **Cut the banner-to-flavor verbatim duplications first.** Seven zones, ~5 lines total. **Single biggest win.** ~1 hour of work, removes the most-fired stickiness.
2. **Rewrite the worst 5 zones' intro sets** — drowned_holds, sealed_chamber, bone_tomb, the_border, hidden_hold. Use the margrave_monument / karst_outpost pattern: each line a new beat.
3. **Style edit pass on the "still ___ing" tic.** ~25 occurrences down to ~8. The whole game loosens.
4. **Trim 5 specific spots in `endings_screens.py`** (line numbers above).

**Do NOT cut intro variants from 3 to 2.** The intro/familiar/cleansed structure is doing real narrative work. The A-grade zones prove the structure can carry distinct content. The bug is content, not structure.

---

## 4. What players actually experience

The reason the reading feels stuck is **density of repetition in any 10-line window**, not absolute lore-heaviness. Specifically:

- A player who visits 5 zones reads **7 verbatim banner-flavor duplications** (every arrival).
- A player who triggers 10 marks reads **4-5 "Tonight…" openers in a row**.
- A player who accepts 10 quests reads **4-6 "End them. The X will Y" closers**.

The lore isn't the problem. The lore is the point. **The sentence-shapes are the problem.**

---

## 5. Proposed plan

### Stage 1 — Quick wins (~1 day, biggest impact)

Estimated effort: 6-8 hours. Player-perceptible improvement: very high.

- [ ] Cut banner-to-flavor duplications in 7 zones (`locations.json` only)
- [ ] Strip ~80 closers on the worst marks (`marks.json` — single targeted edit per line)
- [ ] Trim 5 specific spots in `endings_screens.py`
- [ ] Cut "still ___ing" from ~10 enemy flavors that don't need it (`enemies.json`)

**Output:** a single commit. All changes hand-reviewed.

### Stage 2 — Surgical hand-edits (~3 days)

Estimated effort: 2-3 working days. Player-perceptible improvement: high.

- [ ] Rewrite intro sets for the 5 C-tier zones (drowned_holds, sealed_chamber, bone_tomb, the_border, hidden_hold)
- [ ] Diversify ~200 "Tonight" openers in marks (convert to "At [X], today" / "Today" / cold open)
- [ ] Rewrite ~50 worst marks ground-up (the negation-triplet ones)
- [ ] Pass 2 on quests: cluster the 880 mid-band by closer-shape, keep best 1-in-4, rewrite ~600

### Stage 3 — Template engine for the b-block (~1 week)

Estimated effort: 4-5 working days. Player-perceptible improvement: massive but risky.

- [ ] Define ~12 voice templates from the 70 best non-formulaic flavors
- [ ] Build a generator that fills templates from `name + target_enemy + requires_mark`
- [ ] Regenerate all 1,039 boilerplate quests
- [ ] Spot-review 100 random outputs; iterate templates until they read like the good ones

**Risk:** template generation can produce uncanny-valley prose. Mitigation: keep the boilerplate as fallback, gate behind a content-flag, A/B-able.

---

## 6. What I'd do first

**Stage 1 alone would already make the game feel substantially less stuck.** Specifically: cutting the seven banner-to-flavor duplications is a one-hour edit that removes the most-fired piece of repetition in the game.

If you want, I can:

1. **Just do Stage 1** — a single commit, fully hand-reviewed, easily revertible.
2. **Do Stage 1 + Stage 2** — would take ~4-5 days of focused work; the game would read noticeably tighter without losing voice.
3. **Do all three stages** — week+ of work; the most dramatic outcome but the b-block regeneration is the risky part.

**My pick:** Stage 1 first as a single commit. Live with it for a session, see if the reading feels lighter. Then decide on Stage 2 based on whether you can still spot the tics or whether Stage 1 was enough.

---

## 7. What I'd NOT do

- **Don't cut lore.** The lore is the point. Everything proposed here cuts *redundancy*, not content. The Pall is still the Pall.
- **Don't shorten across the board.** Forced brevity reveals which marks are padding and which are doing real work. Better to cut specific bad lines than uniformly trim.
- **Don't reduce intro variants from 3 to 2.** The first-visit/familiar/cleansed structure shows the world progressing without needing mechanics. Keep it.
- **Don't kill the Atrél closer.** At 10% it's well-paced. It's the *secular* "you will, from now on" that's worn out.
- **Don't auto-regenerate the mid-band quests.** Templates work for the boilerplate b-block (which has none of its own voice). The mid-band has voice that's just stuck in formula — it deserves hand editing.

---

## 8. Files inspected (research only — none modified)

- `terminalquest/data/quests.json` (2,242 entries, 839 KB)
- `terminalquest/data/marks.json` (1,001 entries, 676 KB)
- `terminalquest/data/locations.json` (22 entries, 132 KB)
- `terminalquest/data/enemies.json` (38 entries, 12 KB)
- `terminalquest/banners.py` (14 KB)
- `terminalquest/endings_screens.py` (19 KB)

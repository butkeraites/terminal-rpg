"""ASCII map of Mournhold for the TUI's left panel.

A pure renderer: given the current location id and the set of past
characters' fall locations, returns a list of strings ready to print into
a curses window. No I/O, no curses dependency — easy to unit test.

The geographic layout follows the design keyframe (design/tui/04_map_full.txt).
Width target ~50 columns so the panel fits left of the hearth log on a
100-column terminal.

Mark conventions:
  ►Name   the player is here
  Name†   a past character fell here (any number, just shown as one †)
  Name    normal
"""

# Hand-set template. ``{key}`` placeholders are substituted with marked,
# centred labels by render(). Keep slot widths in sync with the labels in
# LABELS — long names get short display forms there.
_TEMPLATE = """\

   Map of Mournhold

                  {summit:^14}
                        │
                  {mountain:^14}
                        │
            {choir:^10} ─ {library:^11}
                        │
                {mourncross:^14}
                        │
                {crossroads:^14}
                /         │         \\
   {gravewatch:^14} {witherwood:^14} {hidden:^14}
        │                 │
   {reach:^14}    {prepall:^14}
        │                 │
   {dholds:^14}    {bonetomb:^14}
        │                 │
   {gullet:^14}    {sealed:^14} ─ {altar:^12}
        │
   {dyke:^14} ─ {border:^10} ─ {wynne:^10}
                                    │
                            {karst:^14}
                                    │
                            {margrave:^14}

   {cache:^14}  (off the Witherwood trail)
"""

# Display label per location id. The short form keeps the map inside its
# ~50-column panel — Pre-Pall Shrine becomes Pre-Pall, etc.
LABELS = {
    "summit":            ("summit",     "Summit"),
    "mountain":          ("mountain",   "Climb"),
    "choir":             ("choir",      "Choir"),
    "burned_library":    ("library",    "Library"),
    "mourncross":        ("mourncross", "Mourncross"),
    "crossroads":        ("crossroads", "Crossroads"),
    "village":           ("gravewatch", "Gravewatch"),
    "forest":            ("witherwood", "Witherwood"),
    "hidden_hold":       ("hidden",     "Hidden Hold"),
    "reach":             ("reach",      "Sodden Reach"),
    "pre_pall_shrine":   ("prepall",    "Pre-Pall"),
    "drowned_holds":     ("dholds",     "Drowned"),
    "bone_tomb":         ("bonetomb",   "Bone Tomb"),
    "cave":              ("gullet",     "Gullet"),
    "sealed_chamber":    ("sealed",     "Sealed"),
    "last_altar":        ("altar",      "Last Altar"),
    "last_dyke":         ("dyke",       "Last Dyke"),
    "the_border":        ("border",     "Border"),
    "wynne_camp":        ("wynne",      "Wynne"),
    "karst_outpost":     ("karst",      "Karst"),
    "margrave_monument": ("margrave",   "Margrave"),
    "hunters_cache":     ("cache",      "Hunter's Cache"),
}


_ASCII_FALLBACK = {"►": ">", "†": "+", "│": "|", "─": "-", "╳": "x"}


def _ascii_safe(text):
    out = []
    for ch in text:
        out.append(_ASCII_FALLBACK.get(ch, ch))
    return "".join(out)


def render(current_loc_id=None, ghost_locs=None, ascii_mode=False):
    """Return the map as a list of lines, ready to print into a window."""
    ghost_set = set(ghost_locs or [])

    def mark(loc_id, label):
        prefix = "►" if loc_id == current_loc_id else ""
        suffix = "†" if loc_id in ghost_set else ""
        return f"{prefix}{label}{suffix}"

    substitutions = {}
    for loc_id, (key, label) in LABELS.items():
        substitutions[key] = mark(loc_id, label)

    text = _TEMPLATE.format(**substitutions)
    if ascii_mode:
        text = _ascii_safe(text)
    return text.splitlines()

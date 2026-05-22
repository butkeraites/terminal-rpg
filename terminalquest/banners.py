"""ASCII banners for zones and key story moments.

Hand-set, one per zone — figlet's bubbly shaded fonts are too cheerful for
the Pall. Keyed by location id (matching ``state.current_location``) plus
the three special keys ``title``, ``death``, ``new_run``.

Print with ``print_banner(io, key)``. If the key isn't in BANNERS the call
is a no-op — adding a new zone without a banner is not an error, the zone
just enters quietly.

When ``io.ascii_mode`` is on, the box-drawing and shading characters are
substituted for their ASCII equivalents so terminals without unicode font
support still get a recognisable banner instead of tofu boxes.
"""

_ASCII_FALLBACKS = {
    "─": "-", "━": "-", "═": "=",
    "│": "|", "┃": "|", "║": "|",
    "┌": "+", "┐": "+", "└": "+", "┘": "+",
    "╔": "+", "╗": "+", "╚": "+", "╝": "+",
    "├": "+", "┤": "+", "┬": "+", "┴": "+", "┼": "+",
    "▒": "#", "░": ".", "▓": "%",
    "▌": "|", "▐": "|", "▀": "-", "▄": "-", "█": "#",
    "≈": "~", "✚": "+", "▼": "v", "▲": "^",
    "·": ".", "•": "*",
}


def _ascii_safe(text):
    out = []
    for ch in text:
        out.append(_ASCII_FALLBACKS.get(ch, ch))
    return "".join(out)


def print_banner(io, key):
    """Print the banner for ``key``, or do nothing if there isn't one."""
    banner = BANNERS.get(key)
    if banner is None:
        return
    if getattr(io, "ascii_mode", False):
        banner = _ascii_safe(banner)
    io.show("")
    for line in banner.splitlines():
        io.show(line)
    io.show("")


BANNERS = {

    # ── special moments ─────────────────────────────────────────────────

    "title": r"""
       ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
       ▒▒                                                         ▒▒
       ▒▒        M    O    U    R    N    H    O    L    D        ▒▒
       ▒▒                                                         ▒▒
       ▒▒        the kingdom that ended in one breath             ▒▒
       ▒▒                                                         ▒▒
       ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
""".strip("\n"),

    "death": r"""
       ─────────────────────────────────────────────────────────────

              the kingdom kept the rest.

                                                another, then.

       ─────────────────────────────────────────────────────────────
""".strip("\n"),

    "new_run": r"""
                  again, then.   again, then.   again.

                  ─────────────────────────────────────
""".strip("\n"),

    # ── zones ───────────────────────────────────────────────────────────

    "crossroads": r"""
                              \                /
                                \            /
                                  \        /
       ────────────  T H E   C R O S S R O A D S  ────────────
                                  /        \
                                /            \
                              /                \
""".strip("\n"),

    "village": r"""
                                 .  ' )
                                  ( .
                                   ` -
                 G    R    A    V    E    W    A    T    C    H
                       — names are for the dead —
""".strip("\n"),

    "forest": r"""
         |\        /|       /|        |\       /|      /|
         | \      / |      / |        | \     / |     / |
         |  \    /  |     /  |        |  \   /  |    /  |
                T H E    W I T H E R W O O D
                — the grey blew in here first, and thinnest —
""".strip("\n"),

    "reach": r"""
       ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                T H E   S O D D E N   R E A C H
       ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
       — like a thing trying to apologise and not knowing how —
""".strip("\n"),

    "drowned_holds": r"""
       ≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈
       ≈≈    T H E   D R O W N E D   H O L D S    ≈≈
       ≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈
              — the streets are still streets —
              — the dead are still in the rooms —
""".strip("\n"),

    "cave": r"""
                  \\                                  //
                   \\                                //
                    \\         T H E   G U L L E T  //
                     \\                            //
                      \\                          //
                       — the kingdom's own throat —
""".strip("\n"),

    "mourncross": r"""
                |
                |
                |       M    O    U    R    N    C    R    O    S    S
                |
                |       every door stands open.
                |       every hearth is cold.
                |       every name is gone.
                |
                |             — forgotten in one breath, and obeyed —
""".strip("\n"),

    "choir": r"""
         │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
         │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
              T H E   U N A N S W E R E D   C H O I R
         │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
              — what knelt for absolution rose up as the Pall —
""".strip("\n"),

    "mountain": r"""
                                  ▲
                                 ▲ ▲
                                ▲   ▲
                               ▲     ▲
                              ▲       ▲
                T H E   A S H E N   C L I M B
                — what lived here did not die, only forgot the difference —
""".strip("\n"),

    "summit": r"""
         ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
              T H E   S H R O U D E D   S U M M I T
         ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
              — something waits that was a person once, and won —
""".strip("\n"),

    "hunters_cache": r"""
                  \________________/
                   \              /
                    \   .    ' ) /
                     \    ( .   /         T H E
                      \________/            H U N T E R ' S
                                              C A C H E
                  — something is still here. it heard you coming —
""".strip("\n"),

    "last_dyke": r"""
       ═════════════════════════════════════════════════════════════
                T H E   L A S T   D Y K E
       ═════════════════════════════════════════════════════════════
                                   ▌
                                   ▌
                                   ▌  ← something stands on it
""".strip("\n"),

    "burned_library": r"""
       ▓▓▓░░▓▓▓░░░▓▓▓░░▓▓▓▓░░░░▓▓▓░░▓▓▓░░░░░▓▓▓░░▓▓▓░░▓▓▓
       ▓▓▓     ▓▓▓     ▓▓▓▓        ▓▓▓     ▓▓▓     ▓▓▓
                T H E   B U R N E D   L I B R A R Y
       ▓▓▓     ▓▓▓     ▓▓▓▓        ▓▓▓     ▓▓▓     ▓▓▓
              — the half they tried hardest to burn —
""".strip("\n"),

    "the_border": r"""
       ─────────────────────────────────────────────────────────────
                T H E   B O R D E R
       ─────────────────────────────────────────────────────────────
              three sister realms watched Mournhold die
""".strip("\n"),

    "karst_outpost": r"""
       T H E   K A R S T   O U T P O S T
                       ▌
                       ▌     ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
                       ▌      ~  ~~~~  ~~~  ~~~~~  ~~~  ~~~~~~  ~
                       ▌     ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
              — Mournhold returned the grain sealed —
""".strip("\n"),

    "wynne_camp": r"""
         |     |     |     |     |     |     |     |     |     |
         ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼

            T H E   S I L E N T   C A M P   O F   W Y N N E
                — two thousand soldiers. the army did not return —
""".strip("\n"),

    "margrave_monument": r"""
                              ▌▌▌▌▌▌▌▌
                              ▌      ▌
                              ▌      ▌
                              ▌      ▌
              T H E   M A R G R A V E ' S   M O N U M E N T
                              ▌      ▌
       ══════════════════════ ▌══════▌ ══════════════════════════
                              — at market rate —
""".strip("\n"),

    "hidden_hold": r"""
                          \                /
                           \______________/
                          /                \         T H E
                         /     .       .    \          H I D D E N
                        /__________________  \           H O L D
              — three generations. none from Mournhold —
""".strip("\n"),

    "sealed_chamber": r"""
       ╔══════════════════════════════╗
       ║   A N N E                    ║
       ║    they wrote, before they  ░░║
       ║   B O R E L                  ║         T H E
       ║    died, the things they   ░░░║           S E A L E D
       ║   C A E L                    ║              C H A M B E R
       ║    wanted remembered.   ░░░░░░║
       ║   . . . . . . . . . .        ║
       ╚══════════════════════════════╝
              — five names. five overturned chairs. —
""".strip("\n"),

    "last_altar": r"""
                              ┌─────┐
                              │  ✚  │
                              │     │
                              └──┬──┘     T H E   L A S T   A L T A R
                       ═════════╧═══════
                                          — whatever is at the altar —
                                          — is also alone —
""".strip("\n"),

    "pre_pall_shrine": r"""
                              ┌─────┐
                              │  ✚  │
                              │  ·  │     T H E   P R E - P A L L
                              └──┬──┘             S H R I N E
                       ═════════╧═══════
                                          — waiting to be remembered —
""".strip("\n"),

    "bone_tomb": r"""
       ░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓
       ▒▓                                                     ▓▒
       ▒▓        T H E    B O N E    T O M B                  ▓▒
       ▒▓                                                     ▓▒
       ░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓░▒▓
              — she turns her head only a little —
              — she sees you —
""".strip("\n"),
}

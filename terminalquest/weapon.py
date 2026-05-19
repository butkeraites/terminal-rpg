"""Combinatorial weapons, assembled from one component per slot.

A weapon is built from four interchangeable components — a head, a haft, a
core and an inscription — defined in ``data/components.json``. Its resolved
``stats`` are the sum of those components' bonuses, and are applied to the
wielder while the weapon is equipped (see ``Player.equip_weapon``).
"""

WEAPON_SLOTS = ("head", "haft", "core", "inscription")


class Weapon:
    """A weapon: a name, the four components it is built from, the resolved
    stat bonuses it grants its wielder, and any combat procs it carries."""

    def __init__(self, name, components, stats, procs=None):
        self.name = name
        self.components = dict(components)
        self.stats = dict(stats)
        self.procs = list(procs or [])

    def summary(self):
        """A compact one-line description of the weapon's bonuses and procs."""
        icons = {"attack": "⚔️", "defense": "🛡️", "max_hp": "❤️", "max_stamina": "⚡"}
        parts = [f"{icons[s]}+{self.stats[s]}"
                 for s in ("attack", "defense", "max_hp", "max_stamina")
                 if self.stats.get(s)]
        for proc in self.procs:
            parts.append(f"{proc['status']} on {proc['trigger'].replace('on_', '')}")
        return "  ".join(parts) or "(no bonuses)"

    def to_dict(self):
        """Serialize to a plain dict for saving."""
        return {
            "name": self.name,
            "components": dict(self.components),
            "stats": dict(self.stats),
            "procs": list(self.procs),
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a Weapon from a saved dict."""
        return cls(data["name"], data["components"], data["stats"],
                   data.get("procs", []))


def make_weapon(content, components, name):
    """Assemble a Weapon from a ``{slot: component_id}`` mapping.

    The weapon's stats are the summed bonuses of its four components, and
    its procs are whatever combat triggers those components carry.
    """
    stats, procs = {}, []
    for slot in WEAPON_SLOTS:
        component = content.components[slot][components[slot]]
        for stat, amount in component.get("stats", {}).items():
            stats[stat] = stats.get(stat, 0) + amount
        if "proc" in component:
            procs.append(dict(component["proc"]))
    return Weapon(name, components, stats, procs)


def roll_weapon(content, act, rng, unlocked=None):
    """Assemble a random weapon from components of tier <= ``act``.

    Deeper acts unlock higher-tier components, so salvage improves as the
    journey descends. Components carrying an ``unlock`` token are excluded
    unless that token is in ``unlocked``; pass ``None`` to ignore gating
    entirely (used by balance sampling). The weapon is named after its head.
    """
    chosen = {}
    for slot in WEAPON_SLOTS:
        pool = [cid for cid, comp in content.components[slot].items()
                if comp.get("tier", 1) <= act
                and (unlocked is None or "unlock" not in comp
                     or comp["unlock"] in unlocked)]
        chosen[slot] = rng.choice(pool)
    return make_weapon(content, chosen, content.components["head"][chosen["head"]]["name"])

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

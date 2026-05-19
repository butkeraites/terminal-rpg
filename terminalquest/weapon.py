"""Combinatorial weapons, assembled from one component per slot.

A weapon is built from four interchangeable components — a head, a haft, a
core and an inscription — defined in ``data/components.json``. Its resolved
``stats`` are the sum of those components' bonuses, and are applied to the
wielder while the weapon is equipped (see ``Player.equip_weapon``).
"""

WEAPON_SLOTS = ("head", "haft", "core", "inscription")


class Weapon:
    """A weapon: a name, the four components it is built from, and the
    resolved stat bonuses it grants its wielder."""

    def __init__(self, name, components, stats):
        self.name = name
        self.components = dict(components)
        self.stats = dict(stats)

    def to_dict(self):
        """Serialize to a plain dict for saving."""
        return {
            "name": self.name,
            "components": dict(self.components),
            "stats": dict(self.stats),
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a Weapon from a saved dict."""
        return cls(data["name"], data["components"], data["stats"])


def make_weapon(content, components, name):
    """Assemble a Weapon from a ``{slot: component_id}`` mapping.

    The weapon's stats are the summed bonuses of its four components.
    """
    stats = {}
    for slot in WEAPON_SLOTS:
        component = content.components[slot][components[slot]]
        for stat, amount in component.get("stats", {}).items():
            stats[stat] = stats.get(stat, 0) + amount
    return Weapon(name, components, stats)

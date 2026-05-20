"""Accessories — trinkets and rings unlocked via the Reborn prestige system.

An accessory is a fixed catalogue entry in ``data/accessories.json``. Once
bought (with Echo currency) at the Echo Trader, it is permanently owned
across every future run via the Chronicle, and can be equipped to a trinket
or ring slot for its passive stat bonus.
"""


class Accessory:
    """An equippable trinket or ring: id, name, slot (trinket|ring), stats, flavor."""

    def __init__(self, accessory_id, name, slot, stats, flavor=""):
        self.accessory_id = accessory_id
        self.name = name
        self.slot = slot
        self.stats = dict(stats)
        self.flavor = flavor

    def summary(self):
        """A compact one-line description of the accessory's bonuses.

        Each stat carries a text label after the emoji so terminals that can't
        render emoji glyphs still convey what every number means.
        """
        icons = {"attack": "⚔️", "defense": "🛡️", "max_hp": "❤️",
                 "max_stamina": "⚡", "crit_bonus": "🎯", "dodge_chance": "💨"}
        labels = {"attack": "atk", "defense": "def", "max_hp": "HP",
                  "max_stamina": "stamina", "crit_bonus": "crit",
                  "dodge_chance": "dodge"}
        parts = []
        for stat, amount in self.stats.items():
            icon = icons.get(stat, stat)
            label = labels.get(stat, stat)
            if stat in ("crit_bonus", "dodge_chance"):
                parts.append(f"{icon}+{int(amount * 100)}% {label}")
            else:
                parts.append(f"{icon}+{amount} {label}")
        return "  ".join(parts) or "(no bonuses)"

    def to_dict(self):
        return {
            "accessory_id": self.accessory_id,
            "name": self.name,
            "slot": self.slot,
            "stats": dict(self.stats),
            "flavor": self.flavor,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["accessory_id"], data["name"], data["slot"],
                   data["stats"], data.get("flavor", ""))


def make_accessory(content, accessory_id):
    """Build an Accessory from a catalog entry by id."""
    entry = content.accessories[accessory_id]
    return Accessory(accessory_id, entry["name"], entry["slot"],
                     entry.get("stats", {}), entry.get("flavor", ""))

"""Companions — bought once at Gravewatch, fight alongside the player.

A companion is a fixed catalogue entry from ``data/companions.json``. Once
recruited, it acts each round after the player turn but before the enemy's,
contributing a damage strike or a heal depending on its ``kind``. Companions
do not take damage — they are spirit-aid, not vulnerable allies. One
companion per run; the existing one must be released before a new one can
be hired.
"""


class Companion:
    """A spirit-aid recruit: name, kind (damage|heal), power, and flavor."""

    def __init__(self, companion_id, name, kind, power, flavor=""):
        self.companion_id = companion_id
        self.name = name
        self.kind = kind
        self.power = power
        self.flavor = flavor

    def summary(self):
        """One-line description of what the companion does each round."""
        if self.kind == "damage":
            return f"Strikes for {self.power} damage each round."
        if self.kind == "heal":
            return f"Mends you for {self.power} HP each round."
        return "(unknown effect)"

    def to_dict(self):
        return {
            "companion_id": self.companion_id,
            "name": self.name,
            "kind": self.kind,
            "power": self.power,
            "flavor": self.flavor,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["companion_id"], data["name"], data["kind"],
                   data["power"], data.get("flavor", ""))


def make_companion(content, companion_id):
    """Build a Companion from a catalog entry by id."""
    entry = content.companions[companion_id]
    return Companion(companion_id, entry["name"], entry["kind"],
                     entry["power"], entry.get("flavor", ""))

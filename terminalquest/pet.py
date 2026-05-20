"""Pets — equippable beasts that grant passive stat bonuses.

Pets live in the new ``pet`` equipment slot alongside weapon, armor, trinket
and ring. Unlike companions (active combat allies), pets are passive: their
stat contribution is applied while equipped and removed on unequip. A pet
also has an optional ``regen_per_round`` field — the Hearth Cat's gimmick —
that fires from combat at the top of each round.

Pets are acquired at the Beastmaster (gold) or by trading enemy trophies.
Once bought, they are permanently owned across all future runs.
"""


class Pet:
    """A pet: id, name, stats, optional per-round regen, and flavor."""

    def __init__(self, pet_id, name, stats, regen_per_round=0, flavor=""):
        self.pet_id = pet_id
        self.name = name
        self.stats = dict(stats)
        self.regen_per_round = regen_per_round
        self.flavor = flavor

    def summary(self):
        """A compact line of what the pet contributes."""
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
        if self.regen_per_round:
            parts.append(f"❤️+{self.regen_per_round}/round")
        return "  ".join(parts) or "(no bonuses)"

    def to_dict(self):
        return {
            "pet_id": self.pet_id,
            "name": self.name,
            "stats": dict(self.stats),
            "regen_per_round": self.regen_per_round,
            "flavor": self.flavor,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["pet_id"], data["name"], data["stats"],
                   data.get("regen_per_round", 0), data.get("flavor", ""))


def make_pet(content, pet_id):
    """Build a Pet from a catalog entry by id."""
    entry = content.pets[pet_id]
    return Pet(pet_id, entry["name"], entry.get("stats", {}),
               entry.get("regen_per_round", 0), entry.get("flavor", ""))

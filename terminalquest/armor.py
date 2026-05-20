"""Armor pieces — a separate equipment slot that grants defense and dodge.

Unlike weapons, armor pieces are not combinatorial. Each piece is a fixed
catalogue entry in ``data/armor.json``, bought from the Quartermaster at
Gravewatch. An equipped armor adds its ``stats`` (defense, max_hp) and its
``dodge_chance`` to the player. A successful dodge bypasses the minimum-1
damage floor: the hit lands for zero.
"""


class Armor:
    """An armor piece: a name, stat bonuses, a dodge chance, and a flavor line."""

    def __init__(self, armor_id, name, stats, dodge_chance, flavor=""):
        self.armor_id = armor_id
        self.name = name
        self.stats = dict(stats)
        self.dodge_chance = dodge_chance
        self.flavor = flavor

    def summary(self):
        """A compact one-line description of the armor's bonuses.

        Each stat carries a text label after the emoji so terminals that can't
        render emoji glyphs still convey what every number means.
        """
        icons = {"defense": "🛡️", "max_hp": "❤️"}
        labels = {"defense": "def", "max_hp": "HP"}
        parts = [f"{icons[s]}+{self.stats[s]} {labels[s]}"
                 for s in ("defense", "max_hp")
                 if self.stats.get(s)]
        if self.dodge_chance:
            parts.append(f"💨 {int(self.dodge_chance * 100)}% dodge")
        return "  ".join(parts) or "(no bonuses)"

    def to_dict(self):
        """Serialize to a plain dict for saving."""
        return {
            "armor_id": self.armor_id,
            "name": self.name,
            "stats": dict(self.stats),
            "dodge_chance": self.dodge_chance,
            "flavor": self.flavor,
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild an Armor from a saved dict."""
        return cls(data["armor_id"], data["name"], data["stats"],
                   data["dodge_chance"], data.get("flavor", ""))


def make_armor(content, armor_id):
    """Build an Armor from a catalog entry by id."""
    entry = content.armor[armor_id]
    return Armor(armor_id, entry["name"], entry.get("stats", {}),
                 entry.get("dodge_chance", 0.0), entry.get("flavor", ""))

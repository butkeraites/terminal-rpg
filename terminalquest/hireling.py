"""Hirelings — vulnerable combat allies, paid in gold once per run.

Unlike companions (invulnerable spirits) and pets (passive bonuses), a
hireling is a real ally that takes blows in your place. They have their
own ``hp`` that ticks down when enemy attacks land. They act once per round:
healing you when you are bloodied, or drinking a Health Potion from your
bag to mend themselves.

If a hireling dies, they are gone for the rest of the run — and the
Chronicle records 'fallen_hireling' so a random combat encounter can later
spawn them as a Forsaken Sworn (a beefed-up enemy bearing their name).
"""

from __future__ import annotations
from .combatant import Combatant


class Hireling(Combatant):
    """A hired ally: id, name, hp/max_hp, defense, heal_per_round, flavor.

    Inherits ``take_damage`` and ``statuses`` from Combatant so the existing
    combat helpers (``_perform_attack``, status checks) work uniformly when
    an enemy strike is redirected from the player to the hireling.
    """

    def __init__(self, hireling_id, name, max_hp, defense, heal_per_round, flavor=""):
        super().__init__()
        self.hireling_id = hireling_id
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.defense = defense
        self.heal_per_round = heal_per_round
        self.flavor = flavor

    def summary(self):
        return (f"❤️{self.hp}/{self.max_hp} HP  🛡️{self.defense} def  "
                f"heals you {self.heal_per_round}/round")

    def to_dict(self):
        return {
            "hireling_id": self.hireling_id,
            "name": self.name,
            "max_hp": self.max_hp,
            "hp": self.hp,
            "defense": self.defense,
            "heal_per_round": self.heal_per_round,
            "flavor": self.flavor,
        }

    @classmethod
    def from_dict(cls, data):
        h = cls(data["hireling_id"], data["name"], data["max_hp"],
                data["defense"], data["heal_per_round"], data.get("flavor", ""))
        h.hp = data.get("hp", h.max_hp)
        return h


def make_hireling(content, hireling_id):
    """Build a Hireling from a catalog entry by id."""
    entry = content.hirelings[hireling_id]
    return Hireling(hireling_id, entry["name"], entry["max_hp"],
                    entry["defense"], entry["heal_per_round"],
                    entry.get("flavor", ""))

"""Shared base class for the Player and Enemy."""
from . import status


class Combatant:
    """Anything that can fight: owns HP, defense and status effects.

    Subclasses must set ``name``, ``hp``, ``max_hp``, ``attack`` and
    ``defense`` before ``take_damage`` is called.
    """

    def __init__(self):
        self.statuses = {}

    def take_damage(self, damage):
        """Apply ``damage`` after defense and status modifiers; min 1.

        Returns the actual HP lost.
        """
        actual = max(1, damage - self.defense)
        actual = max(1, round(actual * status.damage_taken_multiplier(self)))
        self.hp -= actual
        return actual

    def is_alive(self):
        return self.hp > 0

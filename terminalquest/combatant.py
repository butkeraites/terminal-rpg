"""Shared base class for the Player and Enemy."""
from . import status


class Combatant:
    """Anything that can fight: owns HP, defense and status effects.

    Subclasses must set ``name``, ``hp``, ``max_hp``, ``attack`` and
    ``defense`` before ``take_damage`` is called.
    """

    def __init__(self):
        self.statuses = {}

    def take_damage(self, damage, attacker_mult=1.0):
        """Apply ``damage`` after defense and status modifiers; min 1.

        ``attacker_mult`` is the attacker's outgoing-damage multiplier
        (reduced while ``weak``). It applies *after* defense, so the
        reduction scales cleanly instead of flooring against flat defense.
        Returns the actual HP lost.
        """
        actual = max(1, damage - self.defense)
        actual = max(1, round(actual * attacker_mult * status.damage_taken_multiplier(self)))
        self.hp -= actual
        return actual

    def is_alive(self):
        return self.hp > 0

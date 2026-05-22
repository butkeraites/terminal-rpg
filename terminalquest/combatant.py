"""Shared base class for the Player and Enemy."""

from __future__ import annotations

from . import status


class Combatant:
    """Anything that can fight: owns HP, defense and status effects.

    Subclasses must set ``name``, ``hp``, ``max_hp``, ``attack`` and
    ``defense`` before ``take_damage`` is called.
    """

    # Common fields subclasses are expected to set. Declared here so
    # callers can rely on the attribute names existing on any Combatant.
    name: str
    hp: int
    max_hp: int
    attack: int
    defense: int
    statuses: dict[str, int]

    def __init__(self) -> None:
        self.statuses = {}

    def take_damage(self, damage: int, attacker_mult: float = 1.0) -> int:
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

    def is_alive(self) -> bool:
        return self.hp > 0

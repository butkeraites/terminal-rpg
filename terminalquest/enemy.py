"""Enemy combatants, built from content data."""
from .combatant import Combatant


class Enemy(Combatant):
    """A hostile combatant. ``ai`` selects its behaviour in combat."""

    def __init__(self, enemy_id, enemy_def):
        super().__init__()
        self.enemy_id = enemy_id
        self.name = enemy_def["name"]
        self.max_hp = enemy_def["hp"]
        self.hp = self.max_hp
        self.attack = enemy_def["attack"]
        self.defense = enemy_def["defense"]
        self.xp_reward = enemy_def["xp_reward"]
        self.gold_reward = enemy_def["gold_reward"]
        self.ai = enemy_def["ai"]
        # Optional special move used by the "caster" AI.
        self.ability = enemy_def.get("ability")
        # Optional one-line flavour shown when the enemy appears.
        self.flavor = enemy_def.get("flavor", "")
        # Set to a pending action name while a big attack is telegraphed.
        self.winding_up = None


def make_enemy(enemy_id, content):
    """Construct a fresh Enemy instance from loaded content."""
    return Enemy(enemy_id, content.enemies[enemy_id])

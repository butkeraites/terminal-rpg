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
        # Turn counter the "relentless" AI uses to time its surge.
        self.turns_taken = 0
        # Latched once an "enrager" enemy drops past its HP threshold.
        self.enraged = False


def make_enemy(enemy_id, content):
    """Construct a fresh Enemy instance from loaded content."""
    return Enemy(enemy_id, content.enemies[enemy_id])


def make_hollowed(entry):
    """Build a Hollowed — a Pall-twisted past character — from a Chronicle entry."""
    p = entry["player"]
    return Enemy("hollowed", {
        "name": f"Hollow {p['name']}",
        "hp": p["max_hp"],
        "attack": p["attack"],
        "defense": p["defense"],
        "xp_reward": p["level"] * 25,
        "gold_reward": p.get("gold", 0),
        "ai": "aggressive",
        "flavor": (f"It wears {p['name']}'s face — the {p['class_name']} who came "
                   f"before you. The Pall kept what was left."),
    })


def make_warden(entry, content):
    """The Shadow Warden as a past victor — kept by the Pall, wearing their face.

    Mechanically the tuned boss; narratively the last character who won.
    """
    p = entry["player"]
    return Enemy("shadow_warden", {
        **content.enemies["shadow_warden"],
        "name": f"{p['name']}, the Shadow Warden",
        "flavor": (f"It wears {p['name']}'s face — the {p['class_name']} who broke "
                   f"the Pall and was kept by it. You climb to do the same."),
    })

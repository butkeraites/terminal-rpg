"""The player character and its progression logic."""
from .combatant import Combatant
from .weapon import Weapon, make_weapon

STARTING_GOLD = 50
STARTING_XP_TO_LEVEL = 100
LEVEL_XP_GROWTH = 1.5

# Every level-up grants this baseline, plus one player-chosen boon.
LEVEL_BASELINE = {"max_hp": 10, "attack": 2, "defense": 1, "max_stamina": 1}

LEVEL_BOONS = {
    "vigor": {"name": "Vigor", "blurb": "+25 Max HP", "gains": {"max_hp": 25}},
    "might": {"name": "Might", "blurb": "+7 Attack", "gains": {"attack": 7}},
    "bulwark": {"name": "Bulwark", "blurb": "+4 Defense, +3 Stamina",
                "gains": {"defense": 4, "max_stamina": 3}},
}

# Inventory item names treated as usable healing potions.
POTION_ITEMS = ("Health Potion", "Greater Potion")


class Player(Combatant):
    """The hero. Built from a class definition loaded from content."""

    def __init__(self, name, class_id, class_def, content):
        super().__init__()
        self.name = name
        self.class_id = class_id
        self.class_name = class_def["name"]
        self.level = 1
        self.max_hp = class_def["max_hp"]
        self.hp = self.max_hp
        self.attack = class_def["attack"]
        self.defense = class_def["defense"]
        self.max_stamina = class_def["max_stamina"]
        self.stamina = self.max_stamina
        self.gold = STARTING_GOLD
        self.xp = 0
        self.xp_to_level = STARTING_XP_TO_LEVEL
        self.consumables = list(class_def["inventory"])
        self.equipment = {}
        self.abilities = list(class_def["abilities"])
        starter = class_def["weapon"]
        self.equip_weapon(make_weapon(content, starter["components"], starter["name"]))
        self.hp = self.max_hp
        self.stamina = self.max_stamina

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def restore_stamina(self, amount):
        self.stamina = min(self.max_stamina, self.stamina + amount)

    def equip_weapon(self, weapon):
        """Equip ``weapon``, replacing any current one, and apply its stat bonuses."""
        self.unequip_weapon()
        self.equipment["weapon"] = weapon
        for stat, amount in weapon.stats.items():
            setattr(self, stat, getattr(self, stat) + amount)

    def unequip_weapon(self):
        """Remove and return the equipped weapon, undoing its stat bonuses."""
        weapon = self.equipment.pop("weapon", None)
        if weapon is not None:
            for stat, amount in weapon.stats.items():
                setattr(self, stat, getattr(self, stat) - amount)
            self.hp = min(self.hp, self.max_hp)
            self.stamina = min(self.stamina, self.max_stamina)
        return weapon

    def gain_xp(self, amount):
        """Add XP and advance levels. Returns the number of levels gained.

        Stat gains are applied separately via ``apply_level_up`` so the
        player chooses a boon for each level earned.
        """
        self.xp += amount
        levels = 0
        while self.xp >= self.xp_to_level:
            self.xp -= self.xp_to_level
            self.level += 1
            self.xp_to_level = int(self.xp_to_level * LEVEL_XP_GROWTH)
            levels += 1
        return levels

    def apply_level_up(self, boon_id):
        """Apply one level's baseline gains plus the chosen boon.

        Restores HP and stamina to full, as a level-up always has.
        """
        gains = dict(LEVEL_BASELINE)
        for stat, amount in LEVEL_BOONS[boon_id]["gains"].items():
            gains[stat] += amount
        self.max_hp += gains["max_hp"]
        self.attack += gains["attack"]
        self.defense += gains["defense"]
        self.max_stamina += gains["max_stamina"]
        self.hp = self.max_hp
        self.stamina = self.max_stamina

    def potion_count(self):
        return sum(self.consumables.count(name) for name in POTION_ITEMS)

    def to_dict(self):
        """Serialize to a plain dict for saving."""
        equipment = {}
        if "weapon" in self.equipment:
            equipment["weapon"] = self.equipment["weapon"].to_dict()
        return {
            "name": self.name,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "level": self.level,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "attack": self.attack,
            "defense": self.defense,
            "stamina": self.stamina,
            "max_stamina": self.max_stamina,
            "gold": self.gold,
            "xp": self.xp,
            "xp_to_level": self.xp_to_level,
            "consumables": list(self.consumables),
            "equipment": equipment,
            "abilities": list(self.abilities),
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a Player from a saved dict."""
        player = cls.__new__(cls)
        Combatant.__init__(player)
        player.name = data["name"]
        player.class_id = data["class_id"]
        player.class_name = data["class_name"]
        player.level = data["level"]
        player.hp = data["hp"]
        player.max_hp = data["max_hp"]
        player.attack = data["attack"]
        player.defense = data["defense"]
        player.stamina = data["stamina"]
        player.max_stamina = data["max_stamina"]
        player.gold = data["gold"]
        player.xp = data["xp"]
        player.xp_to_level = data["xp_to_level"]
        player.consumables = list(data["consumables"])
        player.equipment = {}
        if "weapon" in data["equipment"]:
            player.equipment["weapon"] = Weapon.from_dict(data["equipment"]["weapon"])
        player.abilities = list(data["abilities"])
        return player

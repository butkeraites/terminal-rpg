"""The player character and its progression logic."""
from .combatant import Combatant

STARTING_GOLD = 50
STARTING_XP_TO_LEVEL = 100
LEVEL_XP_GROWTH = 1.5

# Stat gains applied on each level-up.
LEVEL_HP_GAIN = 20
LEVEL_ATTACK_GAIN = 5
LEVEL_DEFENSE_GAIN = 2
LEVEL_STAMINA_GAIN = 2

# Inventory item names treated as usable healing potions.
POTION_ITEMS = ("Health Potion", "Greater Potion")


class Player(Combatant):
    """The hero. Built from a class definition loaded from content."""

    def __init__(self, name, class_id, class_def):
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
        self.inventory = list(class_def["inventory"])
        self.abilities = list(class_def["abilities"])

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def restore_stamina(self, amount):
        self.stamina = min(self.max_stamina, self.stamina + amount)

    def gain_xp(self, amount):
        """Add XP, leveling up repeatedly while enough XP has accrued."""
        self.xp += amount
        leveled = False
        while self.xp >= self.xp_to_level:
            self.level_up()
            leveled = True
        return leveled

    def level_up(self):
        self.level += 1
        self.xp -= self.xp_to_level
        self.xp_to_level = int(self.xp_to_level * LEVEL_XP_GROWTH)
        self.max_hp += LEVEL_HP_GAIN
        self.attack += LEVEL_ATTACK_GAIN
        self.defense += LEVEL_DEFENSE_GAIN
        self.max_stamina += LEVEL_STAMINA_GAIN
        self.hp = self.max_hp
        self.stamina = self.max_stamina

    def potion_count(self):
        return sum(self.inventory.count(name) for name in POTION_ITEMS)

    def to_dict(self):
        """Serialize to a plain dict for saving."""
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
            "inventory": list(self.inventory),
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
        player.inventory = list(data["inventory"])
        player.abilities = list(data["abilities"])
        return player

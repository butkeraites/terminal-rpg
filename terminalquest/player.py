"""The player character and its progression logic."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from .accessory import Accessory
from .armor import Armor
from .combatant import Combatant
from .companion import Companion
from .hireling import Hireling
from .pet import Pet
from .weapon import Weapon, make_weapon

if TYPE_CHECKING:
    from .content import Content

STARTING_GOLD = 50
STARTING_XP_TO_LEVEL = 100
LEVEL_XP_GROWTH = 1.5

# Every level-up grants this baseline, plus one player-chosen boon.
LEVEL_BASELINE = {"max_hp": 10, "attack": 2, "defense": 1, "max_stamina": 1}

LEVEL_BOONS: dict[str, dict[str, Any]] = {
    "vigor": {"name": "Vigor", "blurb": "+25 Max HP", "gains": {"max_hp": 25}},
    "might": {"name": "Might", "blurb": "+7 Attack", "gains": {"attack": 7}},
    "bulwark": {"name": "Bulwark", "blurb": "+4 Defense, +3 Stamina",
                "gains": {"defense": 4, "max_stamina": 3}},
}

# Inventory item names treated as usable healing potions (HUD potion counter).
POTION_ITEMS = ("Health Potion", "Greater Potion", "Sovereign Potion",
                "Pall-Drinker", "Warrior's Breath", "Rogue's Vial",
                "Mage's Crystal", "Ranger's Tonic", "Cleric's Wafer",
                "the Last Bread")


class Player(Combatant):
    """The hero. Built from a class definition loaded from content."""

    class_id: str
    class_name: str
    level: int
    max_stamina: int
    stamina: int
    crit_bonus: float
    dodge_chance: float
    gold: int
    xp: int
    xp_to_level: int
    consumables: list[str]
    equipment: dict[str, Any]
    abilities: list[str]
    companion: Companion | None
    hireling: Hireling | None
    trophies: dict[str, int]
    marks: list[str]
    run_id: str

    def __init__(
        self,
        name: str,
        class_id: str,
        class_def: dict[str, Any],
        content: Content,
    ) -> None:
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
        self.crit_bonus = 0.0  # weapon upgrades (e.g. Sharpened) raise this
        self.dodge_chance = 0.0  # armor pieces raise this
        self.gold = STARTING_GOLD
        self.xp = 0
        self.xp_to_level = STARTING_XP_TO_LEVEL
        self.consumables = list(class_def["inventory"])
        self.equipment = {}
        self.abilities = list(class_def["abilities"])
        self.companion = None  # bought once at Gravewatch; persists for the run
        self.hireling = None   # paid combat ally; can die and stays dead this run
        self.trophies = {}  # enemy-drop bag — keys map to entries in enemies.json
        # v1.51 — irreversible per-character events from the Marks system.
        # Each fired mark id is recorded here and in a sidecar file keyed by
        # run_id, so reloading an older save still re-applies fired marks.
        self.marks = []
        self.run_id = uuid.uuid4().hex[:12]
        starter = class_def["weapon"]
        self.equip_weapon(make_weapon(content, starter["components"], starter["name"]))
        self.hp = self.max_hp
        self.stamina = self.max_stamina

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def restore_stamina(self, amount: int) -> None:
        self.stamina = min(self.max_stamina, self.stamina + amount)

    def equip_weapon(self, weapon: Weapon) -> None:
        """Equip ``weapon``, replacing any current one, and apply its stat bonuses.

        The weapon's component-stats and its one-time upgrade bonus are both
        applied. Re-applying an upgrade (via re-equip) is a no-op because
        ``upgrade_stat_bonus`` keys are added once per equip.
        """
        self.unequip_weapon()
        self.equipment["weapon"] = weapon
        for stat, amount in weapon.stats.items():
            setattr(self, stat, getattr(self, stat) + amount)
        for stat, amount in weapon.upgrade_stat_bonus().items():
            setattr(self, stat, getattr(self, stat) + amount)

    def unequip_weapon(self) -> Weapon | None:
        """Remove and return the equipped weapon, undoing its stat bonuses."""
        weapon = self.equipment.pop("weapon", None)
        if weapon is not None:
            for stat, amount in weapon.stats.items():
                setattr(self, stat, getattr(self, stat) - amount)
            for stat, amount in weapon.upgrade_stat_bonus().items():
                setattr(self, stat, getattr(self, stat) - amount)
            self.hp = min(self.hp, self.max_hp)
            self.stamina = min(self.stamina, self.max_stamina)
        return weapon

    def equip_armor(self, armor: Armor) -> None:
        """Equip ``armor``, replacing any current piece, and apply its bonuses."""
        self.unequip_armor()
        self.equipment["armor"] = armor
        for stat, amount in armor.stats.items():
            setattr(self, stat, getattr(self, stat) + amount)
        self.dodge_chance += armor.dodge_chance

    def unequip_armor(self) -> Armor | None:
        """Remove and return the equipped armor, undoing its bonuses."""
        armor = self.equipment.pop("armor", None)
        if armor is not None:
            for stat, amount in armor.stats.items():
                setattr(self, stat, getattr(self, stat) - amount)
            self.dodge_chance -= armor.dodge_chance
            self.hp = min(self.hp, self.max_hp)
        return armor

    def equip_accessory(self, accessory: Accessory) -> None:
        """Equip a trinket or ring in its slot, applying its bonuses."""
        self.unequip_accessory(accessory.slot)
        self.equipment[accessory.slot] = accessory
        for stat, amount in accessory.stats.items():
            setattr(self, stat, getattr(self, stat) + amount)

    def unequip_accessory(self, slot: str) -> Accessory | None:
        """Remove and return the accessory in ``slot`` (trinket|ring), undoing its bonuses."""
        accessory = self.equipment.pop(slot, None)
        if accessory is not None:
            for stat, amount in accessory.stats.items():
                setattr(self, stat, getattr(self, stat) - amount)
            self.hp = min(self.hp, self.max_hp)
            self.stamina = min(self.stamina, self.max_stamina)
        return accessory

    def equip_pet(self, pet: Pet) -> None:
        """Equip a pet (a 5th equipment slot), applying its passive bonuses.

        Pets behave like accessories — stat contributions are tracked here
        and removed on unequip. The per-round regen is read from the equipped
        pet directly during combat.
        """
        self.unequip_pet()
        self.equipment["pet"] = pet
        for stat, amount in pet.stats.items():
            setattr(self, stat, getattr(self, stat) + amount)

    def unequip_pet(self) -> Pet | None:
        """Remove and return the equipped pet, undoing its bonuses."""
        pet = self.equipment.pop("pet", None)
        if pet is not None:
            for stat, amount in pet.stats.items():
                setattr(self, stat, getattr(self, stat) - amount)
            self.hp = min(self.hp, self.max_hp)
            self.stamina = min(self.stamina, self.max_stamina)
        return pet

    def gain_xp(self, amount: int) -> int:
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

    def apply_baseline(self) -> None:
        """Apply one level's baseline stat gains. Restores HP and stamina."""
        self.max_hp += LEVEL_BASELINE["max_hp"]
        self.attack += LEVEL_BASELINE["attack"]
        self.defense += LEVEL_BASELINE["defense"]
        self.max_stamina += LEVEL_BASELINE["max_stamina"]
        self.hp = self.max_hp
        self.stamina = self.max_stamina

    def apply_boon(self, boon_id: str) -> None:
        """Apply one level-up boon's bonus stat gains. Restores HP and stamina."""
        for stat, amount in LEVEL_BOONS[boon_id]["gains"].items():
            if stat == "max_hp":
                self.max_hp += amount
            elif stat == "attack":
                self.attack += amount
            elif stat == "defense":
                self.defense += amount
            elif stat == "max_stamina":
                self.max_stamina += amount
        self.hp = self.max_hp
        self.stamina = self.max_stamina

    def apply_level_up(self, boon_id: str) -> None:
        """Apply one level's baseline gains plus the chosen boon.

        Restores HP and stamina to full, as a level-up always has.
        """
        self.apply_baseline()
        self.apply_boon(boon_id)

    def learn_ability(self, ability_id: str) -> None:
        """Add a new ability to the player's known list (no-op if already known)."""
        if ability_id not in self.abilities:
            self.abilities.append(ability_id)

    def learnable_abilities(self, content: Content) -> list[str]:
        """Ability ids the player has unlocked by level but has not yet learned."""
        progression = content.classes[self.class_id].get("progression", [])
        return [entry["ability"] for entry in progression
                if entry["level"] <= self.level and entry["ability"] not in self.abilities]

    def potion_count(self) -> int:
        return sum(self.consumables.count(name) for name in POTION_ITEMS)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for saving."""
        equipment = {}
        if "weapon" in self.equipment:
            equipment["weapon"] = self.equipment["weapon"].to_dict()
        if "armor" in self.equipment:
            equipment["armor"] = self.equipment["armor"].to_dict()
        for slot in ("trinket", "ring"):
            if slot in self.equipment:
                equipment[slot] = self.equipment[slot].to_dict()
        if "pet" in self.equipment:
            equipment["pet"] = self.equipment["pet"].to_dict()
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
            "crit_bonus": self.crit_bonus,
            "dodge_chance": self.dodge_chance,
            "gold": self.gold,
            "xp": self.xp,
            "xp_to_level": self.xp_to_level,
            "consumables": list(self.consumables),
            "equipment": equipment,
            "abilities": list(self.abilities),
            "companion": self.companion.to_dict() if self.companion else None,
            "hireling": self.hireling.to_dict() if self.hireling else None,
            "trophies": dict(self.trophies),
            "marks": list(self.marks),
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Player:
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
        player.crit_bonus = data.get("crit_bonus", 0.0)  # older saves lack this
        player.dodge_chance = data.get("dodge_chance", 0.0)
        player.gold = data["gold"]
        player.xp = data["xp"]
        player.xp_to_level = data["xp_to_level"]
        player.consumables = list(data["consumables"])
        player.equipment = {}
        if "weapon" in data["equipment"]:
            player.equipment["weapon"] = Weapon.from_dict(data["equipment"]["weapon"])
        if "armor" in data["equipment"]:
            player.equipment["armor"] = Armor.from_dict(data["equipment"]["armor"])
        for slot in ("trinket", "ring"):
            if slot in data["equipment"]:
                player.equipment[slot] = Accessory.from_dict(data["equipment"][slot])
        if "pet" in data["equipment"]:
            player.equipment["pet"] = Pet.from_dict(data["equipment"]["pet"])
        player.abilities = list(data["abilities"])
        comp_data = data.get("companion")
        player.companion = Companion.from_dict(comp_data) if comp_data else None
        hire_data = data.get("hireling")
        player.hireling = Hireling.from_dict(hire_data) if hire_data else None
        player.trophies = dict(data.get("trophies", {}))
        # v1.51 — restore marks list and run_id (older saves lack both).
        player.marks = list(data.get("marks", []))
        player.run_id = data.get("run_id") or uuid.uuid4().hex[:12]
        return player

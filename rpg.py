#!/usr/bin/env python3
import random
import time
import sys

class Player:
    def __init__(self, name):
        self.name = name
        self.level = 1
        self.hp = 100
        self.max_hp = 100
        self.attack = 10
        self.defense = 5
        self.gold = 50
        self.xp = 0
        self.xp_to_level = 100
        self.inventory = ["Health Potion", "Health Potion"]
        self.position = "village"
    
    def take_damage(self, damage):
        actual_damage = max(1, damage - self.defense)
        self.hp -= actual_damage
        return actual_damage
    
    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)
    
    def gain_xp(self, amount):
        self.xp += amount
        if self.xp >= self.xp_to_level:
            self.level_up()
    
    def level_up(self):
        self.level += 1
        self.xp -= self.xp_to_level
        self.xp_to_level = int(self.xp_to_level * 1.5)
        self.max_hp += 20
        self.hp = self.max_hp
        self.attack += 5
        self.defense += 2
        print(f"\n🎉 LEVEL UP! You are now level {self.level}!")
        print(f"HP: {self.max_hp} | Attack: {self.attack} | Defense: {self.defense}")
        time.sleep(2)

class Enemy:
    def __init__(self, name, hp, attack, defense, xp_reward, gold_reward):
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.attack = attack
        self.defense = defense
        self.xp_reward = xp_reward
        self.gold_reward = gold_reward
    
    def take_damage(self, damage):
        actual_damage = max(1, damage - self.defense)
        self.hp -= actual_damage
        return actual_damage

def print_slow(text, delay=0.03):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def clear_screen():
    print("\n" * 2)

def show_stats(player):
    print("\n" + "="*50)
    print(f"⚔️  {player.name} | Level {player.level}")
    print(f"❤️  HP: {player.hp}/{player.max_hp}")
    print(f"⚔️  Attack: {player.attack} | 🛡️  Defense: {player.defense}")
    print(f"✨ XP: {player.xp}/{player.xp_to_level} | 💰 Gold: {player.gold}")
    print("="*50 + "\n")

def combat(player, enemy):
    print_slow(f"\n⚔️  A wild {enemy.name} appears!")
    print(f"HP: {enemy.hp} | Attack: {enemy.attack}\n")
    time.sleep(1)
    
    while player.hp > 0 and enemy.hp > 0:
        print(f"\n{player.name}: {player.hp}/{player.max_hp} HP")
        print(f"{enemy.name}: {enemy.hp}/{enemy.max_hp} HP\n")
        
        print("1. Attack")
        print("2. Use Potion")
        print("3. Run Away")
        
        choice = input("\nWhat do you do? ").strip()
        
        if choice == "1":
            damage = player.attack + random.randint(-2, 5)
            actual_damage = enemy.take_damage(damage)
            print(f"\n💥 You deal {actual_damage} damage to {enemy.name}!")
            time.sleep(1)
            
            if enemy.hp <= 0:
                print_slow(f"\n🎉 You defeated {enemy.name}!")
                player.gain_xp(enemy.xp_reward)
                player.gold += enemy.gold_reward
                print(f"Gained {enemy.xp_reward} XP and {enemy.gold_reward} gold!")
                time.sleep(2)
                return True
            
            enemy_damage = enemy.attack + random.randint(-2, 3)
            actual_damage = player.take_damage(enemy_damage)
            print(f"💢 {enemy.name} deals {actual_damage} damage to you!")
            time.sleep(1)
            
        elif choice == "2":
            if "Health Potion" in player.inventory:
                player.inventory.remove("Health Potion")
                heal_amount = 40
                player.heal(heal_amount)
                print(f"\n💚 You used a Health Potion and restored {heal_amount} HP!")
                print(f"Current HP: {player.hp}/{player.max_hp}")
                time.sleep(1)
            else:
                print("\n❌ You don't have any potions!")
                continue
                
        elif choice == "3":
            if random.random() < 0.5:
                print("\n🏃 You successfully ran away!")
                time.sleep(1)
                return False
            else:
                print("\n❌ Couldn't escape!")
                enemy_damage = enemy.attack + random.randint(-2, 3)
                actual_damage = player.take_damage(enemy_damage)
                print(f"💢 {enemy.name} deals {actual_damage} damage to you!")
                time.sleep(1)
        else:
            print("\n❌ Invalid choice!")
            continue
    
    if player.hp <= 0:
        return False
    
    return True

def village(player):
    clear_screen()
    print_slow("🏘️  Welcome to the Village")
    print("\nA peaceful place with a shop and an inn.\n")
    
    while True:
        print("1. Visit Shop")
        print("2. Rest at Inn (20 gold)")
        print("3. View Stats")
        print("4. Leave Village")
        
        choice = input("\nWhat do you do? ").strip()
        
        if choice == "1":
            shop(player)
        elif choice == "2":
            if player.gold >= 20:
                player.gold -= 20
                player.hp = player.max_hp
                print("\n😴 You rest at the inn and restore all HP!")
                time.sleep(1)
            else:
                print("\n❌ Not enough gold!")
        elif choice == "3":
            show_stats(player)
        elif choice == "4":
            player.position = "world"
            break
        else:
            print("\n❌ Invalid choice!")

def shop(player):
    clear_screen()
    print_slow("🏪 Welcome to the Shop!\n")
    
    while True:
        print(f"Your gold: {player.gold}")
        print("\n1. Health Potion (30 gold)")
        print("2. Upgrade Attack (+5 attack, 100 gold)")
        print("3. Upgrade Defense (+3 defense, 80 gold)")
        print("4. Leave Shop")
        
        choice = input("\nWhat would you like? ").strip()
        
        if choice == "1":
            if player.gold >= 30:
                player.gold -= 30
                player.inventory.append("Health Potion")
                print("\n✅ Bought Health Potion!")
            else:
                print("\n❌ Not enough gold!")
        elif choice == "2":
            if player.gold >= 100:
                player.gold -= 100
                player.attack += 5
                print(f"\n✅ Attack increased to {player.attack}!")
            else:
                print("\n❌ Not enough gold!")
        elif choice == "3":
            if player.gold >= 80:
                player.gold -= 80
                player.defense += 3
                print(f"\n✅ Defense increased to {player.defense}!")
            else:
                print("\n❌ Not enough gold!")
        elif choice == "4":
            break
        else:
            print("\n❌ Invalid choice!")
        
        time.sleep(1)

def forest(player):
    clear_screen()
    print_slow("🌲 You enter the Dark Forest...")
    print("Strange sounds echo through the trees.\n")
    time.sleep(1)
    
    enemies = [
        Enemy("Goblin", 30, 8, 2, 30, 15),
        Enemy("Wolf", 25, 12, 1, 25, 10),
        Enemy("Bandit", 40, 10, 3, 40, 25)
    ]
    
    enemy = random.choice(enemies)
    if combat(player, enemy):
        if player.hp > 0:
            player.position = "world"
    else:
        player.position = "world"

def cave(player):
    clear_screen()
    print_slow("🕳️  You enter a dark cave...")
    print("You can barely see anything.\n")
    time.sleep(1)
    
    enemies = [
        Enemy("Giant Bat", 35, 15, 2, 50, 30),
        Enemy("Cave Troll", 60, 12, 5, 70, 40),
        Enemy("Dark Slime", 40, 10, 1, 45, 20)
    ]
    
    enemy = random.choice(enemies)
    if combat(player, enemy):
        if player.hp > 0:
            player.position = "world"
    else:
        player.position = "world"

def mountain(player):
    clear_screen()
    print_slow("⛰️  You climb the treacherous mountain...")
    print("The air grows thin and cold.\n")
    time.sleep(1)
    
    enemies = [
        Enemy("Mountain Ogre", 80, 18, 6, 100, 60),
        Enemy("Ice Wraith", 50, 20, 3, 80, 45),
        Enemy("Stone Golem", 100, 15, 10, 120, 70)
    ]
    
    enemy = random.choice(enemies)
    if combat(player, enemy):
        if player.hp > 0:
            player.position = "world"
    else:
        player.position = "world"

def world_map(player):
    clear_screen()
    print_slow("🗺️  World Map\n")
    
    while player.hp > 0:
        print(f"\nCurrent Location: Crossroads")
        print(f"HP: {player.hp}/{player.max_hp} | Gold: {player.gold}")
        print(f"Inventory: {len([i for i in player.inventory if i == 'Health Potion'])} Health Potions\n")
        
        print("1. Return to Village")
        print("2. Explore Dark Forest")
        print("3. Enter Cave")
        print("4. Climb Mountain")
        print("5. View Stats")
        print("6. Quit Game")
        
        choice = input("\nWhere do you want to go? ").strip()
        
        if choice == "1":
            village(player)
        elif choice == "2":
            forest(player)
        elif choice == "3":
            cave(player)
        elif choice == "4":
            mountain(player)
        elif choice == "5":
            show_stats(player)
        elif choice == "6":
            print("\n👋 Thanks for playing!")
            return
        else:
            print("\n❌ Invalid choice!")
        
        if player.hp <= 0:
            break
    
    if player.hp <= 0:
        clear_screen()
        print_slow("💀 You have been defeated...")
        print(f"\nFinal Stats:")
        print(f"Level: {player.level}")
        print(f"Gold Earned: {player.gold}")
        print("\nGame Over!")

def main():
    clear_screen()
    print_slow("="*50)
    print_slow("⚔️  TERMINAL QUEST ⚔️", delay=0.05)
    print_slow("="*50)
    print()
    
    name = input("Enter your hero's name: ").strip()
    if not name:
        name = "Hero"
    
    player = Player(name)
    
    clear_screen()
    print_slow(f"Welcome, {player.name}!")
    print_slow("Your adventure begins...\n")
    time.sleep(2)
    
    world_map(player)

if __name__ == "__main__":
    main()

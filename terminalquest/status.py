"""Status effects shared by every combatant.

A combatant stores active effects as ``{effect_name: turns_remaining}``.
Damage-over-time effects deal flat damage that ignores defense.
"""

# Flat damage dealt per turn by each damage-over-time effect.
DOT_DAMAGE = {"poison": 5, "burn": 7, "bleed": 6}

# Effects that exist but deal no direct damage.
_MODIFIERS = {"stun", "weak", "vulnerable", "braced", "evasive"}

ALL_EFFECTS = set(DOT_DAMAGE) | _MODIFIERS

# One-line player-facing explanations for the non-damage effects.
_MODIFIER_HELP = {
    "stun": "loses its next turn",
    "weak": "deals 40% less attack damage",
    "vulnerable": "takes 30% more damage",
    "braced": "takes 50% less damage from the next hit",
    "evasive": "has a 50% chance to dodge attacks",
}

_EMOJI = {
    "poison": "🟢",
    "burn": "🔥",
    "bleed": "🩸",
    "stun": "💫",
    "weak": "⬇️",
    "vulnerable": "🎯",
    "braced": "🛡️",
    "evasive": "💨",
}


def apply_status(entity, name, turns):
    """Add or refresh a status effect, keeping the longer remaining duration."""
    if name not in ALL_EFFECTS:
        raise ValueError(f"unknown status effect '{name}'")
    entity.statuses[name] = max(entity.statuses.get(name, 0), turns)


def has_status(entity, name):
    return entity.statuses.get(name, 0) > 0


def tick_statuses(entity):
    """Apply damage-over-time, decrement timers, drop expired effects.

    Returns ``(total_damage, messages)``. Does not subtract HP itself —
    callers apply the returned damage so they can report a death.
    """
    total_damage = 0
    messages = []
    for name in list(entity.statuses):
        if name in DOT_DAMAGE:
            dmg = DOT_DAMAGE[name]
            total_damage += dmg
            messages.append(f"{_EMOJI[name]} {entity.name} suffers {dmg} {name} damage!")
        entity.statuses[name] -= 1
        if entity.statuses[name] <= 0:
            del entity.statuses[name]
    return total_damage, messages


def attack_multiplier(entity):
    """Outgoing-damage multiplier from the attacker's own effects."""
    return 0.6 if has_status(entity, "weak") else 1.0


def damage_taken_multiplier(entity):
    """Incoming-damage multiplier from the defender's own effects."""
    mult = 1.0
    if has_status(entity, "vulnerable"):
        mult *= 1.3
    if has_status(entity, "braced"):
        mult *= 0.5
    return mult


def describe(entity):
    """Return a short human-readable summary of active effects, or ''."""
    if not entity.statuses:
        return ""
    parts = [f"{_EMOJI.get(n, '')}{n}({t})" for n, t in entity.statuses.items()]
    return " ".join(parts)


def glossary():
    """Return the status-effect glossary as a list of display lines."""
    lines = [f"{_EMOJI[name]} {name} — takes {dmg} damage each turn"
             for name, dmg in DOT_DAMAGE.items()]
    lines += [f"{_EMOJI[name]} {name} — {desc}"
              for name, desc in _MODIFIER_HELP.items()]
    return lines

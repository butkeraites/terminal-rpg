"""The central run-state object.

``GameState`` bundles everything a running game needs: the player, the
loaded content, the IO channel, the RNG, the current location, and a
``flags`` dict reserved for future quest/world state. It is the unit of
save/load — ``player``, ``current_location`` and ``flags`` are persisted;
``content``, ``io`` and ``rng`` are runtime-injected and never serialized.
"""
from . import chronicle
from .player import Player


class GameState:
    """Mutable state for a single playthrough."""

    def __init__(self, player, content, io, rng,
                 current_location="crossroads", flags=None, chronicle_dir=None):
        self.player = player
        self.content = content
        self.io = io
        self.rng = rng
        self.current_location = current_location
        self.flags = flags if flags is not None else {}
        # Where the cross-run Chronicle lives; not part of the save.
        self.chronicle_dir = chronicle_dir or chronicle.DEFAULT_DIR

    def to_dict(self):
        """Serialize the persistable fields to a plain dict."""
        return {
            "current_location": self.current_location,
            "flags": dict(self.flags),
            "player": self.player.to_dict(),
        }

    @classmethod
    def from_dict(cls, data, content, io, rng):
        """Rebuild a GameState from a saved dict plus the runtime environment."""
        return cls(
            Player.from_dict(data["player"]),
            content, io, rng,
            current_location=data["current_location"],
            flags=dict(data.get("flags", {})),
        )

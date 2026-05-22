"""The central run-state object.

``GameState`` bundles everything a running game needs: the player, the
loaded content, the IO channel, the RNG, the current location, and a
``flags`` dict reserved for future quest/world state. It is the unit of
save/load — ``player``, ``current_location``, ``flags`` and the run
``seed`` are persisted; ``content``, ``io``, ``rng`` and ``audio`` are
runtime-injected.
"""
from . import chronicle
from .audio import AudioEngine
from .player import Player


class GameState:
    """Mutable state for a single playthrough."""

    def __init__(self, player, content, io, rng,
                 current_location="crossroads", flags=None, chronicle_dir=None,
                 seed=None, audio=None):
        self.player = player
        self.content = content
        self.io = io
        self.rng = rng
        self.current_location = current_location
        self.flags = flags if flags is not None else {}
        # Where the cross-run Chronicle lives; not part of the save.
        self.chronicle_dir = chronicle_dir or chronicle.DEFAULT_DIR
        # The run's RNG seed — surfaced to the player and recorded.
        self.seed = seed
        # Ambient audio. A disabled engine is a perfect no-op, so callers
        # can always safely do ``state.audio.play_zone(...)`` without
        # checking — tests and headless runs land on the disabled default.
        self.audio = audio if audio is not None else AudioEngine(enabled=False)

    def to_dict(self):
        """Serialize the persistable fields to a plain dict."""
        return {
            "current_location": self.current_location,
            "flags": dict(self.flags),
            "seed": self.seed,
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
            seed=data.get("seed"),
        )

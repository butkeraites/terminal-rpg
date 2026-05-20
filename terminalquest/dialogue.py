"""Branching dialogue trees for NPCs that talk, not just trade quests.

A dialogue tree is a dict of nodes loaded from ``data/dialogues/<id>.json``:

    {
      "initial": {
        "lines": ["..."],
        "responses": [
          {"text": "Why?", "next": "why"},
          {"text": "Leave.", "next": null, "sets_flag": "atrel_offered"}
        ]
      },
      "why": {...}
    }

``run_dialogue`` walks the tree from the ``initial`` node, prints each node's
lines slowly, prompts the player to pick a response, follows ``next``, and
optionally sets a state flag on choice. ``next: null`` (or missing) ends the
conversation. Flags persist via the normal state.flags save/load.
"""


def run_dialogue(state, tree, start_node="initial"):
    """Walk a dialogue tree. Returns the id of the last node visited.

    A node may carry ``voice: "stone"`` to render its lines through the
    speaking-through-stone formatting — used by Cael in v0.12 Arc V, where
    her mouth is filled with the seal she became.
    """
    io = state.io
    current = start_node
    while current is not None:
        node = tree.get(current)
        if node is None:
            return current
        voice = node.get("voice", "normal")
        renderer = io.show_through_stone if voice == "stone" else io.show_slow
        for line in node.get("lines", []):
            renderer(line)
        responses = node.get("responses", [])
        if not responses:
            io.pause(2)
            return current
        for index, response in enumerate(responses, start=1):
            io.show(f"\n{index}. {response['text']}")
        choice = io.ask("\nWhat do you say? ")
        if not (choice.isdigit() and 1 <= int(choice) <= len(responses)):
            io.show("\n❌ Invalid choice!")
            continue
        chosen = responses[int(choice) - 1]
        if "sets_flag" in chosen:
            state.flags[chosen["sets_flag"]] = True
        # A response may also grant a consumable (e.g. the Last Bread).
        if "grants_consumable" in chosen:
            state.player.consumables.append(chosen["grants_consumable"])
        current = chosen.get("next")
    return None


def validate_tree(tree, tree_id):
    """Raise ValueError if a dialogue tree is malformed.

    Every node must have ``lines``. Every response's ``next`` must resolve
    to another node in the tree, or be None (terminal). ``initial`` must
    exist.
    """
    if "initial" not in tree:
        raise ValueError(f"dialogue '{tree_id}' has no 'initial' node")
    for node_id, node in tree.items():
        if "lines" not in node or not isinstance(node["lines"], list):
            raise ValueError(
                f"dialogue '{tree_id}' node '{node_id}' has no lines list")
        for response in node.get("responses", []):
            nxt = response.get("next")
            if nxt is not None and nxt not in tree:
                raise ValueError(
                    f"dialogue '{tree_id}' node '{node_id}' response points "
                    f"to unknown node '{nxt}'")

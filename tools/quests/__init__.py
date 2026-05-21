"""Quest-authoring tooling for the 2000-quest campaign.

Phase-2 of the quests campaign per docs/QUESTS.md. The package exposes
the ``python3 -m tools.quests`` CLI, with subcommands for validation,
listing, chain DAG inspection, Graphviz DOT export, and orphan detection.

The tool is dev-only — never imported by the shipped game.
"""

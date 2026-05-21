"""tools/quests CLI — Phase-2 of the quests campaign.

Smoke tests for each subcommand. The tool is dev-only; this test suite
keeps the surface honest as the engine grows. Tests run the CLI via
``tools.quests.__main__.main`` so they share the same content as the
running game.
"""
import io
from contextlib import redirect_stdout, redirect_stderr

from tools.quests.__main__ import main


def _run(*args):
    """Invoke the CLI and return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


def test_validate_default_subcommand_passes_on_shipped_content():
    """No args defaults to --validate; the shipped quests.json is clean."""
    code, out, _err = _run()
    assert code == 0
    assert "validated cleanly" in out


def test_validate_subcommand_explicit():
    code, out, _err = _run("--validate")
    assert code == 0
    assert "validated cleanly" in out


def test_list_subcommand_prints_every_quest():
    """--list emits every quest_id and shows its category."""
    code, out, _err = _run("--list")
    assert code == 0
    # The 6 shipped bounties should all appear.
    for qid in ("wolf_cull", "scavver_purge", "bandit_hunt",
                "drowned_thresher_quiet", "magistrate_unmade",
                "warden_hunt"):
        assert qid in out
    # Bounty header is present.
    assert "Bounty" in out


def test_chains_subcommand_runs_on_chainless_catalog():
    """--chains is graceful when no chains exist yet (the current state)."""
    code, out, _err = _run("--chains")
    assert code == 0
    # Either prints the empty-state hint or rolls cleanly with 0 heads.
    assert ("no chain links found" in out
            or "Chain heads" in out)


def test_dot_subcommand_emits_valid_graphviz():
    """--dot emits a digraph block usable by ``dot``."""
    code, out, _err = _run("--dot")
    assert code == 0
    assert out.startswith("digraph quests {")
    assert out.rstrip().endswith("}")
    # Every quest should appear as a node.
    assert '"wolf_cull"' in out


def test_orphans_subcommand_clean_on_shipped_content():
    """--orphans returns 0 (no issues) for the shipped quests.json."""
    code, out, _err = _run("--orphans")
    assert code == 0
    assert "no structural issues" in out


def test_orphans_subcommand_catches_dangling_chain_next(monkeypatch):
    """Inject a quest with chain_next → unknown id and confirm --orphans flags it.

    Uses monkeypatch on load_content so we don't write to quests.json.
    Loads normally, then mutates the in-memory dict, then re-validates by
    calling the orphan checker via the public main() function.
    """
    from terminalquest import content as content_mod
    original = content_mod.load_content

    def patched():
        c = original()
        c.quests["danglingq"] = {
            "name": "Dangling",
            "target_enemy": "wolf",
            "needed": 1,
            "reward_gold": 10,
            "cleanse_required": 0,
            "chain_next": "this_does_not_exist",
        }
        # NOTE: we skip c.validate() because the schema validator would
        # reject the dangling chain_next at load. The --orphans command
        # is the *runtime* re-check that catches issues post-load.
        return c

    monkeypatch.setattr("tools.quests.__main__.load_content", patched)
    code, out, _err = _run("--orphans")
    assert code == 1
    assert "danglingq" in out
    assert "chain_next" in out


def test_orphans_subcommand_catches_hidden_with_no_trigger(monkeypatch):
    """A hidden quest with no trigger_action is structurally broken."""
    from terminalquest import content as content_mod
    original = content_mod.load_content

    def patched():
        c = original()
        c.quests["voiceless_hidden"] = {
            "name": "Voiceless",
            "target_enemy": "wolf",
            "needed": 1,
            "reward_gold": 10,
            "cleanse_required": 0,
            "hidden": True,
            # no trigger_action — quest can never pin
        }
        return c

    monkeypatch.setattr("tools.quests.__main__.load_content", patched)
    code, out, _err = _run("--orphans")
    assert code == 1
    assert "voiceless_hidden" in out
    assert "cannot ever be pinned" in out

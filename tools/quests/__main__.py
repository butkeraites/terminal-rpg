"""``python3 -m tools.quests`` — the quest-authoring CLI.

Phase-2 of the quests campaign (docs/QUESTS.md). Five subcommands:

  --validate   re-run Content.validate() and confirm quests.json loads clean.
  --list       print every quest, its category, and its principal gates.
  --chains     print chain DAGs (heads, branches, depths) in text form.
  --dot        emit Graphviz DOT for ``dot -Tpng`` rendering of the chains.
  --orphans    list hidden quests with no possible trigger, chains with
               dangling chain_next, and any quest whose gates are
               internally unsatisfiable (e.g. requires_class for a class
               that doesn't exist).

Author quests by editing ``terminalquest/data/quests.json``; run this tool
after each round of edits to catch issues the runtime would only surface
on the player's machine.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from terminalquest.content import load_content
from terminalquest.locations import _quest_category


def cmd_validate(content):
    """Re-run Content.validate(). Already done at load — this is a smoke test."""
    try:
        content.validate()
    except ValueError as exc:
        print(f"❌ validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"✅ {len(content.quests)} quests loaded and validated cleanly.")
    return 0


def cmd_list(content):
    """Print every quest with its category and principal gates."""
    by_cat = defaultdict(list)
    for qid, q in content.quests.items():
        by_cat[_quest_category(q)].append((qid, q))
    for cat in ("bounty", "chain", "special"):
        if not by_cat[cat]:
            continue
        print(f"\n── {cat.title()} ──")
        for qid, q in by_cat[cat]:
            gates = _format_gates(q)
            tgt = q.get("target_enemy") or q.get("target_trophy") or "(condition only)"
            print(f"  {qid:30s} {q['needed']}× {tgt:25s}  {gates}")
    print(f"\nTotal: {len(content.quests)} quests.")
    return 0


def _format_gates(q):
    """Render a one-line summary of a quest's gates for the --list output."""
    bits = []
    if q.get("cleanse_required", 0) > 0:
        bits.append(f"cleanse>={q['cleanse_required']}")
    if q.get("min_level"):
        bits.append(f"lvl>={q['min_level']}")
    if q.get("requires_class"):
        bits.append(f"class={','.join(q['requires_class'])}")
    if q.get("requires_mark") or q.get("requires_marks"):
        marks = [q.get("requires_mark")] if q.get("requires_mark") else []
        marks += q.get("requires_marks") or []
        bits.append(f"marks={len(marks)}")
    if q.get("requires_quest"):
        bits.append(f"after={','.join(q['requires_quest'])}")
    if q.get("denies_quest"):
        bits.append(f"not-after={','.join(q['denies_quest'])}")
    if q.get("requires_ending"):
        bits.append(f"ending={','.join(q['requires_ending'])}")
    if q.get("requires_discovery"):
        bits.append(f"read={len(q['requires_discovery'])}")
    if q.get("hidden"):
        bits.append("hidden")
    if q.get("completion_condition"):
        bits.append(f"cond={q['completion_condition']}")
    return " ".join(f"[{b}]" for b in bits) if bits else "[free]"


def _build_chain_graph(content):
    """Return (heads, edges) for the chain DAG.

    edges: list of (parent_qid, child_qid) tuples. Edge sources come from
    BOTH requires_quest (child → parent semantics inverted: parent must
    finish first → so the parent is the upstream) and chain_next (parent's
    chain_next is the child).

    heads: quests with NO inbound requires_quest reference — chain starting
    points. A pure bounty with no chain fields is also a head (a trivial
    chain of one).
    """
    edges = set()
    referenced_as_child = set()
    for qid, q in content.quests.items():
        for prereq in (q.get("requires_quest") or []):
            edges.add((prereq, qid))
            referenced_as_child.add(qid)
        if q.get("chain_next"):
            edges.add((qid, q["chain_next"]))
            referenced_as_child.add(q["chain_next"])
    heads = [qid for qid in content.quests
             if qid not in referenced_as_child]
    return heads, sorted(edges)


def cmd_chains(content):
    """Print chain DAGs in text form, head-rooted with depths."""
    heads, edges = _build_chain_graph(content)
    children = defaultdict(list)
    for parent, child in edges:
        children[parent].append(child)

    # Only show heads that have at least one outgoing edge — pure singletons
    # (a bounty with no chain links) aren't interesting in the chain view.
    chain_heads = [h for h in heads if h in {p for p, _ in edges}]
    print(f"Chain heads (heads with downstream): {len(chain_heads)}\n")
    for head in chain_heads:
        _print_chain(head, children, depth=0, visited=set())
        print()
    if not chain_heads:
        print("(no chain links found yet — author chains by adding "
              "requires_quest or chain_next fields.)")
    return 0


def _print_chain(qid, children, depth, visited):
    """Recursive text printer for a chain DAG. Visits each qid once."""
    if qid in visited:
        print(f"{'  ' * depth}↻ {qid} (cycle / re-entry)")
        return
    visited = visited | {qid}
    print(f"{'  ' * depth}● {qid}")
    for child in children.get(qid, []):
        _print_chain(child, children, depth + 1, visited)


def cmd_dot(content):
    """Emit Graphviz DOT for ``dot -Tpng quests.dot -o quests.png``."""
    heads, edges = _build_chain_graph(content)
    print("digraph quests {")
    print("  rankdir=LR;")
    print("  node [shape=box, style=rounded];")
    # Group nodes by category for color hints.
    cat_color = {
        "bounty":  '"#e6f0ff"',
        "chain":   '"#fff4e6"',
        "special": '"#f3e6ff"',
    }
    for qid, q in content.quests.items():
        cat = _quest_category(q)
        label = q["name"].replace('"', '\\"')
        print(f'  "{qid}" [label="{label}", fillcolor={cat_color[cat]}, '
              f'style="rounded,filled"];')
    for parent, child in edges:
        print(f'  "{parent}" -> "{child}";')
    print("}")
    return 0


def cmd_orphans(content):
    """List structural issues: dangling chains, unsatisfiable gates, etc."""
    issues = []
    class_ids = set(content.classes.keys())
    mark_ids = set(content.marks.keys())
    quest_ids = set(content.quests.keys())

    for qid, q in content.quests.items():
        # 1) chain_next dangling — schema validator already catches this at
        #    load, but a re-check here is cheap and surfaces in --orphans.
        nxt = q.get("chain_next")
        if nxt and nxt not in quest_ids:
            issues.append((qid, f"chain_next → unknown quest '{nxt}'"))
        # 2) Hidden with no trigger
        if q.get("hidden") and not q.get("trigger_action"):
            issues.append((qid,
                           "hidden:true with no trigger_action — quest "
                           "cannot ever be pinned"))
        # 3) Class gate naming an unknown class
        for cls in (q.get("requires_class") or []):
            if cls not in class_ids:
                issues.append((qid, f"requires_class '{cls}' (unknown)"))
        # 4) Mark gate referencing a mark not in the pool
        if q.get("requires_mark") and q["requires_mark"] not in mark_ids:
            issues.append((qid,
                           f"requires_mark '{q['requires_mark']}' (unknown)"))
        for m in (q.get("requires_marks") or []):
            if m not in mark_ids:
                issues.append((qid, f"requires_marks contains '{m}' (unknown)"))
        # 5) Self-reference loops
        if qid in (q.get("requires_quest") or []):
            issues.append((qid, "requires_quest references itself"))

    # 6) Chain orphans: quests in requires_quest that don't exist.
    for qid, q in content.quests.items():
        for prereq in (q.get("requires_quest") or []):
            if prereq not in quest_ids:
                issues.append((qid, f"requires_quest → unknown '{prereq}'"))

    if not issues:
        print("✅ no structural issues found in "
              f"{len(content.quests)} quests.")
        return 0
    print(f"⚠ {len(issues)} structural issue(s):\n")
    for qid, msg in issues:
        print(f"  {qid:30s} {msg}")
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.quests",
        description=(
            "Quest-authoring CLI for the 2000-quest campaign. "
            "See docs/QUESTS.md."))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--validate", action="store_true",
                       help="Re-run Content.validate() and confirm load. Default.")
    group.add_argument("--list", action="store_true",
                       help="Print every quest with category and gates.")
    group.add_argument("--chains", action="store_true",
                       help="Print chain DAGs in text form.")
    group.add_argument("--dot", action="store_true",
                       help="Emit Graphviz DOT for chain rendering.")
    group.add_argument("--orphans", action="store_true",
                       help="Detect dangling chains, unsatisfiable gates, etc.")
    args = parser.parse_args(argv)

    content = load_content()  # raises on validation failure already

    if args.list:
        return cmd_list(content)
    if args.chains:
        return cmd_chains(content)
    if args.dot:
        return cmd_dot(content)
    if args.orphans:
        return cmd_orphans(content)
    # Default: --validate
    return cmd_validate(content)


if __name__ == "__main__":
    sys.exit(main())

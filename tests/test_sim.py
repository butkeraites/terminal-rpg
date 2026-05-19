"""The balance simulator runs headless and is reproducible by seed (ticket A1)."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_sim(*args):
    return subprocess.run(
        [sys.executable, "-m", "tools.sim", *args],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True)


def test_sim_runs_headless_to_completion():
    """`python3 -m tools.sim` plays the chain and reports per-class results."""
    result = _run_sim("--runs", "3", "--builds", "4")
    assert "reach" in result.stdout
    assert "win" in result.stdout
    assert "warrior" in result.stdout


def test_sim_is_reproducible_by_seed():
    """The same master seed always produces an identical report."""
    first = _run_sim("--runs", "5", "--builds", "4", "--seed", "fixed-seed")
    second = _run_sim("--runs", "5", "--builds", "4", "--seed", "fixed-seed")
    assert first.stdout.strip()
    assert first.stdout == second.stdout


def test_sim_build_sampling_reports_a_win_rate_spread():
    """A2: build-sampling reports a per-class win-rate spread and flags outliers."""
    result = _run_sim("--runs", "3", "--builds", "5")
    assert "BUILD SAMPLING" in result.stdout
    assert "degenerate" in result.stdout

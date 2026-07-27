"""T4.1 — o custo de varrer o histórico precisa caber no orçamento (Risco M5 nº 1)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))

from bench_history import measure_history  # noqa: E402


def test_benchmark_reports_git_and_scan_separately():
    """Saber qual das duas partes domina é o que decide onde otimizar, se for preciso."""
    assert set(measure_history(n_commits=100)) >= {"git_s", "scan_s", "total_s", "commits"}


def test_history_scan_of_5000_commits_stays_under_the_budget():
    """Orçamento generoso de propósito: o teste protege contra regressão de ordem de
    grandeza, não contra ruído de máquina. O número real vai para o log."""
    m = measure_history(n_commits=5000)
    assert m["total_s"] < 10.0, m

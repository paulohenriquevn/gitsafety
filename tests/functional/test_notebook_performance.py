"""T3.1 — o custo do parsing precisa caber no orçamento (Unresolved Question Q3)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))

from bench_notebook import measure_notebook  # noqa: E402


def test_benchmark_reports_both_paths():
    assert set(measure_notebook(n_cells=20)) >= {"parsed_s", "text_s", "ratio"}


def test_parsing_costs_at_most_five_times_the_text_path():
    """Acima de 5×, o ganho de localização não pagaria o custo — e o teto seria revisto."""
    m = measure_notebook(n_cells=200)
    assert m["parsed_s"] < m["text_s"] * 5, m

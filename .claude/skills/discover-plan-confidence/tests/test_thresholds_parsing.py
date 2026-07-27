"""Regression tests for threshold parsing in run_discover_plan_score.

Bug caught 2026-07-27: `rules/discover-plan-thresholds.txt` shipped in `KEY = VALUE`
format while `_parse_thresholds` splits on `|`. Nothing parsed, `bands` was empty, and
`_verdict_for` fell through to its `return "INVALID"` default — so EVERY discovery plan
scored INVALID regardless of quality, with an empty `hard_caps_triggered` list.

That empty list is itself the tell: `discover-plan-golden-rule.md § 2` states
`hard_caps_triggered` MUST be non-empty when the verdict is INVALID. A verdict of
INVALID with no triggered cap is structurally impossible, so it can only come from a
parsing failure.

No test covered the parser, which is why the defect survived. These tests close that
gap at both the unit level (the file parses) and the behavior level (a perfect score
does not yield INVALID).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from run_discover_plan_score import _parse_thresholds, _verdict_for

# Verdict tokens locked by rules/discover-plan-golden-rule.md § 5.
CANONICAL_BANDS = {
    "SHIPPABLE": 90,
    "SHIPPABLE_WITH_CAVEATS": 70,
    "NEEDS_REVISION": 50,
    "INVALID": 0,
}


@pytest.fixture(scope="module")
def project_thresholds_path(project_root: Path) -> Path:
    return project_root / ".claude" / "rules" / "discover-plan-thresholds.txt"


def test_project_thresholds_file_parses_into_non_empty_bands(project_thresholds_path: Path) -> None:
    # Arrange — the promoted per-project thresholds file.
    assert project_thresholds_path.exists(), f"missing: {project_thresholds_path}"

    # Act
    bands = _parse_thresholds(project_thresholds_path)

    # Assert — an empty dict makes every verdict INVALID.
    assert bands, (
        "no band parsed from the project thresholds file; the parser splits on '|' "
        "so entries must be written as NAME|VALUE|SUNSET|ADR_REF"
    )


def test_project_thresholds_declare_every_canonical_verdict_band(
    project_thresholds_path: Path,
) -> None:
    # Act
    bands = _parse_thresholds(project_thresholds_path)

    # Assert — token names and cut-offs both come from the golden rule.
    assert bands == CANONICAL_BANDS


def test_perfect_score_with_project_thresholds_is_shippable(
    project_thresholds_path: Path,
) -> None:
    # Arrange — a plan that passed every checker with no cap applied.
    bands = _parse_thresholds(project_thresholds_path)

    # Act
    verdict = _verdict_for(100.0, bands)

    # Assert — this is the user-visible symptom the bug produced.
    assert verdict == "SHIPPABLE"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, "SHIPPABLE"),
        (90.0, "SHIPPABLE"),
        (89.9, "SHIPPABLE_WITH_CAVEATS"),
        (70.0, "SHIPPABLE_WITH_CAVEATS"),
        (69.9, "NEEDS_REVISION"),
        (50.0, "NEEDS_REVISION"),
        (49.0, "INVALID"),
        (0.0, "INVALID"),
    ],
)
def test_every_band_boundary_maps_to_its_verdict(
    project_thresholds_path: Path, score: float, expected: str
) -> None:
    # Arrange
    bands = _parse_thresholds(project_thresholds_path)

    # Act / Assert — boundaries are inclusive on the lower edge.
    assert _verdict_for(score, bands) == expected


def test_shipped_fallback_thresholds_file_exists_and_parses(templates_dir: Path) -> None:
    """`_resolve_thresholds` falls back to this file when a project has no promoted one.

    Without it the fallback resolves to a non-existent path and the scorer raises
    FileNotFoundError instead of scoring — a crash for any project that adopts the
    skill without promoting its own thresholds.
    """
    # Arrange
    fallback = templates_dir / "discover-plan-thresholds.example.txt"

    # Assert — existence first: a missing fallback is the harder failure.
    assert fallback.exists(), f"shipped fallback missing: {fallback}"

    # Act
    bands = _parse_thresholds(fallback)

    # Assert
    assert bands == CANONICAL_BANDS

"""T3.3 — orçamento de latência da varredura.

O M1 amarra a varredura ao `git commit`, e a partir dali latência vira experiência do
usuário (`docs/PRD.md § NFR-2`). Medir agora, antes de existir a pressão do hook, cria
a linha de base contra a qual o M1 será comparado. Sem número no M0, "ficou mais
lento" no M1 é opinião.

O orçamento é **absoluto e folgado** de propósito: pega regressão de ordem de
grandeza, não ruído de máquina. Comparação relativa entre execuções é trabalho do
`cycle-analysis`, com série histórica — não deste teste.
"""

from __future__ import annotations

from benchmarks.bench_scan import build_corpus, measure
from gitsafety.scanner import scan_path

#: Orçamento declarado na Unresolved Question Q1 do plano do M0.
BUDGET_SECONDS = 5.0
CORPUS_FILES = 1000
SECRETS_EVERY = 100


def test_scanning_1000_files_stays_within_the_absolute_budget(tmp_path):
    # Arrange
    build_corpus(tmp_path, n_files=CORPUS_FILES, secrets_every=SECRETS_EVERY)

    # Act
    metrics = measure(tmp_path)

    # Assert
    assert metrics["total_s"] < BUDGET_SECONDS, f"orçamento estourado: {metrics}"


def test_benchmark_corpus_contains_the_expected_number_of_secrets(tmp_path):
    """Um benchmark que não acha nada mede travessia, não detecção.

    Sem esta asserção, uma regressão que quebrasse a detecção deixaria o benchmark
    mais RÁPIDO e o teste de orçamento passaria — o pior tipo de falso verde.
    """
    # Arrange
    build_corpus(tmp_path, n_files=CORPUS_FILES, secrets_every=SECRETS_EVERY)

    # Act
    result = scan_path(tmp_path)

    # Assert
    assert len(result.findings) == CORPUS_FILES // SECRETS_EVERY


def test_measure_reports_the_three_metrics(tmp_path):
    # Arrange
    build_corpus(tmp_path, n_files=50, secrets_every=10)

    # Act
    metrics = measure(tmp_path)

    # Assert
    assert set(metrics) == {
        "total_s",
        "per_file_ms",
        "files_per_s",
        "files_scanned",
        "findings",
    }
    assert metrics["files_per_s"] > 0


def test_corpus_is_deterministic(tmp_path):
    """Corpus aleatório tornaria o número não comparável entre execuções."""
    # Arrange
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()

    # Act
    build_corpus(a, n_files=20, secrets_every=5)
    build_corpus(b, n_files=20, secrets_every=5)

    # Assert
    conteudos_a = sorted(p.read_text() for p in sorted(a.rglob("*")) if p.is_file())
    conteudos_b = sorted(p.read_text() for p in sorted(b.rglob("*")) if p.is_file())
    assert conteudos_a == conteudos_b

"""T3.2 — orçamento de latência do hook (`docs/API.md § Superfície da CLI`).

O `NFR-2` promete que a verificação "não deve ser perceptível no fluxo normal (alvo:
< 1 s para um commit típico)". Sem medir o caminho completo — invocação do processo
incluída — a promessa é afirmação sem lastro.

O orçamento é asserido sobre o **overhead**, não sobre o tempo total: o `git commit` em
si custa o que custa, e o que prometemos é não atrapalhar.
"""

from __future__ import annotations

from benchmarks.bench_hook import measure_pair

#: `docs/API.md § Superfície da CLI`.
BUDGET_SECONDS = 1.0

#: Um commit típico toca poucas dezenas de arquivos.
TYPICAL_COMMIT_FILES = 20


def test_hook_overhead_on_a_typical_commit_is_under_one_second():
    # Arrange / Act
    metricas = measure_pair(n_files=TYPICAL_COMMIT_FILES, rounds=3)

    # Assert
    assert metricas["overhead_s"] < BUDGET_SECONDS, f"NFR-2 violado: {metricas}"


def test_measure_pair_reports_both_conditions():
    """Sem as duas medições não há overhead — só um número absoluto sem referência."""
    metricas = measure_pair(n_files=1, rounds=1)
    assert set(metricas) == {"without_hook_s", "with_hook_s", "overhead_s", "files"}


def test_overhead_does_not_explode_with_ten_times_more_files():
    """Se o overhead escalasse com o número de arquivos, a varredura dominaria.

    A hipótese do M0 é que o custo é o startup do processo, que é constante. Este teste
    é a forma falsificável dela: 10× mais arquivos não pode custar perto de 10× mais.
    """
    # Arrange / Act
    pequeno = measure_pair(n_files=20, rounds=3)
    grande = measure_pair(n_files=200, rounds=3)

    # Assert — folga generosa: o objetivo é pegar crescimento linear, não medir constante.
    assert grande["overhead_s"] < pequeno["overhead_s"] * 5

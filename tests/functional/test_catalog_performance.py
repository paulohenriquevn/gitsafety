"""T3.2 — orçamento de varredura com o catálogo completo.

O M0 mediu com **uma** regra. O motor aplica cada regra a cada linha, então o custo
poderia escalar com o número de regras — e com 53, a varredura ficaria 53× mais lenta,
levando o overhead do hook (0,04 s no M1) para perto do teto de 1 s do `NFR-2`.

Este teste guarda o orçamento; o `benchmarks/bench_catalog.py` produz a curva que decide
sobre o pré-filtro (Unresolved Question Q3 do plano).
"""

from __future__ import annotations

from benchmarks.bench_catalog import measure_with_n_rules
from benchmarks.bench_scan import build_corpus
from gitsafety.rules import BUILTIN_RULES

#: O mesmo orçamento do M0, para que a comparação entre milestones seja direta.
BUDGET_SECONDS = 5.0


def test_full_catalog_stays_within_the_scan_budget(tmp_path):
    # Arrange
    build_corpus(tmp_path, n_files=1000, secrets_every=100)

    # Act
    m = measure_with_n_rules(tmp_path, n_rules=len(BUILTIN_RULES))

    # Assert
    assert m["total_s"] < BUDGET_SECONDS, m


def test_cost_does_not_scale_linearly_with_rule_count(tmp_path):
    """A pergunta falsificável do milestone.

    Se o custo fosse linear no número de regras, 53 regras custariam ~53× uma regra e o
    pré-filtro por palavra-chave se justificaria. Se a travessia dominar, o pré-filtro é
    YAGNI. Este teste falha se a premissa mudar — por exemplo, se alguém acrescentar uma
    regra muito mais cara que as demais.
    """
    # Arrange
    build_corpus(tmp_path, n_files=500, secrets_every=100)

    # Act
    uma = measure_with_n_rules(tmp_path, n_rules=1)
    todas = measure_with_n_rules(tmp_path, n_rules=len(BUILTIN_RULES))

    # Assert — bem abaixo do crescimento linear (folga larga: o teste guarda a ordem de
    # grandeza, não um valor preciso, para não ficar flaky em CI).
    fator_regras = len(BUILTIN_RULES)
    fator_tempo = todas["total_s"] / uma["total_s"]
    assert fator_tempo < fator_regras / 4, (
        f"custo escalou {fator_tempo:.1f}× para {fator_regras}× regras — "
        f"o pré-filtro por palavra-chave precisa ser reavaliado"
    )


def test_detection_is_unchanged_by_rule_count(tmp_path):
    """Mais regras não podem mudar o que é achado no corpus do M0.

    Sem esta asserção, uma regra nova largando falso positivo no corpus passaria
    despercebida no benchmark — que mede tempo, não correção.
    """
    build_corpus(tmp_path, n_files=200, secrets_every=50)
    uma = measure_with_n_rules(tmp_path, n_rules=1)
    todas = measure_with_n_rules(tmp_path, n_rules=len(BUILTIN_RULES))
    assert uma["findings"] == todas["findings"]

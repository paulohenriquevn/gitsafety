"""T2.2 — Finding e mascaramento do segredo.

`docs/PRD.md § NFR-4` exige que o segredo apareça mascarado por padrão em toda saída:
o relatório de um detector de segredos não pode ser o próximo vazamento. O
mascaramento vive no objeto que carrega o segredo, e não no renderizador, para que
nenhum caminho de saída futuro (hook do M1, histórico do M5) possa esquecer de aplicá-lo.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from gitsafety.finding import MASK_CHAR, Finding, mask

SECRET = "AKIAIOSFODNN7EXAMPLE"  # 20 caracteres


def test_mask_preserves_head_and_tail_and_hides_the_middle():
    # Arrange / Act
    resultado = mask(SECRET)

    # Assert — 4 na frente, 4 atrás, 12 ocultos.
    assert resultado == "AKIA" + MASK_CHAR * 12 + "MPLE"


def test_masked_length_equals_original_length():
    """O comprimento não pode encolher nem crescer.

    Encolher esconderia o tamanho real; crescer confundiria quem compara com o valor
    que tem em mãos.
    """
    assert len(mask(SECRET)) == len(SECRET)


@pytest.mark.parametrize("curto", ["", "a", "AKIA", "AKIAIOSF"])
def test_mask_hides_everything_when_secret_is_too_short_to_keep_edges(curto):
    """Edge case central: segredo curto não tem miolo para ocultar.

    Preservar 4 na frente e 4 atrás de um segredo de 8 caracteres exporia o segredo
    inteiro sob aparência de estar mascarado — pior que não mascarar, porque engana.
    """
    # Act
    resultado = mask(curto)

    # Assert — nenhum caractere original sobrevive.
    assert set(resultado) <= {MASK_CHAR}
    assert len(resultado) == len(curto)


def test_mask_respects_a_custom_keep_size():
    # Act / Assert
    assert mask(SECRET, keep=2) == "AK" + MASK_CHAR * 16 + "LE"


def test_mask_with_keep_zero_hides_everything():
    # Caso negativo de parâmetro: keep=0 é pedido explícito de ocultação total.
    assert set(mask(SECRET, keep=0)) == {MASK_CHAR}


def test_finding_exposes_the_masked_secret():
    # Arrange
    finding = Finding(rule_id="aws-access-key-id", path=Path("a.py"), line=3, secret=SECRET)

    # Assert — o miolo não aparece.
    assert "IOSFODNN7EXA" not in finding.masked_secret
    assert finding.masked_secret.startswith("AKIA")


def test_finding_still_carries_the_raw_secret_for_show_secrets():
    """`--show-secrets` (PRD FR-16) precisa do valor íntegro.

    Mascarar destruindo o original tornaria a flag impossível de implementar; o
    contrato é que o mascarado seja o DEFAULT, não que o original desapareça.
    """
    finding = Finding(rule_id="aws-access-key-id", path=Path("a.py"), line=3, secret=SECRET)
    assert finding.secret == SECRET


def test_finding_is_immutable():
    """Erro tipado, não "levanta alguma coisa" (`rules/testing.md` § 4.1)."""
    finding = Finding(rule_id="r", path=Path("a.py"), line=1, secret=SECRET)
    with pytest.raises(FrozenInstanceError):
        finding.line = 2  # type: ignore[misc]


def test_finding_line_is_one_based_by_contract():
    """Linha 0 não existe em editor nenhum; aceitar 0 mascararia um off-by-one."""
    with pytest.raises(ValueError):
        Finding(rule_id="r", path=Path("a.py"), line=0, secret=SECRET)

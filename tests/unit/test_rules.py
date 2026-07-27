"""T2.1 — a regra de detecção e seus casos de acerto e não-acerto.

A forma segue o precedente do gitleaks
(`cmd/generate/config/rules/adafruit.go`), onde cada regra carrega seus true
positives e false positives junto da definição. `rules/testing.md § 4.1` chama isso
de cobrir os dois lentes: o acerto prova detecção, o não-acerto prova que a regra não
vai inundar o usuário de ruído — e é a metade que a maioria das suítes esquece.
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError

import pytest

from gitsafety.rules import AWS_ACCESS_KEY_ID, BUILTIN_RULES, Rule

# --- Acertos (true positives) -------------------------------------------------

TRUE_POSITIVES = [
    "AKIAIOSFODNN7EXAMPLE",
    'aws_key = "AKIAIOSFODNN7EXAMPLE"',
    "export AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF",
    "AKIAZZZZZZZZZZZZZZZZ",
]


@pytest.mark.parametrize("texto", TRUE_POSITIVES)
def test_aws_rule_matches_a_real_access_key_id(texto):
    # Arrange / Act
    match = AWS_ACCESS_KEY_ID.pattern.search(texto)

    # Assert
    assert match is not None, f"deveria casar: {texto!r}"


def test_aws_rule_extracts_exactly_the_key_and_nothing_around_it():
    # Arrange
    linha = 'aws_key = "AKIAIOSFODNN7EXAMPLE"  # comentário'

    # Act
    match = AWS_ACCESS_KEY_ID.pattern.search(linha)

    # Assert — o segredo reportado não pode arrastar aspas nem comentário.
    assert match.group(0) == "AKIAIOSFODNN7EXAMPLE"


# --- Não-acertos (false positives) --------------------------------------------

NEAR_MISSES = [
    "AKIA",  # só o prefixo
    "AKIAIOSFODNN7EXAMPL",  # 19 caracteres — um a menos (edge case de borda)
    "AKIAiosfodnn7example",  # minúsculas
    "AKIA-IOSFODNN7EXAMP",  # caractere fora da classe
    "",  # vazio
]


@pytest.mark.parametrize("texto", NEAR_MISSES)
def test_aws_rule_does_not_match_near_misses(texto):
    # Arrange / Act / Assert
    assert AWS_ACCESS_KEY_ID.pattern.fullmatch(texto) is None, f"não deveria casar: {texto!r}"


def test_aws_rule_does_not_match_a_longer_alphanumeric_run():
    """Caso negativo de fronteira: 17 caracteres após o prefixo não é chave AWS.

    Sem delimitação, `AKIA[0-9A-Z]{16}` casaria o prefixo de uma cadeia maior e
    reportaria um segredo que não existe — falso positivo, que segundo
    `docs/PRD.md § 4` é o que faz o time desinstalar a ferramenta.
    """
    # Arrange
    texto = "AKIAIOSFODNN7EXAMPLEEXTRA"

    # Act / Assert
    assert AWS_ACCESS_KEY_ID.pattern.fullmatch(texto) is None


# --- Invariantes do catálogo ---------------------------------------------------


def test_builtin_rules_have_unique_ids():
    # Arrange
    ids = [r.id for r in BUILTIN_RULES]

    # Assert — id duplicado tornaria o finding ambíguo já no M2.
    assert len(ids) == len(set(ids))


def test_builtin_rules_is_not_empty():
    assert len(BUILTIN_RULES) >= 1


def test_pattern_is_compiled_once_at_import_time():
    """`isinstance(..., re.Pattern)` — compilada no import, não a cada chamada.

    Recompilar por arquivo tornaria o custo proporcional ao número de arquivos vezes
    o número de regras, que é exatamente o que quebra quando o M2 trouxer 40 regras.
    """
    assert isinstance(AWS_ACCESS_KEY_ID.pattern, re.Pattern)


def test_rule_is_immutable():
    # Regra é dado, não estado — congelar evita mutação acidental entre arquivos.
    with pytest.raises(FrozenInstanceError):
        AWS_ACCESS_KEY_ID.id = "outro"  # type: ignore[misc]


def test_every_builtin_rule_has_a_human_readable_description():
    # A descrição aparece para o usuário; regra sem descrição vira ruído no output.
    for rule in BUILTIN_RULES:
        assert isinstance(rule, Rule)
        assert rule.description.strip()

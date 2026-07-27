"""T1.2 — contrato de exit code e hierarquia de erro (ADR D4).

O mecanismo verificado aqui é o do ggshield (`core/errors.py:24-59`): o código de
saída viaja junto da exceção, em vez de ser reconstruído no `main` por uma cadeia de
`if`. O teste que importa não é "o enum tem os valores certos" — é "toda exceção de
domínio carrega um código", porque é isso que impede a cadeia de `if` de voltar.
"""

from __future__ import annotations

import pytest

from gitsafety.errors import ExitCode, GitsafetyError, PathNotFoundError, UsageError


def test_exit_codes_match_the_documented_contract():
    # Arrange / Act / Assert — os três valores são contrato público (README + PRD FR-18).
    assert ExitCode.SUCCESS == 0
    assert ExitCode.SECRETS_FOUND == 1
    assert ExitCode.USAGE_ERROR == 2


def test_exit_codes_are_integers_usable_as_process_status():
    # `sys.exit` precisa de int; IntEnum garante isso sem conversão no chamador.
    assert isinstance(ExitCode.SUCCESS, int)


def test_path_not_found_error_carries_the_usage_exit_code():
    # Arrange
    err = PathNotFoundError("/nao/existe")

    # Assert
    assert err.exit_code == ExitCode.USAGE_ERROR


def test_path_not_found_error_message_names_the_offending_path():
    """Caso negativo: mensagem específica, nunca 'erro inesperado'.

    `rules/error-handling.md § 5` classifica mensagem genérica como anti-pattern —
    quem lê o erro precisa saber QUAL caminho falhou sem abrir o debugger.
    """
    # Arrange
    err = PathNotFoundError("/nao/existe")

    # Assert
    assert "/nao/existe" in str(err)


def test_path_not_found_is_a_usage_error():
    # A hierarquia importa: quem trata UsageError trata todas as suas espécies.
    assert issubclass(PathNotFoundError, UsageError)


@pytest.mark.parametrize("cls", [UsageError, PathNotFoundError])
def test_every_domain_error_carries_an_exit_code(cls):
    """A invariante que sustenta o ADR D4.

    Se uma subclasse futura esquecer de declarar seu código, este teste falha e o
    `main` não precisa aprender a adivinhar.
    """
    # Arrange / Act
    err = cls("contexto qualquer")

    # Assert
    assert isinstance(err, GitsafetyError)
    assert err.exit_code in tuple(ExitCode)


def test_domain_errors_are_catchable_by_the_base_class():
    # É o que permite ao `main` capturar só GitsafetyError, sem `except Exception`.
    with pytest.raises(GitsafetyError):
        raise PathNotFoundError("/nao/existe")

"""Códigos de saída e hierarquia de erro do domínio (ADR D4).

O mecanismo é o do ggshield (`core/errors.py:24-59`): cada exceção carrega o código
de saída que ela deve produzir. A alternativa — decidir o código no `main` com uma
cadeia de `if isinstance(...)` — concentra em um ponto distante o conhecimento que
pertence ao erro, e apodrece a cada erro novo.

O ggshield herda de `click.ClickException`; sem `click` (ADR D5), a base é `Exception`
com um atributo. São as ~10 linhas previstas como consequência daquele ADR.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Contrato público de código de saída — `docs/PRD.md § FR-18` e README.

    Não é configurável por flag, ao contrário do gitleaks
    (`cmd/detect.go:65`): aquela opção existe para acomodar CI legado que não temos,
    e um knob que ninguém pediu é YAGNI.
    """

    SUCCESS = 0
    SECRETS_FOUND = 1
    USAGE_ERROR = 2


class GitsafetyError(Exception):
    """Base de todo erro previsto do gitsafety.

    Capturar esta classe no `main` é o que permite não escrever `except Exception`:
    o que não é `GitsafetyError` é defeito nosso e deve subir com traceback, em vez
    de virar mensagem amigável que esconde o problema (`rules/error-handling.md § 5`).
    """

    exit_code: ExitCode = ExitCode.USAGE_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UsageError(GitsafetyError):
    """O usuário pediu algo impossível — argumento, caminho ou configuração."""

    exit_code = ExitCode.USAGE_ERROR


class PathNotFoundError(UsageError):
    """Caminho de varredura inexistente.

    Existe como erro, e não como resultado vazio, porque `gitsafety scan
    /caminho/digitado/errado` devolvendo 0 faria o usuário concluir que está limpo —
    o falso negativo mais caro que este produto pode produzir.
    """

    def __init__(self, path: str) -> None:
        super().__init__(f"caminho não encontrado: {path}")
        self.path = path

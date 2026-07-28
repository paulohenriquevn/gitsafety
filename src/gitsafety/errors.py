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
    """Contrato público de código de saída — `docs/API.md § Códigos de saída` e README.

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


class GitUnavailableError(UsageError):
    """O binário `git` não foi encontrado no PATH.

    Distinto de `NotAGitRepositoryError` de propósito: numa máquina sem git, dizer
    "não é um repositório git" manda a pessoa investigar o diretório quando o problema
    é a ausência do programa.
    """


class NotAGitRepositoryError(UsageError):
    """O caminho não está dentro de um repositório git."""

    def __init__(self, path: str) -> None:
        super().__init__(f"não é um repositório git: {path}")
        self.path = path


class HookExistsError(UsageError):
    """Já existe um hook de pre-commit que não é nosso.

    A mensagem carrega a linha exata a acrescentar no hook do usuário: recusar sem
    dizer como prosseguir transfere o problema em vez de resolvê-lo
    (precedente: ggshield `cmd/install.py:331-335`).
    """

    def __init__(self, path: str, line_to_add: str) -> None:
        super().__init__(
            f"já existe um hook em {path} e ele não é do gitsafety.\n"
            f"Para não destruir o seu hook, nada foi alterado.\n"
            f"Acrescente esta linha ao final dele:\n\n    {line_to_add}\n"
        )
        self.path = path
        self.line_to_add = line_to_add


class HookPathIsDirectoryError(UsageError):
    """O caminho do hook é um diretório.

    Erro próprio porque a remediação é outra: apagar um diretório é decisão do
    usuário, não algo que `install` deva sugerir junto com "acrescente esta linha".
    """

    def __init__(self, path: str) -> None:
        super().__init__(f"o caminho do hook é um diretório, não um arquivo: {path}")
        self.path = path


class CommandNotOnPathError(UsageError):
    """`gitsafety` não é resolvível no PATH (ADR D8).

    Falha na instalação em vez de no commit: o hook invoca `gitsafety` pelo PATH, e sem
    esta verificação o erro apareceria como `gitsafety: not found` do shell, no meio de
    um commit — momento em que a pessoa está fazendo outra coisa.
    """

    def __init__(self, command: str) -> None:
        super().__init__(
            f"'{command}' não foi encontrado no PATH.\n"
            f"O hook o invoca pelo PATH, então ele precisa estar acessível quando você "
            f"commitar. Ative o ambiente onde o gitsafety está instalado e tente de novo."
        )
        self.command = command


class GitCommandError(UsageError):
    """Um comando do git falhou por uma razão que não é defeito nosso.

    Existe para separar duas coisas que o `RuntimeError` confundia: um bug do gitsafety,
    que deve subir com traceback para ser corrigido, e uma condição operacional do
    ambiente — git antigo sem a flag que usamos, repositório corrompido, timeout num
    histórico enorme. A segunda é esperada, e quem a encontra precisa de uma mensagem que
    diga o que fazer, não de um stack trace (`rules/error-handling.md § 2`).
    """

    def __init__(self, comando: str, detalhe: str) -> None:
        super().__init__(f"o git falhou ao executar `{comando}`: {detalhe}")


class ConfigError(UsageError):
    """`.gitsafety.yml` inválido, ou padrão de usuário recusado.

    Erro de uso, não defeito nosso: o usuário escreveu o arquivo e é ele quem corrige.
    A mensagem precisa dizer **onde** — chave, índice e id da regra — porque `config
    inválida` sem localização manda a pessoa procurar no arquivo inteiro.
    """


class PathNotFoundError(UsageError):
    """Caminho de varredura inexistente.

    Existe como erro, e não como resultado vazio, porque `gitsafety scan
    /caminho/digitado/errado` devolvendo 0 faria o usuário concluir que está limpo —
    o falso negativo mais caro que este produto pode produzir.
    """

    def __init__(self, path: str) -> None:
        super().__init__(f"caminho não encontrado: {path}")
        self.path = path

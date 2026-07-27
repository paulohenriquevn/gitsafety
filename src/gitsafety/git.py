"""Fronteira com o binário `git` (ADR D7).

Único módulo do projeto que invoca `subprocess`. Isolar aqui evita que cada consumidor
invente seu próprio tratamento de erro do git — e é o que `rules/architecture.md § 1`
pede para infraestrutura.

**Sem abstração de propósito.** Não há `GitClient` protocolo, nem injeção de dependência:
existe um git só, não há segundo implementador previsto, e o ADR D5 decidiu testar contra
repositório real em vez de mock. Interface com um implementador único e nenhum consumidor
de teste é o anti-pattern literal de `rules/architecture.md § 6`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from gitsafety.errors import GitCommandError, GitUnavailableError, NotAGitRepositoryError

#: `git` costuma responder em milissegundos; um repositório patológico pode demorar mais.
#: O teto existe para que um git travado não pendure o commit do usuário indefinidamente.
_GIT_TIMEOUT_SEC = 120

#: Fragmentos que o git emite quando o diretório não pertence a um repositório. A
#: comparação é por substring porque a redação varia entre versões e locales do git.
_NOT_A_REPO_MARKERS = (
    "not a git repository",
    "não é um repositório git",
)


def run_git(args: Sequence[str], *, cwd: Path) -> str:
    """Executa `git <args>` em `cwd` e devolve o stdout sem espaços nas pontas.

    Traduz três modos de falha distintos, que o código óbvio confunde num só:

    - binário ausente → `GitUnavailableError`
    - fora de repositório → `NotAGitRepositoryError`
    - qualquer outra falha → `GitCommandError` com o stderr no contexto

    Usa `check=False` e inspeciona o `returncode` em vez de `check=True`: queremos
    traduzir para erro de domínio, não repassar `CalledProcessError` ao chamador.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            # `errors="replace"` pelo mesmo motivo que `scanner._read_text` (ADR D2 do M0): um
            # arquivo que não decodifica em UTF-8 não pode derrubar a varredura dos demais.
            # Sem isso, um único arquivo em latin-1 no histórico levantava `UnicodeDecodeError`
            # de dentro do `subprocess` e abortava o comando inteiro — com traceback cru, e sem
            # reportar os segredos que já haviam sido encontrados nos outros arquivos.
            errors="replace",
            check=False,
            timeout=_GIT_TIMEOUT_SEC,
        )
    except FileNotFoundError as exc:
        raise GitUnavailableError("o programa 'git' não foi encontrado no PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(
            " ".join(args),
            f"excedeu o tempo limite de {_GIT_TIMEOUT_SEC}s. Em repositório muito grande, "
            "o histórico pode levar mais que isso",
        ) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if any(marker in stderr.lower() for marker in _NOT_A_REPO_MARKERS):
            raise NotAGitRepositoryError(str(cwd))
        raise GitCommandError(" ".join(args), f"código {result.returncode}: {stderr}")

    return result.stdout.strip()


def is_git_repository(path: Path) -> bool:
    """Responde se `path` está dentro de um repositório git.

    Consulta, não asserção: devolve `False` em vez de levantar, porque quem chama quer
    decidir o que fazer. A exceção fica para quem *precisa* do repositório.
    """
    try:
        run_git(["rev-parse", "--git-dir"], cwd=path)
    except NotAGitRepositoryError:
        return False
    return True


def repo_root(path: Path) -> Path:
    """Raiz do repositório que contém `path`.

    Funciona de qualquer subdiretório — o hook roda de onde o usuário está, não da raiz.
    """
    return Path(run_git(["rev-parse", "--show-toplevel"], cwd=path))


def hooks_dir(path: Path) -> Path:
    """Diretório de hooks em vigor para o repositório.

    Usa `git rev-parse --git-path hooks` em vez de assumir `.git/hooks`: assim respeita
    `core.hooksPath` configurado pelo usuário e worktrees, onde os hooks vivem no
    diretório comum. Assumir o literal escreveria o hook num lugar que o git não lê —
    falha silenciosa, porque a instalação "funcionaria" e o commit nunca seria checado.
    """
    raw = run_git(["rev-parse", "--git-path", "hooks"], cwd=path)
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else (path / candidate)

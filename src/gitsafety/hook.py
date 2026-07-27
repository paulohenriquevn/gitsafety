"""Instalação do hook de pre-commit (ADRs D2, D3, D4, D8).

Único módulo que escreve no sistema de arquivos do usuário — e, mais delicado, no
diretório onde outras ferramentas também escrevem. Daí a disciplina: nunca sobrescrever,
sempre dizer como prosseguir, e reconhecer o próprio hook para não brigar consigo mesmo.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

from gitsafety.errors import (
    CommandNotOnPathError,
    HookExistsError,
    HookPathIsDirectoryError,
    NotAGitRepositoryError,
)
from gitsafety.git import hooks_dir, is_git_repository

#: Nome do comando que o hook invoca. O hook o resolve pelo PATH (ADR D2), e não por
#: caminho absoluto, para não amarrar a instalação a um venv que pode mudar de lugar.
COMMAND_NAME = "gitsafety"

#: A linha que o hook executa — e, ao mesmo tempo, o marcador de auto-reconhecimento
#: (ADR D4). É a própria linha de comando, não metadado à parte: um comentário
#: `# gitsafety-managed` poderia ser removido sem quebrar o hook, criando divergência
#: entre o marcador e a realidade.
HOOK_MARKER = f"{COMMAND_NAME} scan --staged"

#: Script `sh`, não Python (ADR D2). O M0 mediu 0,0145 ms por arquivo, de onde se conclui
#: que o custo dominante aqui é o startup do interpretador — que um hook em shell não paga
#: quando o git decide não executá-lo. E funciona com o venv desativado.
#:
#: O `"$@"` repassa os argumentos que o git fornece; engoli-los quebra o contrato em
#: silêncio.
HOOK_SCRIPT = f'#!/bin/sh\n{HOOK_MARKER} "$@"\n'

#: Somente o dono lê, escreve e executa. O ggshield usa `0o700` por padrão
#: (`cmd/install.py:351`) e só abre para `0o755` no modo system, onde o hook roda como
#: cada usuário que commita. Um arquivo que executa código deve alcançar o menor conjunto
#: possível de usuários.
_HOOK_MODE = stat.S_IRWXU  # 0o700


def hook_path_for(cwd: Path) -> Path:
    """Caminho do `pre-commit` no diretório de hooks em vigor.

    Delega a `git.hooks_dir`, que consulta o git em vez de assumir `.git/hooks` — assim
    respeita `core.hooksPath` e worktrees.
    """
    return hooks_dir(cwd) / "pre-commit"


def is_our_hook(path: Path) -> bool:
    """Diz se o arquivo é um hook escrito por nós.

    Responde `False` para caminho inexistente ou ilegível em vez de levantar: quem chama
    quer decidir, e um hook binário ilegível é "não é nosso", não é erro.
    """
    try:
        return path.is_file() and HOOK_MARKER in path.read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return False


def _assert_command_on_path() -> None:
    """ADR D8 — falhar na instalação, não no meio de um commit.

    Sem esta verificação o erro apareceria como `gitsafety: not found`, emitido pelo
    shell, enquanto a pessoa está tentando commitar outra coisa.
    """
    if shutil.which(COMMAND_NAME) is None:
        raise CommandNotOnPathError(COMMAND_NAME)


def install_hook(cwd: Path) -> Path:
    """Escreve o hook de pre-commit e devolve o caminho escrito.

    A ordem das verificações é a do precedente (`ggshield/cmd/install.py:328-335`) e
    importa:

    1. não é repositório git → erro;
    2. `gitsafety` fora do PATH → erro (D8);
    3. o caminho é um **diretório** → erro próprio;
    4. o arquivo existe e **é nosso** → já instalado, sai em silêncio (D4);
    5. o arquivo existe e **não é nosso** → recusa com a linha a colar (D3);
    6. caso contrário → escreve.

    Inverter (4) e (5) faz `install` repetido acusar conflito com o próprio hook,
    empurrando o usuário para um `--force` que decidimos não oferecer.
    """
    if not is_git_repository(cwd):
        raise NotAGitRepositoryError(str(cwd))

    _assert_command_on_path()

    destino = hook_path_for(cwd)

    if destino.is_dir():
        raise HookPathIsDirectoryError(str(destino))

    if destino.is_file():
        if is_our_hook(destino):
            return destino  # idempotente
        raise HookExistsError(str(destino), HOOK_MARKER + ' "$@"')

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(HOOK_SCRIPT, encoding="utf-8")
    os.chmod(destino, _HOOK_MODE)
    return destino

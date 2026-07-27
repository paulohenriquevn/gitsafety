"""Fixtures compartilhadas — repositório git temporário.

`user.email` e `user.name` são configurados **no repositório local**, nunca no global.
Configurar o global do runner é efeito colateral que vaza entre testes e altera a máquina
de quem roda a suíte (`rules/testing.md § 3` — testes independentes, sem estado
compartilhado).
"""

from __future__ import annotations

import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest


def _git(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """Repositório git isolado, pronto para receber commits."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    # Local, não global — ver docstring do módulo.
    _git(repo, "config", "user.email", "teste@exemplo.invalid")
    _git(repo, "config", "user.name", "Suite de Teste")
    return repo


@pytest.fixture
def stage(tmp_git_repo: Path):
    """Escreve um arquivo e o coloca no índice."""

    def _stage(name: str, content: str) -> Path:
        path = tmp_git_repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        _git(tmp_git_repo, "add", name)
        return path

    return _stage


@pytest.fixture
def path_with_gitsafety() -> str:
    """`PATH` que contém o console script deste ambiente.

    O hook invoca `gitsafety` pelo PATH (ADR D2). Injetar o diretório de scripts no
    ambiente do **subprocesso** — nunca no do processo de teste — é o que permite ao
    `git commit` encontrar o comando sem depender de o venv estar ativo no shell.
    """
    import os

    scripts = sysconfig.get_path("scripts")
    return f"{scripts}{os.pathsep}{os.environ.get('PATH', '')}"


@pytest.fixture
def gitsafety_on_path(monkeypatch, path_with_gitsafety: str) -> None:
    """Põe o console script no `PATH` do processo de teste.

    O ADR D8 faz `install_hook` recusar quando `gitsafety` não é resolvível — porque o
    hook o invoca pelo PATH e falhar na instalação é muito melhor que falhar no meio de
    um commit. Os testes de instalação precisam, portanto, montar essa pré-condição
    explicitamente: sem ela estariam testando o próprio D8, não o que vem depois dele.
    """
    monkeypatch.setenv("PATH", path_with_gitsafety)


@pytest.fixture
def git_commit(tmp_git_repo: Path, path_with_gitsafety: str):
    """Dispara `git commit` de verdade e devolve o exit code + a saída."""
    import os

    def _commit(message: str, *, no_verify: bool = False) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PATH"] = path_with_gitsafety
        args = ["commit", "-m", message]
        if no_verify:
            args.append("--no-verify")
        return _git(tmp_git_repo, *args, env=env)

    return _commit


@pytest.fixture(scope="session")
def console_script() -> Path:
    name = "gitsafety.exe" if sys.platform == "win32" else "gitsafety"
    return Path(sysconfig.get_path("scripts")) / name

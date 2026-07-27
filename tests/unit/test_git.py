"""T1.1 — fronteira com o binário `git` (ADR D7).

O teste que mais importa aqui é
`test_missing_git_binary_raises_git_unavailable`: confundir "git não está instalado" com
"não é um repositório git" produz, numa máquina sem git, uma mensagem que manda o usuário
procurar o problema errado. São dois modos de falha distintos e precisam de dois erros
distintos (`rules/error-handling.md § 2`).
"""

from __future__ import annotations

import subprocess

import pytest

from gitsafety.errors import ExitCode, GitUnavailableError, NotAGitRepositoryError
from gitsafety.git import hooks_dir, is_git_repository, repo_root, run_git


def test_repo_root_returns_the_repository_root(tmp_git_repo):
    # Arrange / Act / Assert — resolve() porque o git pode devolver o caminho canônico.
    assert repo_root(tmp_git_repo).resolve() == tmp_git_repo.resolve()


def test_repo_root_works_from_a_subdirectory(tmp_git_repo):
    # Edge case: o hook roda a partir de onde o usuário está, não da raiz.
    sub = tmp_git_repo / "src" / "deep"
    sub.mkdir(parents=True)
    assert repo_root(sub).resolve() == tmp_git_repo.resolve()


def test_is_git_repository_is_true_inside_a_repo(tmp_git_repo):
    assert is_git_repository(tmp_git_repo) is True


def test_is_git_repository_is_false_outside_a_repo(tmp_path):
    """Consulta, não erro: `is_git_repository` responde, não levanta."""
    assert is_git_repository(tmp_path) is False


def test_run_git_outside_a_repo_raises_not_a_git_repository(tmp_path):
    # Caso negativo: erro específico com o caminho na mensagem.
    with pytest.raises(NotAGitRepositoryError) as exc:
        run_git(["rev-parse", "--git-dir"], cwd=tmp_path)
    assert str(tmp_path) in str(exc.value)


def test_missing_git_binary_raises_git_unavailable(monkeypatch, tmp_path):
    """Caso negativo decisivo: NUNCA pode virar 'não é repositório'.

    Numa máquina sem git, dizer "não é um repositório git" manda a pessoa investigar o
    diretório quando o problema é a ausência do programa.
    """
    monkeypatch.setenv("PATH", "")
    with pytest.raises(GitUnavailableError):
        run_git(["--version"], cwd=tmp_path)


def test_run_git_returns_stdout_stripped(tmp_git_repo):
    # `config` em vez de `rev-parse HEAD`: um repositório recém-criado não tem commit
    # nenhum, então HEAD não resolve e o teste falharia pelo motivo errado.
    assert run_git(["config", "user.name"], cwd=tmp_git_repo) == "Suite de Teste"


def test_hooks_dir_defaults_to_dot_git_hooks(tmp_git_repo):
    assert hooks_dir(tmp_git_repo).resolve() == (tmp_git_repo / ".git" / "hooks").resolve()


def test_hooks_dir_respects_core_hookspath(tmp_git_repo):
    """Edge case: config customizada — assumir `.git/hooks` escreveria no lugar errado."""
    # Arrange
    run_git(["config", "core.hooksPath", "meus-hooks"], cwd=tmp_git_repo)

    # Act / Assert
    assert hooks_dir(tmp_git_repo).name == "meus-hooks"


@pytest.mark.parametrize("cls", [GitUnavailableError, NotAGitRepositoryError])
def test_every_git_error_carries_the_usage_exit_code(cls):
    # A invariante do ADR D4 do M0 estendida aos erros novos.
    assert cls("contexto").exit_code == ExitCode.USAGE_ERROR


# --- M5: falha do git é condição operacional, não defeito nosso -----------------


def test_git_command_failure_raises_a_typed_error(tmp_path):
    """Um comando do git que falha precisa virar erro de domínio, não `RuntimeError`.

    `cli.main` captura apenas `GitsafetyError` — de propósito, para que defeito nosso suba
    com traceback (`rules/error-handling.md § 5`). Mas git antigo sem `--diff-merges`, ou
    um repositório corrompido, são condições **esperadas**: viram traceback cru e o usuário
    não sabe o que fazer com ele.
    """
    from gitsafety.errors import ExitCode, GitCommandError

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    with pytest.raises(GitCommandError) as exc:
        run_git(["log", "--flag-que-nao-existe"], cwd=tmp_path)

    assert exc.value.exit_code == ExitCode.USAGE_ERROR
    assert "--flag-que-nao-existe" in exc.value.message


def test_git_timeout_raises_a_typed_error(tmp_path, monkeypatch):
    """Timeout em repositório enorme é o Risco M5 nº 1 acontecendo — precisa de mensagem."""
    from gitsafety.errors import GitCommandError

    def estourar(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(subprocess, "run", estourar)
    with pytest.raises(GitCommandError) as exc:
        run_git(["log"], cwd=tmp_path)

    assert "tempo" in exc.value.message.lower() or "timeout" in exc.value.message.lower()

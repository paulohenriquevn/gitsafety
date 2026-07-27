"""T2.2 — instalação do hook (ADRs D2, D3, D4, D8).

A proporção deste arquivo é deliberada: **mais teste de estado degenerado que de caminho
feliz**. Em `ggshield/tests/unit/cmd/test_install.py`, 4 de 7 testes cobrem "já existe
alguma coisa lá" (`:34,44,54,88,116,141`). No `install` o caminho feliz é trivial; o valor
está nos estados em que o sistema de arquivos não está limpo — que é a situação normal de
qualquer repositório com história.
"""

from __future__ import annotations

import pytest

from gitsafety.errors import (
    CommandNotOnPathError,
    HookExistsError,
    HookPathIsDirectoryError,
    NotAGitRepositoryError,
)
from gitsafety.hook import HOOK_MARKER, hook_path_for, install_hook, is_our_hook

# --- Estados degenerados (D6) --------------------------------------------------


def test_install_refuses_when_a_foreign_hook_exists(tmp_git_repo, gitsafety_on_path):
    """Nunca destruir configuração alheia — e dizer como prosseguir."""
    # Arrange
    alheio = hook_path_for(tmp_git_repo)
    alheio.parent.mkdir(parents=True, exist_ok=True)
    alheio.write_text("#!/bin/sh\necho outra-ferramenta\n", encoding="utf-8")

    # Act / Assert
    with pytest.raises(HookExistsError) as exc:
        install_hook(tmp_git_repo)

    # A mensagem precisa trazer a linha a colar, não só informar o conflito.
    assert HOOK_MARKER in str(exc.value)


def test_refused_install_leaves_the_foreign_hook_untouched(tmp_git_repo, gitsafety_on_path):
    """A recusa não pode ter efeito colateral."""
    # Arrange
    alheio = hook_path_for(tmp_git_repo)
    alheio.parent.mkdir(parents=True, exist_ok=True)
    original = "#!/bin/sh\necho outra-ferramenta\n"
    alheio.write_text(original, encoding="utf-8")

    # Act
    with pytest.raises(HookExistsError):
        install_hook(tmp_git_repo)

    # Assert
    assert alheio.read_text(encoding="utf-8") == original


def test_install_is_idempotent_when_the_hook_is_ours(tmp_git_repo, gitsafety_on_path):
    """Sem o marcador (D4), a segunda execução acusaria conflito com o próprio hook."""
    # Arrange
    install_hook(tmp_git_repo)

    # Act / Assert — não levanta.
    install_hook(tmp_git_repo)


def test_install_refuses_when_hook_path_is_a_directory(tmp_git_repo, gitsafety_on_path):
    """Erro próprio: apagar um diretório é decisão do usuário, não sugestão nossa."""
    # Arrange
    caminho = hook_path_for(tmp_git_repo)
    caminho.mkdir(parents=True, exist_ok=True)

    # Act / Assert
    with pytest.raises(HookPathIsDirectoryError):
        install_hook(tmp_git_repo)


def test_install_outside_a_git_repo_raises(tmp_path, gitsafety_on_path):
    # Caso negativo.
    with pytest.raises(NotAGitRepositoryError):
        install_hook(tmp_path)


def test_install_creates_the_hooks_directory_when_missing(tmp_git_repo, gitsafety_on_path):
    # Arrange — repositório sem diretório de hooks.
    import shutil

    hooks = hook_path_for(tmp_git_repo).parent
    if hooks.exists():
        shutil.rmtree(hooks)

    # Act
    escrito = install_hook(tmp_git_repo)

    # Assert
    assert escrito.exists()


def test_install_fails_when_gitsafety_is_not_on_path(tmp_git_repo, monkeypatch):
    """ADR D8: falhar na instalação, não no meio de um commit.

    O cenário reproduzido é o real: `git` instalado no sistema, mas o venv onde o
    gitsafety vive **não ativado**. Zerar o `PATH` inteiro testaria outra coisa — sem
    `git` a instalação falha antes, em `is_git_repository`, e o D8 nem seria alcançado.
    """
    # Arrange — só o diretório do git no PATH; o console script do venv fica de fora.
    import shutil as _shutil
    from pathlib import Path as _Path

    git_bin = _shutil.which("git")
    assert git_bin, "o ambiente de teste precisa de git para este cenário"
    monkeypatch.setenv("PATH", str(_Path(git_bin).parent))

    # Act / Assert
    with pytest.raises(CommandNotOnPathError):
        install_hook(tmp_git_repo)


# --- Conteúdo e permissão do hook (D2) -----------------------------------------


def test_installed_hook_is_executable_by_owner_only(tmp_git_repo, gitsafety_on_path):
    """`0o700`, não `0o755`: o hook executa código e deve alcançar o mínimo de usuários."""
    escrito = install_hook(tmp_git_repo)
    assert oct(escrito.stat().st_mode)[-3:] == "700"


def test_installed_hook_starts_with_sh_shebang(tmp_git_repo, gitsafety_on_path):
    assert install_hook(tmp_git_repo).read_text(encoding="utf-8").startswith("#!/bin/sh")


def test_installed_hook_invokes_scan_staged(tmp_git_repo, gitsafety_on_path):
    assert HOOK_MARKER in install_hook(tmp_git_repo).read_text(encoding="utf-8")


def test_installed_hook_forwards_arguments(tmp_git_repo, gitsafety_on_path):
    """`"$@"` — o git passa argumentos a alguns hooks; engoli-los quebra o contrato."""
    assert '"$@"' in install_hook(tmp_git_repo).read_text(encoding="utf-8")


# --- Reconhecimento e localização ----------------------------------------------


def test_is_our_hook_recognises_what_we_wrote(tmp_git_repo, gitsafety_on_path):
    assert is_our_hook(install_hook(tmp_git_repo)) is True


def test_is_our_hook_rejects_a_foreign_script(tmp_git_repo):
    # Caso negativo do marcador.
    alheio = tmp_git_repo / "outro"
    alheio.write_text("#!/bin/sh\necho nada a ver\n", encoding="utf-8")
    assert is_our_hook(alheio) is False


def test_is_our_hook_is_false_for_a_missing_file(tmp_path):
    # Edge case: consultar caminho inexistente responde, não levanta.
    assert is_our_hook(tmp_path / "nao-existe") is False


def test_install_respects_core_hookspath(tmp_git_repo, gitsafety_on_path):
    """Edge case: `core.hooksPath` customizado — escrever em `.git/hooks` seria inútil."""
    # Arrange
    from gitsafety.git import run_git

    run_git(["config", "core.hooksPath", "meus-hooks"], cwd=tmp_git_repo)

    # Act
    escrito = install_hook(tmp_git_repo)

    # Assert
    assert escrito.parent.name == "meus-hooks"

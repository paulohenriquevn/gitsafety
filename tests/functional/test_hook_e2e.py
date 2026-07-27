"""T3.1 — prova ponta a ponta: um `git commit` de verdade é bloqueado.

Todos os testes anteriores exercem partes. Este exerce o produto como o usuário o usa —
`git commit` real, hook real, exit code real. É o DoD nº 4 do `ROADMAP.md § M1`.

Sem mock do git (ADR D5): o comportamento sob teste **é** a interação com o git, e o
Risco nº 1 (índice divergindo do disco) só se manifesta num índice de verdade.
A asserção é sobre o **exit code**, não sobre texto — o contrato do hook com o git é
numérico, e asserir texto acoplaria o teste à formatação.
"""

from __future__ import annotations

from gitsafety.hook import install_hook

SECRET = "AKIAIOSFODNN7EXAMPLE"


def test_commit_with_a_new_secret_is_blocked(
    tmp_git_repo, stage, git_commit, gitsafety_on_path
):
    # Arrange
    install_hook(tmp_git_repo)
    stage("config.py", f'API_KEY = "{SECRET}"\n')

    # Act
    resultado = git_commit("adiciona config")

    # Assert
    assert resultado.returncode != 0, resultado.stdout + resultado.stderr


def test_clean_commit_succeeds_with_the_hook_installed(
    tmp_git_repo, stage, git_commit, gitsafety_on_path
):
    """O hook não pode atrapalhar o fluxo normal — é metade da razão de ele ser tolerado."""
    # Arrange
    install_hook(tmp_git_repo)
    stage("app.py", "print('ok')\n")

    # Act
    resultado = git_commit("adiciona app")

    # Assert
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_no_verify_bypasses_the_hook(tmp_git_repo, stage, git_commit, gitsafety_on_path):
    """O bypass é nativo do git e não deve ser combatido (`docs/PRD.md § 6.1`)."""
    # Arrange
    install_hook(tmp_git_repo)
    stage("config.py", f'API_KEY = "{SECRET}"\n')

    # Act
    resultado = git_commit("bypass consciente", no_verify=True)

    # Assert
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_secret_only_on_disk_does_not_block_the_commit(
    tmp_git_repo, stage, git_commit, gitsafety_on_path
):
    """O RISCO Nº 1 DO ROADMAP, PONTA A PONTA.

    O índice tem conteúdo limpo; o disco tem o segredo. Uma implementação que lesse o
    disco bloquearia um commit que não contém segredo nenhum.
    """
    # Arrange
    install_hook(tmp_git_repo)
    stage("a.py", "x = 1\n")
    (tmp_git_repo / "a.py").write_text(f'K = "{SECRET}"\n', encoding="utf-8")

    # Act
    resultado = git_commit("commit seguro")

    # Assert
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_blocked_commit_shows_the_masked_secret_not_the_real_one(
    tmp_git_repo, stage, git_commit, gitsafety_on_path
):
    """A saída do hook chega ao terminal do usuário — e não pode vazar (`PRD § NFR-4`).

    Este é o teste que impede o produto de virar o problema que ele resolve: o segredo
    aparece no terminal, no histórico do shell e, muitas vezes, no log do CI.
    """
    # Arrange
    install_hook(tmp_git_repo)
    stage("config.py", f'API_KEY = "{SECRET}"\n')

    # Act
    resultado = git_commit("adiciona config")
    saida = resultado.stdout + resultado.stderr

    # Assert
    assert SECRET not in saida
    assert "AKIA" in saida  # o prefixo fica: identifica o provedor sem expor a chave


def test_blocked_commit_tells_the_user_to_revoke(
    tmp_git_repo, stage, git_commit, gitsafety_on_path
):
    """`PRD § FR-19`: remover a linha não desfaz a exposição."""
    install_hook(tmp_git_repo)
    stage("config.py", f'API_KEY = "{SECRET}"\n')
    saida = (lambda r: r.stdout + r.stderr)(git_commit("adiciona config"))
    assert "revogue" in saida.lower()


def test_commit_is_actually_prevented_not_just_reported(
    tmp_git_repo, stage, git_commit, gitsafety_on_path
):
    """Exit code não-zero é o contrato; o efeito é o commit **não existir**.

    Um hook que reclama mas deixa o commit passar seria pior que nenhum: daria a falsa
    sensação de proteção.
    """
    # Arrange
    from gitsafety.git import run_git

    install_hook(tmp_git_repo)
    stage("config.py", f'API_KEY = "{SECRET}"\n')

    # Act
    git_commit("adiciona config")

    # Assert — nenhum commit no repositório.
    contagem = run_git(["rev-list", "--all", "--count"], cwd=tmp_git_repo)
    assert contagem == "0"

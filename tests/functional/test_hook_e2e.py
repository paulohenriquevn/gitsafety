"""T3.1 — prova ponta a ponta: um `git commit` de verdade é bloqueado.

Todos os testes anteriores exercem partes. Este exerce o produto como o usuário o usa —
`git commit` real, hook real, exit code real. É o DoD nº 4 do `ROADMAP.md § M1`.

Sem mock do git (ADR D5): o comportamento sob teste **é** a interação com o git, e o
Risco nº 1 (índice divergindo do disco) só se manifesta num índice de verdade.
A asserção é sobre o **exit code**, não sobre texto — o contrato do hook com o git é
numérico, e asserir texto acoplaria o teste à formatação.
"""

from __future__ import annotations

import pytest

from gitsafety.hook import install_hook
from gitsafety.staged import scan_staged

SECRET = "AKIAIOSFODNN7EXAMPLE"


@pytest.mark.usefixtures("gitsafety_on_path")
def test_commit_with_a_new_secret_is_blocked(tmp_git_repo, stage, git_commit):
    # Arrange
    install_hook(tmp_git_repo)
    stage("config.py", f'API_KEY = "{SECRET}"\n')

    # Act
    resultado = git_commit("adiciona config")

    # Assert
    assert resultado.returncode != 0, resultado.stdout + resultado.stderr


@pytest.mark.usefixtures("gitsafety_on_path")
def test_clean_commit_succeeds_with_the_hook_installed(tmp_git_repo, stage, git_commit):
    """O hook não pode atrapalhar o fluxo normal — é metade da razão de ele ser tolerado."""
    # Arrange
    install_hook(tmp_git_repo)
    stage("app.py", "print('ok')\n")

    # Act
    resultado = git_commit("adiciona app")

    # Assert
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


@pytest.mark.usefixtures("gitsafety_on_path")
def test_no_verify_bypasses_the_hook(tmp_git_repo, stage, git_commit):
    """O bypass é nativo do git e não deve ser combatido (`docs/PRD.md § 6.1`)."""
    # Arrange
    install_hook(tmp_git_repo)
    stage("config.py", f'API_KEY = "{SECRET}"\n')

    # Act
    resultado = git_commit("bypass consciente", no_verify=True)

    # Assert
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


@pytest.mark.usefixtures("gitsafety_on_path")
def test_secret_only_on_disk_does_not_block_the_commit(tmp_git_repo, stage, git_commit):
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


@pytest.mark.usefixtures("gitsafety_on_path")
def test_blocked_commit_shows_the_masked_secret_not_the_real_one(
    tmp_git_repo, stage, git_commit
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


@pytest.mark.usefixtures("gitsafety_on_path")
def test_blocked_commit_tells_the_user_to_revoke(tmp_git_repo, stage, git_commit):
    """`PRD § FR-19`: remover a linha não desfaz a exposição."""
    install_hook(tmp_git_repo)
    stage("config.py", f'API_KEY = "{SECRET}"\n')
    saida = (lambda r: r.stdout + r.stderr)(git_commit("adiciona config"))
    assert "revogue" in saida.lower()


@pytest.mark.usefixtures("gitsafety_on_path")
def test_commit_is_actually_prevented_not_just_reported(tmp_git_repo, stage, git_commit):
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


# --- Notebook no hook: mesma localização do scan (issue #6) ----------------------


def test_staged_notebook_finding_reports_the_cell(tmp_git_repo, stage):
    """O hook e o `scan` precisam dizer a mesma coisa sobre o mesmo arquivo.

    O ADR D5 do M4 decidiu que `--staged` não parsearia notebooks, e estava certo NAQUELE
    momento: mapear a linha do diff de volta para a célula exigiria um segundo caminho de
    varredura, e o M4 gastou cinco rodadas de review consertando defeitos que nasceram
    exatamente disso.

    O M5 mudou o cálculo. `scanner._localise` já pareia achado bruto com achado de notebook
    **pela linha do arquivo** — o mecanismo existe, é usado pelo `--history`, e reusá-lo
    aqui não cria caminho novo nenhum.
    """
    import json

    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["import os\n"], "metadata": {}, "outputs": []},
            {
                "cell_type": "code",
                "source": [f'AWS = "{SECRET}"\n'],
                "metadata": {},
                "outputs": [],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    stage("analise.ipynb", json.dumps(notebook, indent=1))

    resultado = scan_staged(tmp_git_repo)

    assert len(resultado.findings) == 1
    assert "célula 2" in str(resultado.findings[0].path)


def test_staged_and_scan_agree_on_a_notebook(tmp_git_repo, stage):
    """A propriedade que a issue #6 pede: os dois alvos não divergem."""
    import json

    from gitsafety.scanner import scan_path

    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["x = 1\n", f'k = "{SECRET}"\n'],
                "metadata": {},
                "outputs": [],
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    stage("nb.ipynb", json.dumps(notebook, indent=1))

    # Compara a parte que descreve a LOCALIZAÇÃO dentro do arquivo. O prefixo difere por
    # desenho: `--staged` usa caminho relativo à raiz do repositório, `scan` usa o caminho
    # que recebeu. Essa diferença é anterior ao notebook e não é o que a issue #6 aponta.
    def localizacao(f):
        return str(f.path).split("::", 1)[1].strip() if "::" in str(f.path) else ""

    do_hook = {localizacao(f) for f in scan_staged(tmp_git_repo).findings}
    do_scan = {localizacao(f) for f in scan_path(tmp_git_repo).findings}

    assert do_hook == do_scan, (do_hook, do_scan)
    assert do_hook == {"célula 1 (código)"}


def test_hook_does_not_report_a_preexisting_secret_in_a_notebook(
    tmp_git_repo, stage, git_commit
):
    """O hook reclama do que você INTRODUZ, não do que já estava no arquivo.

    A localização por célula quebrou isto quando chegou: `_localise` foi escrito para o
    `scan`, onde a varredura de texto cobre o arquivo INTEIRO, e ali toda sobra é um valor
    partido pelo Jupyter. No hook o texto cobre só as linhas adicionadas — então todo
    segredo preexistente virava sobra e era reportado.

    `incluir_extras=False` desliga esse ramo nos caminhos que veem parte do arquivo.
    """
    import json

    def notebook(*celulas):
        return json.dumps(
            {
                "cells": [
                    {"cell_type": "code", "source": [c], "metadata": {}, "outputs": []}
                    for c in celulas
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            indent=1,
        )

    stage("a.ipynb", notebook(f'ANTIGO = "{SECRET}"\n'))
    git_commit("segredo preexistente")

    novo = "ghp_" + "a" * 36
    stage("a.ipynb", notebook(f'ANTIGO = "{SECRET}"\n', f'NOVO = "{novo}"\n'))

    achados = scan_staged(tmp_git_repo).findings

    assert [f.secret for f in achados] == [novo], "só o que foi introduzido"
    assert "célula 2" in str(achados[0].path)

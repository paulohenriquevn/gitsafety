"""T2.1 — `scan_history` num repositório de verdade.

Aqui moram os quatro itens do DoD do `ROADMAP.md § M5`, e o teste que prova que **não**
copiamos o comando do gitleaks: `test_secret_pasted_in_a_merge_resolution_is_found`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gitsafety.history import rewritten_commits, scan_history
from gitsafety.scanner import scan_path

AKIA = "AKIAIOSFODNN7EXAMPLE"
GHP = "ghp_" + "a" * 36


class Repo:
    """Fábrica de repositório com histórico.

    Imprime stdout e stderr do git antes de relançar, como
    `knowledge-base/references/ggshield/tests/repository.py:22-27` — um teste de histórico
    que falha sem mostrar a saída do git custa uma hora para diagnosticar.
    """

    def __init__(self, path: Path):
        self.path = path
        self.git("init", "-q", "-b", "main", ".")
        self.git("config", "user.email", "t@exemplo.com")
        self.git("config", "user.name", "Teste")

    def git(self, *args: str) -> str:
        p = subprocess.run(
            ["git", "-C", str(self.path), *args],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if p.returncode != 0:
            raise AssertionError(
                f"git {' '.join(args)} falhou ({p.returncode})\n"
                f"--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}"
            )
        return p.stdout

    def commit(self, nome: str, conteudo: str, mensagem: str = "c") -> str:
        alvo = self.path / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", mensagem)
        return self.git("rev-parse", "HEAD").strip()

    def remove(self, nome: str, mensagem: str = "remove") -> None:
        self.git("rm", "-q", nome)
        self.git("commit", "-q", "--no-verify", "-m", mensagem)


@pytest.fixture
def repo(tmp_path) -> Repo:
    return Repo(tmp_path)


# --- DoD do ROADMAP § M5 --------------------------------------------------------


def test_secret_introduced_and_later_removed_is_still_found(repo):
    """DoD nº 3 — o teste que carrega o milestone.

    O arquivo não existe mais na árvore; `gitsafety scan` não acha nada. O histórico é a
    única forma de saber que a chave esteve exposta e precisa ser revogada.
    """
    sha = repo.commit("config.py", f"AWS = '{AKIA}'\n")
    repo.remove("config.py")

    assert scan_path(repo.path).findings == []  # a árvore está limpa
    achados = scan_history(repo.path)

    assert len(achados) == 1
    assert achados[0].commit.sha == sha
    assert achados[0].finding.secret == AKIA


def test_repository_without_commits_reports_nothing_and_does_not_raise(tmp_path):
    """DoD nº 4 — resolvido por `--all`, não por caso especial (ADR D4)."""
    repo = Repo(tmp_path)
    assert scan_history(repo.path) == []


def test_history_reports_commit_author_and_date(repo):
    """DoD nº 1 — commit, autor e data."""
    sha = repo.commit("a.py", f"k = '{AKIA}'\n")
    commit = scan_history(repo.path)[0].commit

    assert commit.sha == sha
    assert commit.author == "Teste"
    assert commit.date.startswith("20")  # ISO-8601


def test_same_matcher_as_file_scan(repo):
    """DoD nº 2 — sem segundo motor: o que o scan de arquivo acha, o histórico acha."""
    repo.commit("a.py", f"AWS = '{AKIA}'\nGH = '{GHP}'\n")

    da_arvore = {f.secret for f in scan_path(repo.path).findings}
    do_historico = {h.finding.secret for h in scan_history(repo.path)}

    assert da_arvore <= do_historico, da_arvore - do_historico


# --- A divergência do gitleaks (ADR D1) -----------------------------------------


def test_secret_pasted_in_a_merge_resolution_is_found(repo):
    """O comando do gitleaks devolve 0 aqui; o nosso devolve 1.

    Cenário real: dois ramos tocam o mesmo arquivo, o merge conflita, e quem resolve cola
    uma credencial. O segredo não existe em **nenhum** dos pais — só no merge. `git log -p`
    não emite diff de merge por padrão, então ele fica invisível.
    """
    repo.commit("f.txt", "limpo\n")
    repo.git("switch", "-qc", "lado")
    repo.commit("f.txt", "versao do ramo\n")
    repo.git("switch", "-q", "main")
    repo.commit("f.txt", "versao do main\n")
    subprocess.run(["git", "-C", str(repo.path), "merge", "-q", "lado"], capture_output=True)
    (repo.path / "f.txt").write_text(f"conn = '{AKIA}'\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "--no-verify", "-m", "resolve conflito")

    # o segredo não está em nenhum pai
    assert AKIA not in repo.git("show", "lado:f.txt")

    achados = scan_history(repo.path)
    assert len(achados) == 1, [h.finding.secret for h in achados]


# --- Dedup (ADR D2 / Risco M5 nº 2) ---------------------------------------------


def test_secret_untouched_across_commits_counts_as_one_introduction(repo):
    """Uma linha que entra e permanece foi introduzida UMA vez.

    `-U0` mostra apenas linhas alteradas. Contar 3 aqui exigiria varrer a árvore de cada
    commit — outro custo e outra decisão. O que o número mede é introdução, e é o que o
    mecanismo entrega honestamente.
    """
    repo.commit("a.py", f"k = '{AKIA}'\n", "c1")
    repo.commit("a.py", f"k = '{AKIA}'\nx = 1\n", "c2")
    repo.commit("a.py", f"k = '{AKIA}'\nx = 2\n", "c3")

    achados = scan_history(repo.path)
    assert len(achados) == 1
    assert achados[0].introductions == 1


def test_secret_removed_and_reintroduced_counts_twice(repo):
    """O número > 1 significa algo específico: a credencial voltou depois de sair."""
    repo.commit("a.py", f"k = '{AKIA}'\n", "c1")
    repo.commit("a.py", "limpo\n", "c2 remove")
    repo.commit("a.py", f"k = '{AKIA}'\n", "c3 recoloca")

    achados = scan_history(repo.path)
    assert len(achados) == 1
    assert achados[0].introductions == 2


def test_reported_commit_is_the_oldest(repo):
    """ "Desde quando está exposta?" é a pergunta que decide a urgência."""
    primeiro = repo.commit("a.py", f"k = '{AKIA}'\n", "c1")
    repo.commit("a.py", f"k = '{AKIA}'\ny = 2\n", "c2")

    assert scan_history(repo.path)[0].commit.sha == primeiro


def test_secret_in_two_different_files_yields_two_findings(repo):
    """Caso negativo do dedup: o arquivo faz parte da chave, e são dois lugares."""
    repo.commit("a.py", f"k = '{AKIA}'\n", "c1")
    repo.commit("b.py", f"k = '{AKIA}'\n", "c2")

    assert len(scan_history(repo.path)) == 2


def test_same_secret_twice_in_one_commit_counts_as_one_commit(repo):
    """A contagem é de commits, não de linhas — ela mede exposição, não ocorrências."""
    repo.commit("a.py", f"k1 = '{AKIA}'\nk2 = '{AKIA}'\n")

    achados = scan_history(repo.path)
    assert len(achados) == 1
    assert achados[0].introductions == 1


# --- Supressão e casos negativos ------------------------------------------------


def test_allow_marker_in_a_historical_line_suppresses(repo):
    repo.commit("a.py", f"exemplo = '{AKIA}'  # gitsafety: allow\nreal = '{GHP}'\n")

    achados = scan_history(repo.path)
    assert [h.finding.rule_id for h in achados] == ["github-personal-access-token"]


def test_clean_history_yields_nothing(repo):
    repo.commit("a.py", "x = 1\n")
    assert scan_history(repo.path) == []


def test_secret_in_an_unmerged_branch_is_found(repo):
    """`--all` cobre refs que não estão em `HEAD` — um ramo abandonado ainda expõe."""
    repo.commit("a.py", "limpo\n")
    repo.git("switch", "-qc", "esquecido")
    repo.commit("b.py", f"k = '{AKIA}'\n")
    repo.git("switch", "-q", "main")

    assert len(scan_history(repo.path)) == 1


# --- Configuração (M3) vale no histórico ----------------------------------------


def test_ignore_glob_from_config_applies_to_history(repo):
    """`ignore:` do `.gitsafety.yml` vale nos três alvos, não só em dois.

    Achado na validação de integração: `scan` e `--staged` respeitavam a chave, e o
    `--history` a ignorava. Uma feature que vale em dois dos três alvos é pior que uma que
    não existe — o usuário configura, confere num alvo e supõe que vale nos outros.
    """
    from gitsafety.config import Config

    repo.commit("tests/fixtures.py", f"EXEMPLO = '{AKIA}'\n", "fixtures")
    repo.commit("app.py", f"REAL = '{GHP}'\n", "app")

    cfg = Config(ignore=("tests/*",))
    achados = scan_history(repo.path, config=cfg)

    assert [h.finding.rule_id for h in achados] == ["github-personal-access-token"]


# --- O invariante que a fixture ASCII não conseguia quebrar ---------------------
#
# `test_same_matcher_as_file_scan` afirma `scan_path ⊆ scan_history`, mas com conteúdo
# ASCII limpo — que nunca dispara as classes de entrada abaixo. Cada uma delas fazia o
# histórico **e o hook** ficarem cegos ao mesmo tempo, e a suíte inteira passava verde.
#
# As três primeiras são configuráveis pelo PRÓPRIO repositório: qualquer um que consiga
# commitar um `.gitattributes` desliga a verificação de um caminho.


def _scan_both(repo) -> tuple[set, set]:
    da_arvore = {f.secret for f in scan_path(repo.path).findings}
    do_historico = {h.finding.secret for h in scan_history(repo.path)}
    return da_arvore, do_historico


def test_gitattributes_minus_diff_does_not_hide_the_secret(repo):
    """`*.env -diff` faz o git emitir `Binary files differ` em vez do conteúdo."""
    (repo.path / ".gitattributes").write_text("*.env -diff\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "--no-verify", "-m", "attrs")
    repo.commit("prod.env", f"AWS_KEY={AKIA}\n", "credencial")

    da_arvore, do_historico = _scan_both(repo)
    assert da_arvore <= do_historico, da_arvore - do_historico


def test_textconv_driver_does_not_hide_the_secret(repo):
    """Um driver `textconv` reescreve o que o diff mostra — e pode redigir a credencial."""
    (repo.path / ".gitattributes").write_text("*.env diff=redact\n", encoding="utf-8")
    repo.git("config", "diff.redact.textconv", "sed s/AKIA[A-Z0-9]*/REDACTED/g")
    repo.git("add", "-A")
    repo.git("commit", "-q", "--no-verify", "-m", "attrs")
    repo.commit("prod.env", f"AWS_KEY={AKIA}\n", "credencial")

    da_arvore, do_historico = _scan_both(repo)
    assert da_arvore <= do_historico, da_arvore - do_historico


def test_nul_byte_does_not_hide_the_secret(repo):
    """A heurística de binário do git dispara com um NUL — comum em dump e UTF-16."""
    (repo.path / "w.txt").write_bytes(f"AWS_KEY={AKIA}\n\x00t\n".encode())
    repo.git("add", "-A")
    repo.git("commit", "-q", "--no-verify", "-m", "nul")

    da_arvore, do_historico = _scan_both(repo)
    assert da_arvore <= do_historico, da_arvore - do_historico


def test_latin1_file_does_not_abort_the_whole_scan(repo):
    """Um arquivo que não decodifica em UTF-8 não pode derrubar a varredura dos demais.

    `scanner._read_text` já usa `errors="replace"` desde o M0 e documenta o motivo; a
    defesa não tinha sido levada para a fronteira do git.
    """
    (repo.path / "latin.txt").write_bytes("configuração=café\n".encode("latin-1"))
    (repo.path / "ok.env").write_text(f"AWS_KEY={AKIA}\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "--no-verify", "-m", "latin")

    achados = scan_history(repo.path)
    assert [h.finding.secret for h in achados] == [AKIA]


# --- A lacuna do reflog, avisada em vez de silenciosa (issue #7) -----------------


def test_history_warns_when_rewritten_commits_exist(repo):
    """Quem reescreve o histórico para "remover" a chave precisa saber que não removeu.

    O pior resultado possível deste comando é falsa sensação de segurança: alguém roda
    `git reset`, vê "nenhum segredo encontrado" e acredita que resolveu. O commit saiu das
    referências, mas o objeto continua no repositório local por ~90 dias.

    O aviso custa 8 ms (`git rev-list --reflog --not --all --count`) e só aparece quando há
    de fato commit fora das referências.
    """
    repo.commit("base.txt", "base\n", "base")
    repo.commit("leak.env", f"AWS='{AKIA}'\n", "oops")
    repo.git("reset", "-q", "--soft", "HEAD~1")
    repo.git("restore", "--staged", "leak.env")
    (repo.path / "leak.env").unlink()
    repo.git("commit", "-q", "--allow-empty", "-m", "reescrito")

    assert scan_history(repo.path) == []  # o histórico está limpo, de fato
    assert rewritten_commits(repo.path) == 1


def test_no_warning_when_history_was_not_rewritten(repo):
    """Repositório comum não recebe aviso — senão vira ruído que ninguém lê."""
    repo.commit("a.py", "x = 1\n")
    assert rewritten_commits(repo.path) == 0


def test_history_localises_notebook_by_cell(repo):
    """A issue #6 vale para os TRÊS alvos, não para dois.

    Eu havia afirmado numa mensagem de commit que `--history` usava `scanner._localise` —
    era falso, o módulo nem o importava. O revisor conferiu e mostrou. Este teste existe
    para que a afirmação passe a ser verificável em vez de confiável.
    """
    import json

    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["import os\n"], "metadata": {}, "outputs": []},
            {
                "cell_type": "code",
                "source": [f'AWS = "{AKIA}"\n'],
                "metadata": {},
                "outputs": [],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    repo.commit("a.ipynb", json.dumps(notebook, indent=1), "notebook")

    achados = scan_history(repo.path)

    assert len(achados) == 1
    assert "célula 2" in str(achados[0].finding.path)


def test_history_does_not_swap_findings_between_cells(repo):
    """Dois segredos no mesmo notebook e commit não podem trocar de identidade.

    O pareamento era posicional — `zip(chaves, melhorados)` — sobre duas premissas falsas:
    `_localise` devolve ordenado por **linha**, não pela ordem de entrada, e pode devolver
    **menos** itens que recebeu, porque descarta os suprimidos. O efeito visível era a
    contagem de introduções aparecer no segredo errado, que é exatamente o campo que o
    usuário lê para saber que a credencial voltou depois de sair.
    """
    import json

    outro = "AKIAI44QH8DHBEXAMPLE"

    def nb(*celulas):
        return json.dumps(
            {
                "cells": [
                    {"cell_type": "code", "source": [c], "metadata": {}, "outputs": []}
                    for c in celulas
                ],
                "metadata": {},
                "nbformat": 4,
            },
            indent=1,
        )

    repo.commit("n.ipynb", nb(f"a = '{AKIA}'\n", "x = 1\n", f"b = '{outro}'\n"), "c1")
    repo.commit("n.ipynb", nb(f"a = '{AKIA}'\n", "x = 1\n", "y = 2\n"), "remove")
    repo.commit("n.ipynb", nb(f"a = '{AKIA}'\n", "x = 1\n", f"b = '{outro}'\n"), "recoloca")

    por_segredo = {h.finding.secret: h for h in scan_history(repo.path)}

    assert por_segredo[outro].introductions == 2, "quem voltou foi este"
    assert por_segredo[AKIA].introductions == 1, "este nunca saiu"
    assert "célula 1" in str(por_segredo[AKIA].finding.path)
    assert "célula 3" in str(por_segredo[outro].finding.path)


def test_history_honours_a_split_allow_marker_without_duplicating(repo):
    """Supressão no notebook não pode virar achado duplicado no histórico.

    `_localise` descarta o achado suprimido, devolvendo menos itens que recebeu. Com o
    pareamento posicional, o `strict=False` truncava em silêncio e deslocava o resto — o
    segredo real aparecia duas vezes, uma delas com a localização crua.
    """
    import json

    real = "AKIAI44QH8DHBEXAMPLE"
    nb = json.dumps(
        {
            "cells": [
                {
                    "cell_type": "code",
                    "source": [f"exemplo = '{AKIA}'", "  # gitsafety: allow\n"],
                    "metadata": {},
                    "outputs": [],
                },
                {
                    "cell_type": "code",
                    "source": [f"real = '{real}'\n"],
                    "metadata": {},
                    "outputs": [],
                },
            ],
            "metadata": {},
            "nbformat": 4,
        },
        indent=1,
    )
    repo.commit("n.ipynb", nb, "com marcador")

    achados = scan_history(repo.path)

    assert [h.finding.secret for h in achados] == [real]

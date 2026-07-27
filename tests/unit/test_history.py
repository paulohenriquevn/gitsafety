"""T1.1 — comando de histórico e fatiamento por commit (ADRs D1, D3 e D4 do M5).

O teste que carrega a fase é `test_diff_of_each_commit_is_isolated`: sem isolar, o parser
de diff do M1 veria cabeçalhos de commit como conteúdo e o achado perderia o commit — que é
exatamente o que o `ROADMAP.md § M5` manda reportar.
"""

from __future__ import annotations

import inspect

from gitsafety.history import SEPARADOR, CommitInfo, history_diff, parse_commits


def _cabecalho(sha: str, autor: str, data: str, assunto: str) -> str:
    return SEPARADOR.join([sha, autor, data, assunto])


BRUTO = "\n".join(
    [
        _cabecalho("aaa111", "Ana", "2026-07-01T10:00:00-03:00", "primeiro"),
        "diff --git a/a.py b/a.py",
        "--- /dev/null",
        "+++ b/a.py",
        "@@ -0,0 +1 @@",
        "+k = 'commit1'",
        "",
        _cabecalho("bbb222", "Bruno", "2026-07-02T11:00:00-03:00", "segundo"),
        "diff --git a/b.py b/b.py",
        "--- /dev/null",
        "+++ b/b.py",
        "@@ -0,0 +1 @@",
        "+k = 'commit2'",
        "",
    ]
)


# --- Cabeçalho ------------------------------------------------------------------


def test_commit_header_is_parsed_into_fields():
    commit, _ = parse_commits(BRUTO)[0]
    assert commit == CommitInfo(
        sha="aaa111", author="Ana", date="2026-07-01T10:00:00-03:00", subject="primeiro"
    )


def test_commits_come_in_the_order_git_emitted_them():
    assert [c.sha for c, _ in parse_commits(BRUTO)] == ["aaa111", "bbb222"]


# --- Isolamento do diff ---------------------------------------------------------


def test_diff_of_each_commit_is_isolated():
    """O diff de um commit não pode conter linha de outro — senão o achado perde o commit."""
    _, diff_segundo = parse_commits(BRUTO)[1]
    assert "commit1" not in diff_segundo
    assert "commit2" in diff_segundo


def test_commit_header_is_not_part_of_the_diff():
    """O cabeçalho não pode vazar para o diff: `parse_added_lines` o leria como conteúdo."""
    _, diff = parse_commits(BRUTO)[0]
    assert "Ana" not in diff
    assert SEPARADOR not in diff


# --- Casos negativos e de borda -------------------------------------------------


def test_empty_output_yields_no_commits():
    """Repositório sem commits: `--all` devolve vazio, e vazio não é erro (ADR D4)."""
    assert parse_commits("") == []


def test_whitespace_only_output_yields_no_commits():
    assert parse_commits("\n\n  \n") == []


def test_commit_without_diff_is_kept_with_empty_diff():
    """Commit vazio (`--allow-empty`) tem cabeçalho e nenhum diff — não pode sumir."""
    bruto = _cabecalho("ccc333", "Carla", "2026-07-03T12:00:00-03:00", "vazio")
    commits = parse_commits(bruto)
    assert len(commits) == 1
    assert commits[0][1].strip() == ""


def test_subject_containing_the_separator_does_not_shift_the_fields():
    """Caso negativo: o separador dentro do assunto não pode desalinhar os campos.

    `%s` é o último campo do formato, então tudo o que sobra pertence a ele. Fatiar com
    limite máximo é o que garante isso — dividir sem limite roubaria caracteres do assunto
    e, pior, faria um assunto malicioso deslocar a data para o lugar do autor.
    """
    bruto = _cabecalho("ddd444", "Dora", "2026-07-04T13:00:00-03:00", f"a{SEPARADOR}b")
    commit, _ = parse_commits(bruto)[0]
    assert commit.author == "Dora"
    assert commit.date == "2026-07-04T13:00:00-03:00"
    assert commit.subject == f"a{SEPARADOR}b"


def test_malformed_header_is_skipped_without_aborting():
    """Uma linha que parece cabeçalho mas não tem os campos não derruba o resto."""
    bruto = "\n".join(
        [
            f"quebrado{SEPARADOR}sem-campos",
            _cabecalho("eee555", "Edu", "2026-07-05T14:00:00-03:00", "bom"),
            "+k = 'valor'",
        ]
    )
    commits = parse_commits(bruto)
    assert [c.sha for c, _ in commits] == ["eee555"]


def test_diff_line_that_looks_like_a_header_is_not_treated_as_one():
    """Conteúdo de arquivo contendo o separador não pode abrir um commit falso."""
    bruto = "\n".join(
        [
            _cabecalho("fff666", "Fabi", "2026-07-06T15:00:00-03:00", "ok"),
            "+++ b/a.py",
            "@@ -0,0 +1 @@",
            f"+texto com {SEPARADOR} no meio",
        ]
    )
    commits = parse_commits(bruto)
    assert len(commits) == 1, [c.sha for c, _ in commits]


# --- O comando (ADR D1) ---------------------------------------------------------


def test_history_diff_uses_the_flags_decided_in_adr_d1():
    """As flags NÃO são cosméticas — `--diff-merges=first-parent` é a decisão do milestone.

    `--full-history --diff-filter=tuxdb`, que o gitleaks usa, foi medido devolvendo 0
    ocorrências onde há 1 real (segredo colado na resolução de um conflito de merge). Este
    teste existe para que ninguém "simplifique" o comando de volta ao do peer.
    """
    fonte = inspect.getsource(history_diff)
    assert "--all" in fonte, "sem --all, repo sem commits sai 128 em vez de 0 (ADR D4)"
    assert "--diff-merges=first-parent" in fonte, "sem isso, segredo de merge some (ADR D1)"
    assert "-U0" in fonte
    assert "--no-ext-diff" in fonte, "diff.external do usuário mudaria o formato parseado"
    assert "--diff-filter" not in fonte, "flag do gitleaks sem razão citável (ADR D1)"

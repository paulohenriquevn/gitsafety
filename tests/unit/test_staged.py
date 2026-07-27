"""T1.2 — leitura do índice e extração das linhas adicionadas (ADR D1).

Dois testes carregam este arquivo:

- `test_scan_staged_ignores_secret_that_is_on_disk_but_not_staged` — o Risco nº 1 do
  `ROADMAP.md § M1` em forma executável. Se a implementação ler o disco, ele falha.
- `test_scan_staged_ignores_preexisting_secret_in_a_touched_file` — documenta a
  consequência declarada do ADR D1. Não é bug: é a decisão que impede o hook de bloquear
  todo commit em repositório legado.

O resto cobre o parser de diff unificado, onde o erro típico é aritmética de número de
linha — que produz relatório apontando para a linha errada, defeito que passa despercebido
porque o finding existe.
"""

from __future__ import annotations

from gitsafety.staged import parse_added_lines, scan_staged

SECRET = "AKIAIOSFODNN7EXAMPLE"


# --- Parser de diff unificado --------------------------------------------------


def test_parse_extracts_added_line_with_correct_number():
    # Arrange — hunk que insere na linha 3 do arquivo novo.
    diff = (
        "diff --git a/a.py b/a.py\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -0,0 +3 @@\n"
        f"+{SECRET}\n"
    )

    # Act
    linhas = parse_added_lines(diff)

    # Assert
    assert len(linhas) == 1
    assert linhas[0].line == 3
    assert linhas[0].text == SECRET
    assert linhas[0].path.name == "a.py"


def test_removed_lines_are_not_reported():
    """Caso negativo: apagar um segredo não pode acusar o usuário."""
    diff = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -3 +0,0 @@\n" f"-{SECRET}\n"
    )
    assert parse_added_lines(diff) == []


def test_plus_plus_plus_header_is_not_an_added_line():
    """Edge case clássico: `+++ b/arquivo` começa com `+` e não é conteúdo."""
    diff = "diff --git a/a.py b/a.py\n--- /dev/null\n+++ b/a.py\n@@ -0,0 +1 @@\n+x = 1\n"
    linhas = parse_added_lines(diff)
    assert len(linhas) == 1
    assert linhas[0].text == "x = 1"


def test_multiple_hunks_each_restart_the_line_counter():
    # Arrange — dois hunks distantes no mesmo arquivo.
    diff = (
        "diff --git a/a.py b/a.py\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -1,0 +2 @@\n"
        "+primeiro\n"
        "@@ -10,0 +50 @@\n"
        "+segundo\n"
    )

    # Act
    linhas = parse_added_lines(diff)

    # Assert — cada hunk usa o `c` do seu próprio cabeçalho.
    assert [(x.line, x.text) for x in linhas] == [(2, "primeiro"), (50, "segundo")]


def test_consecutive_added_lines_increment_the_counter():
    diff = (
        "diff --git a/a.py b/a.py\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -0,0 +5,3 @@\n"
        "+um\n+dois\n+tres\n"
    )
    assert [x.line for x in parse_added_lines(diff)] == [5, 6, 7]


def test_new_file_takes_its_name_from_the_plus_side():
    """Arquivo novo tem `--- /dev/null`; o nome só existe do lado `+++`."""
    diff = "diff --git a/n.py b/n.py\n--- /dev/null\n+++ b/n.py\n@@ -0,0 +1 @@\n+x = 1\n"
    assert parse_added_lines(diff)[0].path.name == "n.py"


def test_binary_file_marker_produces_no_findings_and_no_error():
    """Caso negativo: binário não tem linhas `+` e não pode derrubar o parser."""
    diff = "diff --git a/logo.png b/logo.png\nBinary files a/logo.png and b/logo.png differ\n"
    assert parse_added_lines(diff) == []


def test_empty_diff_produces_no_findings():
    # Edge case: nada em stage.
    assert parse_added_lines("") == []


def test_parser_handles_noprefix_style_headers():
    """Edge case: `diff.noprefix=true` na config do usuário remove o `a/`/`b/`.

    Passamos `--src-prefix`/`--dst-prefix` justamente para evitar isso, mas o parser não
    deve quebrar se um diff vier de outra origem.
    """
    diff = "diff --git a.py a.py\n--- a.py\n+++ a.py\n@@ -0,0 +1 @@\n+x = 1\n"
    linhas = parse_added_lines(diff)
    assert len(linhas) == 1
    assert linhas[0].path.name == "a.py"


# --- Integração com o índice de verdade ----------------------------------------


def test_scan_staged_finds_secret_added_to_the_index(tmp_git_repo, stage):
    # Arrange
    stage("cfg.py", f'K = "{SECRET}"\n')

    # Act
    resultado = scan_staged(tmp_git_repo)

    # Assert
    assert resultado.has_findings
    assert resultado.findings[0].rule_id == "aws-access-key-id"


def test_scan_staged_ignores_secret_that_is_on_disk_but_not_staged(tmp_git_repo, stage):
    """O RISCO Nº 1 DO ROADMAP, EM FORMA DE TESTE.

    `git add -p` faz índice e disco divergirem. Uma implementação que lê o disco acha o
    segredo aqui e bloqueia um commit que não o contém — e, pior, o inverso também vale:
    ela deixaria passar um segredo que está no índice mas não no disco.
    """
    # Arrange — o índice tem conteúdo limpo; o disco, não.
    stage("a.py", "x = 1\n")
    (tmp_git_repo / "a.py").write_text(f'K = "{SECRET}"\n', encoding="utf-8")

    # Act
    resultado = scan_staged(tmp_git_repo)

    # Assert
    assert resultado.has_findings is False


def test_scan_staged_ignores_preexisting_secret_in_a_touched_file(tmp_git_repo, stage):
    """Consequência declarada do ADR D1, documentada por teste.

    Segredo que já estava commitado não é reportado quando o usuário edita outra linha
    do mesmo arquivo. É deliberado: varrer o arquivo inteiro faria a adoção em
    repositório legado bloquear todo commit até alguém limpar o histórico.
    """
    import subprocess

    # Arrange — o segredo entra no histórico primeiro.
    stage("legado.py", f'ANTIGO = "{SECRET}"\n')
    subprocess.run(
        ["git", "-C", str(tmp_git_repo), "commit", "-q", "-m", "legado"],
        check=True,
        capture_output=True,
    )
    # Agora o usuário edita OUTRA linha do mesmo arquivo.
    stage("legado.py", f'ANTIGO = "{SECRET}"\nnovo = 1\n')

    # Act
    resultado = scan_staged(tmp_git_repo)

    # Assert — só a linha nova foi varrida, e ela é limpa.
    assert resultado.has_findings is False


def test_scan_staged_reports_the_line_number_within_the_new_file(tmp_git_repo, stage):
    # Arrange
    stage("cfg.py", f'a = 1\nb = 2\nK = "{SECRET}"\n')

    # Act / Assert
    assert scan_staged(tmp_git_repo).findings[0].line == 3


def test_scan_staged_on_a_clean_index_finds_nothing(tmp_git_repo, stage):
    stage("app.py", "print('ok')\n")
    assert scan_staged(tmp_git_repo).has_findings is False


def test_scan_staged_with_nothing_staged_finds_nothing(tmp_git_repo):
    # Edge case: `git commit` sem nada em stage; o hook ainda roda.
    assert scan_staged(tmp_git_repo).has_findings is False

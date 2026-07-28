"""T2.3 — travessia de arquivos com pulos reportados (ADRs D1 e D3).

Este é o task que ataca o risco nº 2 do `ROADMAP.md § M0`. Ele tem duas metades:

1. A heurística de classificação (D1) — por extensão, nunca lendo conteúdo.
2. A visibilidade do pulo (D3) — o arquivo pulado é valor de retorno, com motivo.

A segunda metade é a que realmente resolve o risco. O D1 admite que a heurística
erra; o que impede o erro de virar falso negativo silencioso é o pulo aparecer no
resultado, não a heurística ser perfeita.
"""

from __future__ import annotations

import pytest

from gitsafety.errors import GitUnavailableError, PathNotFoundError
from gitsafety.walker import MAX_FILE_BYTES, SkipReason, is_binary_path, walk
from tests.conftest import _git


def test_walk_returns_text_files_to_scan(tmp_path):
    # Arrange
    (tmp_path / "app.py").write_text("print('ok')\n")
    (tmp_path / "notas.md").write_text("# título\n")

    # Act
    files, skipped = walk(tmp_path)

    # Assert
    assert {p.name for p in files} == {"app.py", "notas.md"}
    assert skipped == []


def test_walk_descends_into_subdirectories(tmp_path):
    # Arrange
    sub = tmp_path / "src" / "deep"
    sub.mkdir(parents=True)
    (sub / "mod.py").write_text("x = 1\n")

    # Act
    files, _ = walk(tmp_path)

    # Assert
    assert [p.name for p in files] == ["mod.py"]


def test_walk_accepts_a_single_file_as_root(tmp_path):
    # Arrange — `gitsafety scan arquivo.py` é uso legítimo.
    alvo = tmp_path / "app.py"
    alvo.write_text("x = 1\n")

    # Act
    files, skipped = walk(alvo)

    # Assert
    assert files == [alvo]
    assert skipped == []


# --- D3: o pulo é resultado, não efeito colateral ------------------------------


def test_walk_reports_binary_file_as_skipped_instead_of_dropping_it(tmp_path):
    """O coração do risco nº 2: o pulo precisa ser visível."""
    # Arrange
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")

    # Act
    files, skipped = walk(tmp_path)

    # Assert
    assert files == []
    assert [s.reason for s in skipped] == [SkipReason.BINARY]
    assert skipped[0].path.name == "logo.png"


def test_walk_reports_oversized_file_as_skipped(tmp_path):
    # Arrange
    grande = tmp_path / "dump.txt"
    grande.write_text("x" * (MAX_FILE_BYTES + 1))

    # Act
    files, skipped = walk(tmp_path)

    # Assert
    assert files == []
    assert [s.reason for s in skipped] == [SkipReason.TOO_LARGE]


def test_file_at_exactly_the_limit_is_scanned_not_skipped(tmp_path):
    """Edge case de fronteira: o limite é inclusivo.

    Off-by-one aqui produz falso negativo em arquivos de exatamente 1 MB — raro,
    mas silencioso, que é a combinação cara.
    """
    # Arrange
    borda = tmp_path / "edge.txt"
    borda.write_text("x" * MAX_FILE_BYTES)

    # Act
    files, skipped = walk(tmp_path)

    # Assert
    assert len(files) == 1
    assert skipped == []


def test_file_one_byte_over_the_limit_is_skipped(tmp_path):
    # Edge case gêmeo do anterior: o primeiro valor inválido logo após a fronteira.
    (tmp_path / "over.txt").write_text("x" * (MAX_FILE_BYTES + 1))
    _, skipped = walk(tmp_path)
    assert [s.reason for s in skipped] == [SkipReason.TOO_LARGE]


# --- D1: extensão antes de tamanho ---------------------------------------------


def test_binary_extension_is_checked_before_file_size(tmp_path):
    """Prova a ordem das decisões, não só o resultado.

    Checar extensão é consulta em conjunto; checar tamanho é um `stat()`. Inverter a
    ordem gasta um `stat()` em todo binário. O motivo reportado é o que revela qual
    verificação decidiu.
    """
    # Arrange — binário E grande ao mesmo tempo.
    (tmp_path / "big.png").write_bytes(b"\x00" * (MAX_FILE_BYTES + 1))

    # Act
    _, skipped = walk(tmp_path)

    # Assert — BINARY, não TOO_LARGE.
    assert skipped[0].reason == SkipReason.BINARY


@pytest.mark.parametrize(
    "nome",
    ["logo.png", "app.exe", "arquivo.zip", "video.mp4", "fonte.woff2", "lib.so"],
)
def test_known_binary_extensions_are_classified_as_binary(nome, tmp_path):
    assert is_binary_path(tmp_path / nome) is True


@pytest.mark.parametrize(
    "nome",
    ["app.py", "notas.md", "config.yml", "script.sh", "dados.csv", "sem_extensao"],
)
def test_text_extensions_are_not_classified_as_binary(nome, tmp_path):
    """Caso negativo: o custo do D1 é pular texto por engano — não pode ser frequente."""
    assert is_binary_path(tmp_path / nome) is False


def test_classification_never_reads_the_file(tmp_path):
    """ADR D1: a classificação é por extensão, sem tocar o conteúdo.

    O teste usa um caminho que NÃO existe em disco: se a implementação lesse bytes
    para decidir, levantaria FileNotFoundError aqui.
    """
    assert is_binary_path(tmp_path / "inexistente.png") is True


# --- Caso negativo: raiz inexistente -------------------------------------------


def test_walk_raises_typed_error_when_root_does_not_exist(tmp_path):
    """Nunca retornar vazio em silêncio.

    `gitsafety scan /caminho/digitado/errado` devolvendo lista vazia sairia com 0 e o
    usuário concluiria que está limpo — o falso negativo mais caro possível.
    """
    # Arrange
    fantasma = tmp_path / "inexistente"

    # Act / Assert
    with pytest.raises(PathNotFoundError) as exc:
        walk(fantasma)
    assert "inexistente" in str(exc.value)


# --- O que o git ignora, a gente ignora (#8) -------------------------------------
#
# Encontrado instalando a ferramenta num monorepo real: 197 arquivos rastreados,
# 20.479 percorridos. O resto era `node_modules/` — código de terceiros que quem roda
# o scan não escreveu, não controla e não pode corrigir. Achado ali é falso positivo
# por definição, e falso positivo é o que faz desinstalarem a ferramenta.


def test_walk_skips_what_gitignore_excludes(tmp_git_repo):
    """O caso que motivou a correção: dependência instalada não é código do usuário."""
    (tmp_git_repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    (tmp_git_repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_git_repo / "node_modules" / "pacote").mkdir(parents=True)
    (tmp_git_repo / "node_modules" / "pacote" / "index.js").write_text(
        "const k = 'AKIAIOSFODNN7EXAMPLE'\n", encoding="utf-8"
    )

    files, _ = walk(tmp_git_repo)

    nomes = {p.name for p in files}
    assert "app.py" in nomes
    assert "index.js" not in nomes, "arquivo gitignorado entrou na varredura"


def test_walk_does_not_read_the_git_directory_itself(tmp_git_repo):
    """`.git/` é o banco de dados do git, não código — e nunca foi escrito por ninguém."""
    (tmp_git_repo / "app.py").write_text("print('ok')\n", encoding="utf-8")

    files, skipped = walk(tmp_git_repo)

    tudo = [p.as_posix() for p in files] + [s.path.as_posix() for s in skipped]
    assert not [p for p in tudo if "/.git/" in p or p.startswith(".git/")]


def test_walk_still_sees_a_file_that_was_force_added(tmp_git_repo, stage):
    """Rastreado vence o `.gitignore`.

    `git add -f` sobre um caminho ignorado é decisão deliberada de versionar aquilo.
    O arquivo passa a fazer parte do repositório, e o que está no repositório é
    exatamente o que pode vazar.
    """
    (tmp_git_repo / ".gitignore").write_text("segredos/\n", encoding="utf-8")
    alvo = tmp_git_repo / "segredos" / "prod.env"
    alvo.parent.mkdir()
    alvo.write_text("AWS=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    _git(tmp_git_repo, "add", "-f", "segredos/prod.env")

    files, _ = walk(tmp_git_repo)

    assert alvo in files


def test_walk_sees_a_new_file_that_was_never_added(tmp_git_repo):
    """Arquivo novo e não rastreado é o caso mais comum do `scan` — não pode sumir.

    Se o conjunto viesse só de `--cached`, o arquivo que você acabou de escrever (e é
    justamente onde a chave recém-colada está) não seria varrido.
    """
    novo = tmp_git_repo / "acabei_de_criar.py"
    novo.write_text("k = 'AKIAIOSFODNN7EXAMPLE'\n", encoding="utf-8")

    files, _ = walk(tmp_git_repo)

    assert novo in files


def test_walk_outside_a_git_repository_is_unchanged(tmp_path):
    """Pasta solta continua funcionando — o README promete `scan` fora de repo."""
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "outro.py").write_text("print('ok')\n", encoding="utf-8")

    files, _ = walk(tmp_path)

    assert {p.name for p in files} == {"app.py", "outro.py"}


def test_walk_falls_back_to_the_filesystem_when_git_is_missing(tmp_git_repo, monkeypatch):
    """Sem `git` no PATH, varre a mais — nunca a menos.

    A referência diz que o git só é exigido por `--staged` e `--history`; o scan de
    disco não pode passar a exigi-lo. E a direção do fallback importa: varrer demais
    gera ruído, varrer de menos esconde credencial. Um é irritante, o outro é o
    fracasso do produto.
    """
    (tmp_git_repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    (tmp_git_repo / "node_modules").mkdir()
    (tmp_git_repo / "node_modules" / "x.js").write_text("k=1\n", encoding="utf-8")

    monkeypatch.setattr(
        "gitsafety.walker.run_git",
        lambda *a, **k: (_ for _ in ()).throw(GitUnavailableError("sem git")),
    )
    files, _ = walk(tmp_git_repo)

    assert "x.js" in {p.name for p in files}


def test_walk_of_a_subdirectory_stays_inside_it(tmp_git_repo):
    """`gitsafety scan src/` não pode devolver achado de fora de `src/`."""
    (tmp_git_repo / "src").mkdir()
    (tmp_git_repo / "src" / "dentro.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_git_repo / "fora.py").write_text("print(2)\n", encoding="utf-8")

    files, _ = walk(tmp_git_repo / "src")

    assert {p.name for p in files} == {"dentro.py"}


def test_walk_of_a_single_file_ignores_gitignore(tmp_git_repo):
    """Apontar para um arquivo é pedido explícito — o usuário já decidiu o alvo."""
    (tmp_git_repo / ".gitignore").write_text("*.env\n", encoding="utf-8")
    alvo = tmp_git_repo / "prod.env"
    alvo.write_text("AWS=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    files, _ = walk(alvo)

    assert files == [alvo]


def test_the_users_ignore_still_applies_on_top_of_gitignore(tmp_git_repo):
    """As duas listas somam; a do `.gitsafety.yml` não foi substituída."""
    (tmp_git_repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    (tmp_git_repo / "fixtures").mkdir()
    (tmp_git_repo / "fixtures" / "exemplo.py").write_text("k=1\n", encoding="utf-8")
    (tmp_git_repo / "app.py").write_text("print(1)\n", encoding="utf-8")

    files, _ = walk(tmp_git_repo, ignore=("fixtures/**",))

    assert {p.name for p in files} == {"app.py", ".gitignore"}


def test_an_empty_repository_does_not_fall_back_to_the_filesystem(tmp_git_repo):
    """Lista vazia é resposta do git, não ausência de resposta.

    `_do_git` devolve `[]` num repositório recém-criado e `None` quando não deu para
    perguntar. Tratar os dois como a mesma coisa faria o repositório vazio cair no
    `rglob` e varrer os `.git/hooks/*.sample` — os únicos arquivos que sobram ali.
    """
    files, skipped = walk(tmp_git_repo)

    assert files == []
    assert skipped == []


# --- O glob do ignore é relativo à raiz do repositório (#10) ---------------------


def test_ignore_applies_the_same_from_the_root_and_from_a_subdirectory(tmp_git_repo):
    """O mesmo `ignore:` precisa valer nos dois níveis.

    Testar só a raiz deixa o defeito invisível — era o caso comum, e por isso ele passou
    despercebido. O par é o teste: `scan .` já funcionava; `scan src/` não.
    """
    (tmp_git_repo / "src").mkdir()
    (tmp_git_repo / "src" / "fixtures").mkdir()
    (tmp_git_repo / "src" / "fixtures" / "exemplo.py").write_text("k=1\n", encoding="utf-8")
    (tmp_git_repo / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")

    glob = ("src/fixtures/**",)

    da_raiz, _ = walk(tmp_git_repo, ignore=glob)
    do_subdir, _ = walk(tmp_git_repo / "src", ignore=glob)

    assert "exemplo.py" not in {p.name for p in da_raiz}
    assert "exemplo.py" not in {p.name for p in do_subdir}, (
        "o ignore foi desconsiderado ao varrer o subdiretório"
    )
    assert "app.py" in {p.name for p in do_subdir}


def test_ignore_outside_a_git_repository_is_relative_to_the_scan_target(tmp_path):
    """Sem repositório não há raiz — o alvo do scan é a única referência possível."""
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "exemplo.py").write_text("k=1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")

    files, _ = walk(tmp_path, ignore=("fixtures/**",))

    assert {p.name for p in files} == {"app.py"}

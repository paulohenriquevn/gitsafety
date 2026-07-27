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

from gitsafety.errors import PathNotFoundError
from gitsafety.walker import MAX_FILE_BYTES, SkipReason, is_binary_path, walk


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

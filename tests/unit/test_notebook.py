"""T1.1 — parsing de notebook (ADRs D1-D4 do M4).

O teste que carrega o milestone é `test_split_value_is_rejoined`: é o único falso negativo
que a medição do blueprint encontrou, e a razão de existir o `"".join(source)`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitsafety.notebook import CODE_ORIGIN, OUTPUT_ORIGIN, is_notebook, parse_notebook

PG = "postgresql://app:s3nh4Sup3r@db.exemplo.com/prod"


def _de(segs, origem: str) -> list:
    """Segmentos de uma origem.

    O percurso é genérico — emite segmento para todo texto do documento, inclusive valores
    estruturais como o `"code"` de `cell_type`. Selecionar por posição no resultado seria
    frágil; selecionar por origem é o que os testes realmente querem dizer.
    """
    return [s for s in segs if s.origin == origem]


def _nb(cells: list[dict], **extra) -> str:
    return json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, **extra})


def _code(source, outputs=None) -> dict:
    return {
        "cell_type": "code",
        "source": source,
        "outputs": outputs or [],
        "execution_count": 1,
        "metadata": {},
    }


# --- Estrutura básica ----------------------------------------------------------


def test_is_notebook_recognises_the_extension():
    assert is_notebook(Path("a.ipynb")) is True
    assert is_notebook(Path("a.py")) is False


def test_code_cell_becomes_a_segment():
    segs = _de(parse_notebook(_nb([_code(["x = 1\n"])])), CODE_ORIGIN)
    assert len(segs) == 1
    assert segs[0].cell_index == 1
    assert segs[0].text == "x = 1\n"


def test_source_as_string_is_accepted():
    """Edge case: o formato permite string, e ferramentas que geram notebook variam."""
    segs = parse_notebook(_nb([_code("x = 1\n")]))
    assert segs and segs[0].text == "x = 1\n"


def test_v3_input_key_is_accepted():
    """Risco M4 nº 1: tratar só `source` daria falso negativo **silencioso** em v3."""
    antigo = {"cell_type": "code", "input": ["x = 1\n"], "outputs": [], "metadata": {}}
    segs = parse_notebook(_nb([antigo]))
    assert segs and segs[0].text == "x = 1\n"


def test_real_v3_notebook_keeps_cell_localisation():
    """Um v3 REAL guarda as células em `worksheets[]`, não no topo.

    O teste anterior montava um híbrido que não existe — container v4 com chave v3 — e
    passava validando ficção: em v3 conforme ao schema, `input` nunca era alcançado, e o
    notebook inteiro caía na degradação para texto. O segredo era achado, mas sem a
    localização por célula, que é justamente o valor deste milestone.
    """
    v3 = json.dumps(
        {
            "nbformat": 3,
            "nbformat_minor": 0,
            "metadata": {},
            "worksheets": [
                {
                    "cells": [
                        {
                            "cell_type": "code",
                            "input": ["x = 1\n"],
                            "outputs": [],
                            "language": "python",
                        }
                    ]
                }
            ],
        }
    )
    segs = parse_notebook(v3)
    assert segs is not None, "v3 real não pode cair na degradação"
    assert segs[0].cell_index == 1
    assert segs[0].text == "x = 1\n"


def test_input_is_read_when_source_is_present_but_empty():
    """A parada é por conteúdo: `source: []` presente não pode esconder o `input`."""
    celula = {"cell_type": "code", "source": [], "input": ["k = 1\n"], "metadata": {}}
    segs = parse_notebook(_nb([celula]))
    assert segs and segs[0].text == "k = 1\n"


def test_traceback_lines_are_joined_with_newline():
    """`traceback` é array de LINHAS no schema, sem `\n` — juntar sem separador as gruda.

    A colagem fundia o fim de um valor com o começo da linha seguinte, e o delimitador de
    fim dos padrões deixava de casar: falso negativo por concatenação.
    """
    out = {
        "output_type": "error",
        "ename": "ValueError",
        "evalue": "x",
        "traceback": ["  chamada(", "    token=abc", "ValueError: bad"],
    }
    segs = parse_notebook(_nb([_code(["x\n"], [out])]))
    texto = next(s.text for s in segs if s.text.startswith("  chamada("))
    assert texto.splitlines() == ["  chamada(", "    token=abc", "ValueError: bad"]


def test_multiple_outputs_in_one_cell_are_distinguishable():
    """Duas saídas na mesma célula precisam ser localizáveis separadamente."""
    saidas = [
        {"output_type": "stream", "name": "stdout", "text": ["a\n"]},
        {"output_type": "stream", "name": "stderr", "text": ["b\n"]},
    ]
    segs = parse_notebook(_nb([_code(["x\n"], saidas)]))
    locais = {s.locate(Path("nb.ipynb")) for s in segs if s.text in ("a\n", "b\n")}
    assert len(locais) == 2, locais


def test_deeply_nested_json_degrades_instead_of_raising():
    """`RecursionError` derrubava a varredura dos DEMAIS arquivos do diretório."""
    assert parse_notebook("[" * 60_000 + "]" * 60_000) is None


def test_split_value_is_rejoined():
    """O ÚNICO FALSO NEGATIVO MEDIDO no blueprint.

    O Jupyter pode partir uma linha entre elementos de `source`, e o JSON insere
    `",\\n   "` entre eles. Nenhuma regex de linha atravessa isso; juntar antes, sim.
    """
    segs = parse_notebook(_nb([_code(["c = '" + PG[:22], PG[22:] + "'\n"])]))
    assert PG in segs[0].text


def test_cell_index_is_one_based_and_in_file_order():
    segs = _de(
        parse_notebook(_nb([_code(["a\n"]), _code(["b\n"]), _code(["c\n"])])), CODE_ORIGIN
    )
    assert [(s.cell_index, s.text) for s in segs] == [(1, "a\n"), (2, "b\n"), (3, "c\n")]


# --- Os quatro tipos de saída (ADR D3) -----------------------------------------


@pytest.mark.parametrize(
    ("output", "esperado"),
    [
        ({"output_type": "stream", "name": "stdout", "text": ["S1\n"]}, "S1\n"),
        (
            {"output_type": "execute_result", "data": {"text/plain": ["S2"]}, "metadata": {}},
            "S2",
        ),
        (
            {"output_type": "display_data", "data": {"text/plain": ["S3"]}, "metadata": {}},
            "S3",
        ),
        ({"output_type": "error", "ename": "E", "evalue": "S4", "traceback": []}, "S4"),
    ],
)
def test_every_output_type_produces_a_segment(output, esperado):
    """Cobrir só `stream` perderia `execute_result` — o tipo de `os.environ` sozinho."""
    segs = parse_notebook(_nb([_code(["x\n"], [output])]))
    saidas = [s for s in segs if s.origin == OUTPUT_ORIGIN]
    assert esperado in "".join(s.text for s in saidas)


def test_error_traceback_is_scanned():
    """Traceback salvo carrega os valores da chamada que falhou."""
    out = {
        "output_type": "error",
        "ename": "ValueError",
        "evalue": "erro",
        "traceback": ["  chamada(token='ghp_x')\n"],
    }
    segs = parse_notebook(_nb([_code(["x\n"], [out])]))
    assert any("ghp_x" in s.text for s in segs)


# --- Localização (ADR D1) ------------------------------------------------------


def test_locate_reports_cell_and_line_within_the_cell():
    """O ponto do milestone: a linha do JSON não serve a quem abre o notebook."""
    segs = _de(parse_notebook(_nb([_code(["a\n"]), _code(["b\n", "c\n"])])), CODE_ORIGIN)
    texto = segs[1].locate(Path("nb.ipynb"))
    assert "célula 2" in texto
    assert "nb.ipynb" in texto


def test_locate_distinguishes_code_from_output():
    segs = parse_notebook(
        _nb([_code(["x\n"], [{"output_type": "stream", "name": "stdout", "text": ["s\n"]}])])
    )
    codigo = _de(segs, CODE_ORIGIN)[0]
    saida = next(s for s in _de(segs, OUTPUT_ORIGIN) if s.text == "s\n")
    assert CODE_ORIGIN in codigo.locate(Path("nb.ipynb"))
    assert OUTPUT_ORIGIN in saida.locate(Path("nb.ipynb"))


# --- Casos negativos e degradação (ADR D4) -------------------------------------


def test_malformed_json_returns_none_for_degradation():
    """`None` sinaliza 'varra como texto' — degradação para estado conhecido."""
    assert parse_notebook("{quebrado") is None


def test_json_without_cells_returns_none():
    """JSON válido, forma errada — não é notebook."""
    assert parse_notebook('{"foo": 1}') is None


def test_top_level_list_returns_none():
    assert parse_notebook("[1, 2]") is None


def test_unexpected_field_shape_does_not_abort_the_notebook():
    """Um campo estranho não pode invalidar as demais células."""
    ruim = {"cell_type": "code", "source": ["a\n"], "outputs": {}, "metadata": {}}
    segs = _de(parse_notebook(_nb([ruim, _code(["b\n"])])), CODE_ORIGIN)
    assert [s.text for s in segs] == ["a\n", "b\n"]


def test_non_dict_cell_is_skipped_without_aborting():
    segs = _de(parse_notebook(_nb(["nao é dicionário", _code(["b\n"])])), CODE_ORIGIN)
    assert [s.text for s in segs] == ["b\n"]


def test_image_payload_is_skipped_but_other_mimes_are_not():
    """`image/*` é a ÚNICA exclusão — e ela é decidida, não esquecida.

    Base64 de PNG não casa com nenhum dos 53 padrões (todos ancorados em marcadores
    literais) e é a maior parte dos bytes de um notebook de análise. Todo mime que **não**
    seja imagem é percorrido: a versão anterior cobria só `text/plain` e por isso deixava
    passar o segredo no `repr` HTML de um DataFrame.
    """
    imagem = {"output_type": "display_data", "data": {"image/png": "iVBOR"}, "metadata": {}}
    html = {"output_type": "display_data", "data": {"text/html": ["<b>x</b>"]}, "metadata": {}}
    segs = parse_notebook(_nb([_code(["c\n"], [imagem, html])]))

    textos = [s.text for s in segs]
    assert "iVBOR" not in textos
    assert "<b>x</b>" in textos


def test_empty_notebook_produces_no_segments():
    assert parse_notebook(_nb([])) == []


# --- Unresolved Question Q2 ----------------------------------------------------


@pytest.mark.parametrize("tipo", ["markdown", "raw"])
def test_markdown_and_raw_cells_are_scanned(tipo):
    """Conteúdo literal que o usuário escreveu — não há razão para tratá-lo diferente."""
    celula = {"cell_type": tipo, "source": ["texto com segredo\n"], "metadata": {}}
    segs = parse_notebook(_nb([celula]))
    assert any("texto com segredo" in s.text for s in segs)

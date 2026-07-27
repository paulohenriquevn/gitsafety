"""T2.1 — varredura ponta a ponta de notebook.

Estes testes são a **medição do blueprint transformada em contrato**: o notebook de 5
segredos que a v0.4.0 achava 4, aqui exige 5.
"""

from __future__ import annotations

import json
import re

from gitsafety.scanner import scan_path
from gitsafety.walker import MAX_FILE_BYTES, SkipReason

AKIA = "AKIAIOSFODNN7EXAMPLE"
GHP = "ghp_" + "a" * 36
PG = "postgresql://app:s3nh4Sup3r@db.exemplo.com/prod"


def _write_nb(path, cells: list[dict]) -> None:
    path.write_text(
        json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}),
        encoding="utf-8",
    )


def _code(source, outputs=None) -> dict:
    return {
        "cell_type": "code",
        "source": source,
        "outputs": outputs or [],
        "execution_count": 1,
        "metadata": {},
    }


def _stream(texto: str) -> dict:
    return {"output_type": "stream", "name": "stdout", "text": [texto]}


def test_notebook_secret_reports_cell_and_line(tmp_path):
    """O resultado do milestone: a localização serve a quem abre o Jupyter."""
    nb = tmp_path / "a.ipynb"
    _write_nb(nb, [_code(["import os\n"]), _code(["x = 1\n", f"k = '{AKIA}'\n"])])

    achados = scan_path(tmp_path).findings

    assert len(achados) == 1
    assert "célula 2" in str(achados[0].path)
    assert achados[0].line == 2  # linha DENTRO da célula, não do JSON


def test_all_five_planted_secrets_are_found(tmp_path):
    """A medição do blueprint (4 de 5) vira contrato: 5 de 5.

    O 5º é o valor partido entre elementos de `source` — o falso negativo que motivou
    o milestone. Nenhuma regex de linha o atravessava.
    """
    nb = tmp_path / "analise.ipynb"
    _write_nb(
        nb,
        [
            _code([f"AWS = '{AKIA}'\n"]),
            _code(["print(t)\n"], [_stream(f"token={GHP}\n")]),
            _code([f"dsn = '{PG}'\n"]),
            _code(["print(c)\n"], [_stream(f"cred={AKIA}\n")]),
            _code(["g = '" + GHP[:20], GHP[20:] + "'\n"]),  # partido
        ],
    )

    achados = scan_path(tmp_path).findings

    assert len(achados) == 5, [str(f.path) for f in achados]
    celulas = {re.search(r"célula (\d+)", str(f.path)).group(1) for f in achados}
    assert celulas == {"1", "2", "3", "4", "5"}  # um por célula, nenhuma perdida


def test_malformed_notebook_still_finds_secrets(tmp_path):
    """D4: degradar para texto, não falhar. O segredo continua importando."""
    truncado = tmp_path / "truncado.ipynb"
    truncado.write_text(
        '{"cells": [{"cell_type": "code", "source": ["k = \'' + AKIA + "'\\n\"]",
        encoding="utf-8",
    )

    resultado = scan_path(tmp_path)

    assert resultado.findings != []
    assert "célula" not in str(resultado.findings[0].path)  # caminho de texto


def test_inline_marker_works_inside_a_cell(tmp_path):
    """O marcador do M2 vale dentro de célula — o `allow` opera sobre a linha do segmento."""
    nb = tmp_path / "a.ipynb"
    _write_nb(nb, [_code([f"exemplo = '{AKIA}'  # gitsafety: allow\n", f"real = '{GHP}'\n"])])

    achados = scan_path(tmp_path).findings

    assert len(achados) == 1
    assert achados[0].rule_id == "github-personal-access-token"


def test_non_notebook_files_are_unaffected(tmp_path):
    """Milestone aditivo: `.py` se comporta como no M3."""
    (tmp_path / "a.py").write_text(f"k = '{AKIA}'\n", encoding="utf-8")

    achados = scan_path(tmp_path).findings

    assert len(achados) == 1
    assert "célula" not in str(achados[0].path)
    assert achados[0].line == 1


def test_oversized_notebook_appears_in_skipped(tmp_path):
    """Risco M4 nº 2: notebook grande é pulado — mas **nunca em silêncio**.

    Mitigado desde o M0; faltava a evidência de que vale para `.ipynb`.
    """
    nb = tmp_path / "grande.ipynb"
    _write_nb(nb, [_code(["#" + "x" * MAX_FILE_BYTES + "\n"])])

    resultado = scan_path(tmp_path)

    assert [s.reason for s in resultado.skipped] == [SkipReason.TOO_LARGE]


def test_secret_only_in_saved_output_is_found(tmp_path):
    """O vetor que o `docs/PRD.md § 2` nomeia: a chave sobrevive no `print`."""
    nb = tmp_path / "a.ipynb"
    _write_nb(nb, [_code(["print(os.environ)\n"], [_stream(f"{{'AWS': '{AKIA}'}}\n")])])

    achados = scan_path(tmp_path).findings

    assert len(achados) == 1
    assert "saída" in str(achados[0].path)


# --- Ordem do relatório, afirmada em teste e não em comentário -------------------


def test_report_follows_the_order_of_the_file(tmp_path):
    """Os achados saem na ordem do arquivo, mesmo vindo por caminhos diferentes.

    Este teste existe por um motivo específico. Três defeitos de uma mesma revisão foram
    **comentários confiantes e falsos** — sobre ordem, sobre o que era compartilhado, sobre
    o que uma função devolvia. Nenhum foi pego por teste, porque comentário não é executável.

    O caso: o segredo e o marcador estão no **mesmo elemento JSON**, em linhas diferentes da
    célula. O arquivo bruto os vê numa linha só e suprime; o parser os separa e não suprime.
    Esse achado chega ao relatório por um caminho distinto dos outros dois — e jogá-lo para
    o fim, como o código fazia, desordenava 13% dos notebooks medidos.

    A indentação importa: é o formato que o Jupyter grava, e é o que faz os outros dois
    achados virem pelo caminho normal. Sem ela tudo cai na mesma linha bruta, todos viram
    sobra, e o defeito fica invisível — foi o que aconteceu com a primeira versão deste
    teste, que passava com e sem a correção.
    """
    outro = "AKIAI44QH8DHBEXAMPLE"
    terceiro = "AKIAZZZZZZZZ9EXAMPLE"
    nb = tmp_path / "n.ipynb"
    nb.write_text(
        json.dumps(
            {
                "cells": [
                    _code([f"k = '{AKIA}'\n# gitsafety: allow\n"]),
                    _code([f"k = '{outro}'\n"]),
                    _code([f"k = '{terceiro}'\n"]),
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            indent=1,
        ),
        encoding="utf-8",
    )

    celulas = [
        int(re.search(r"célula (\d+)", str(f.path)).group(1)) for f in scan_path(nb).findings
    ]

    assert len(celulas) == 3, celulas
    assert celulas == sorted(celulas), f"relatório fora da ordem do arquivo: {celulas}"

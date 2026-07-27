"""O oráculo de cobertura: parsear NUNCA pode achar menos que varrer como texto.

Esta é a propriedade que faltava no M4 e que deixou passar dez vetores de falso negativo.
O parsing existe para **localizar melhor**, jamais para **cobrir menos** — e a única forma
de garantir isso é afirmar a relação entre os dois caminhos, não enumerar os formatos que
lembramos de cobrir. Um formato novo do Jupyter é uma linha nova aqui, não um vazamento.
"""

from __future__ import annotations

import json

import pytest

from gitsafety.rules import BUILTIN_RULES
from gitsafety.scanner import _scan_text, scan_path

A = "AKIAIOSFODNN7EXAMPLE"


def _cell(**extra) -> dict:
    return {"cell_type": "code", "source": ["x = 1\n"], "outputs": [], "metadata": {}, **extra}


def _out(tipo: str, dados: dict) -> dict:
    return {"output_type": tipo, "data": dados, "metadata": {}}


#: Cada caso é um lugar REAL do formato onde o segredo pode estar e que a tabela de
#: extratores do M4 não cobria. Nomes descrevem o vetor, não o número.
CASOS = {
    "display_data_html": {
        "cells": [_cell(outputs=[_out("display_data", {"text/html": [f"<b>{A}</b>"]})])]
    },
    "execute_result_html": {
        "cells": [_cell(outputs=[_out("execute_result", {"text/html": [A]})])]
    },
    "data_json": {
        "cells": [_cell(outputs=[_out("display_data", {"application/json": {"k": A}})])]
    },
    "data_markdown": {"cells": [_cell(outputs=[_out("display_data", {"text/markdown": [A]})])]},
    "output_type_desconhecido": {
        "cells": [_cell(outputs=[_out("update_display_data", {"text/plain": [A]})])]
    },
    "output_sem_output_type": {"cells": [_cell(outputs=[{"data": {"text/plain": [A]}}])]},
    "metadata_do_notebook": {
        "cells": [_cell()],
        "metadata": {"papermill": {"parameters": {"k": A}}},
    },
    "metadata_da_celula": {"cells": [_cell(metadata={"tags": [A]})]},
    "attachments": {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["a\n"],
                "metadata": {},
                "attachments": {"n.txt": {"text/plain": [A]}},
            }
        ]
    },
    "v3_worksheets": {
        "nbformat": 3,
        "nbformat_minor": 0,
        "metadata": {},
        "worksheets": [
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "input": [f"k = '{A}'\n"],
                        "outputs": [],
                        "language": "python",
                    }
                ]
            }
        ],
    },
    "traceback_multilinha": {
        "cells": [
            _cell(
                outputs=[
                    {
                        "output_type": "error",
                        "ename": "E",
                        "evalue": "x",
                        "traceback": ["  chamada(", f"    token={A}", "ValueError: bad"],
                    }
                ]
            )
        ]
    },
}


@pytest.mark.parametrize("nome", sorted(CASOS))
def test_parsed_path_never_finds_less_than_text_path(nome, tmp_path):
    """Para todo notebook: achados(.ipynb) ⊇ achados(mesmo conteúdo como texto)."""
    bruto = json.dumps(CASOS[nome], indent=1)
    nb = tmp_path / "a.ipynb"
    nb.write_text(bruto, encoding="utf-8")

    parseado = {(f.rule_id, f.secret) for f in scan_path(nb).findings}
    texto = {(f.rule_id, f.secret) for f in _scan_text(bruto, nb, BUILTIN_RULES)}

    faltando = texto - parseado
    assert not faltando, f"{nome}: o caminho parseado perdeu {faltando}"


def test_control_secret_is_actually_present():
    """Controle: os casos precisam mesmo conter o segredo, senão o oráculo é vácuo."""
    for nome, doc in CASOS.items():
        assert A in json.dumps(doc), nome

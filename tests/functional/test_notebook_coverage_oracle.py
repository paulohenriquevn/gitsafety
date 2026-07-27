"""O oráculo de cobertura: parsear NUNCA pode achar menos que varrer como texto.

Esta é a propriedade que faltava no M4 e que deixou passar dez vetores de falso negativo.
O parsing existe para **localizar melhor**, jamais para **cobrir menos** — e a única forma
de garantir isso é afirmar a relação entre os dois caminhos, não enumerar os formatos que
lembramos de cobrir. Um formato novo do Jupyter é uma linha nova aqui, não um vazamento.
"""

from __future__ import annotations

import json
from collections import Counter

import pytest

from gitsafety.rules import BUILTIN_RULES
from gitsafety.scanner import _scan_text, scan_path

A = "AKIAIOSFODNN7EXAMPLE"


def unescape(secret: str) -> str:
    """Desfaz o escape JSON para comparar os dois lados.

    Vive no teste, não na produção: o arquivo bruto grafa `ã` como `\\u00e3` e o documento
    parseado traz o caractere. É a única diferença legítima entre as duas visões, e
    normalizá-la é o que torna a comparação justa. A produção não precisa disso desde que
    passou a ter um caminho só.
    """
    try:
        return json.loads(f'"{secret}"')
    except ValueError:
        return secret


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
    # Os três abaixo passaram a ser críticos quando a varredura de texto deixou de rodar em
    # runtime: sem a rede, é o percurso que precisa alcançá-los sozinho.
    "svg_e_texto": {
        "cells": [_cell(outputs=[_out("display_data", {"image/svg+xml": [f"<t>{A}</t>"]})])]
    },
    "segredo_como_chave": {"cells": [_cell(metadata={A: "valor"})]},
    "chave_e_valor_ambos_segredo": {"cells": [_cell(metadata={A: A})]},
    # Um vetor de `keyword_assignment` (nome da variável ao lado de um valor sem prefixo
    # próprio) foi tentado aqui e removido: o controle mostrou que ele é VAZIO, porque o
    # catálogo do M2 não tem nenhuma regra dessa família — nem o caminho de texto o
    # detectava. A lacuna está em `knowledge-base/backlog.md` § B2; quando for fechada, este
    # é o lugar do vetor, e `_collect` já emite `chave: valor` para sustentá-lo.
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

    # `Counter`, não `set`: comparar conjuntos esconde subcontagem — dois lugares com o
    # mesmo valor viram um elemento só, e foi por isso que este oráculo passou verde
    # enquanto uma ocorrência real era engolida pela fusão.
    parseado = Counter((f.rule_id, unescape(f.secret)) for f in scan_path(nb).findings)
    texto = Counter(
        (f.rule_id, unescape(f.secret)) for f in _scan_text(bruto, nb, BUILTIN_RULES)
    )

    faltando = texto - parseado
    assert not faltando, f"{nome}: o caminho parseado perdeu {faltando}"


@pytest.mark.parametrize("nome", sorted(CASOS))
def test_control_every_vector_is_non_vacuous(nome, tmp_path):
    """Controle: cada vetor precisa MESMO conter um segredo detectável.

    Um vetor sem segredo faria o oráculo passar por vacuidade — `texto - parseado` vazio
    porque `texto` está vazio. Afirmar sobre o caminho de texto, e não sobre a presença da
    string, é o controle que não pode ser burlado por um vetor mal montado.
    """
    bruto = json.dumps(CASOS[nome], indent=1)
    achados = _scan_text(bruto, tmp_path / "a.ipynb", BUILTIN_RULES)
    assert achados, f"{nome}: nenhum segredo detectável — o vetor não prova nada"

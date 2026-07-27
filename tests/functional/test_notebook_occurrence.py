"""Cada OCORRÊNCIA de segredo precisa de um achado — não cada valor distinto.

O oráculo de cobertura compara conjuntos e por isso não enxerga subcontagem: dois lugares
com o mesmo valor viram um elemento só. Estes testes afirmam a contagem, que é o que
importa na prática — o usuário remove o segredo do lugar reportado e o outro fica no
arquivo.
"""

from __future__ import annotations

import json

from gitsafety.scanner import scan_path

A = "AKIAIOSFODNN7EXAMPLE"
SENHA_ACENTUADA = "postgresql://app:senhãSup3r@db.exemplo.com/prod"


def _scan(tmp_path, doc):
    alvo = tmp_path / "a.ipynb"
    alvo.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return scan_path(alvo).findings


def _cell(**extra) -> dict:
    return {"cell_type": "code", "source": ["x = 1\n"], "outputs": [], "metadata": {}, **extra}


def test_split_value_plus_metadata_reports_both_occurrences(tmp_path):
    """O valor partido é invisível ao texto; o do metadata é invisível ao parser antigo.

    Reconciliar por valor fazia um consumir o outro: o usuário limpava a célula e a cópia
    nos parâmetros do papermill continuava no arquivo.
    """
    doc = {
        "cells": [_cell(source=["k = '" + A[:10], A[10:] + "'\n"])],
        "metadata": {"papermill": {"parameters": {"k": A}}},
    }
    assert len(_scan(tmp_path, doc)) == 2


def test_split_value_plus_cell_metadata_plus_attachment(tmp_path):
    doc = {
        "cells": [
            _cell(source=["k = '" + A[:10], A[10:] + "'\n"], metadata={"tags": [A]}),
            {
                "cell_type": "markdown",
                "source": ["a\n"],
                "metadata": {},
                "attachments": {"n.txt": {"text/plain": [A]}},
            },
        ]
    }
    assert len(_scan(tmp_path, doc)) == 3


def test_same_secret_in_two_cells_reports_twice(tmp_path):
    """Controle: a contagem por ocorrência não pode colapsar dois lugares reais."""
    doc = {"cells": [_cell(source=[f"a = '{A}'\n"]), _cell(source=[f"b = '{A}'\n"])]}
    assert len(_scan(tmp_path, doc)) == 2


def test_inline_marker_works_when_the_line_is_split(tmp_path):
    """A supressão pedida pelo usuário não pode ser desfeita pela fusão.

    O parser junta os elementos, vê o marcador e suprime. O texto vê o segredo numa linha
    do JSON onde o marcador não está — e reintroduzia o achado.
    """
    doc = {"cells": [_cell(source=["exemplo = '" + A + "'", "  # gitsafety: allow\n"])]}
    assert _scan(tmp_path, doc) == []


def test_escaped_unicode_is_not_reported_twice(tmp_path):
    """`json.dumps` grava `ã` como `\\u00e3`; o texto e o parser viam strings diferentes.

    O resultado era a mesma ocorrência contada duas vezes, uma delas exibindo um valor
    que não existe em lugar nenhum do arquivo.
    """
    doc = {"cells": [_cell(source=[f"d = '{SENHA_ACENTUADA}'\n"])]}
    achados = _scan(tmp_path, doc)
    assert len(achados) == 1, [f.secret for f in achados]
    # O valor reportado é o que existe no documento, não a grafia do JSON.
    assert "senhãSup3r" in achados[0].secret
    assert "\\u00e3" not in achados[0].secret


def test_secret_in_notebook_metadata_is_localised(tmp_path):
    """Metadado do notebook não pertence a célula nenhuma — a localização tem de dizer isso."""
    doc = {"cells": [_cell()], "metadata": {"papermill": {"parameters": {"k": A}}}}
    achados = _scan(tmp_path, doc)
    assert len(achados) == 1
    assert "célula" not in str(achados[0].path)
    assert "metadados" in str(achados[0].path)

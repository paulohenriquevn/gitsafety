"""Fuzz diferencial: gera notebooks válidos e exige que a varredura não perca nada.

**Por que fuzz e não uma lista de vetores.** Três vezes neste milestone uma lista foi
declarada completa e não era: a tabela de `output_type`, a lista de mime-types, o conjunto
de supressão. Uma lista testa o que alguém lembrou; o defeito mora exatamente no que
ninguém lembrou. O gerador produz formas que ninguém enumerou, e a propriedade que ele
verifica não depende de enumeração nenhuma:

    achados(`a.ipynb`) ⊇ achados(mesmo conteúdo varrido como texto)

A varredura de texto é a especificação executável da cobertura — é o comportamento que os
quatro milestones anteriores já entregavam, e nenhum notebook pode fazer o produto regredir
abaixo dele. O parser existe para localizar melhor, nunca para cobrir menos.

O gerador **não** planta `# gitsafety: allow`. A propriedade é sobre cobertura, e a
supressão é a única razão legítima para reportar menos que o texto — o parser enxerga um
marcador que o Jupyter separou do segredo ao quebrar a linha, e o texto não. Misturar as
duas coisas faria a propriedade acusar como perda um comportamento pedido pelo usuário.
A semântica da supressão é verificada em `test_notebook_occurrence.py`.

Determinístico por construção: `Random(semente)` com sementes fixas. Um fuzz que muda a cada
execução transforma falha em ruído intermitente (`rules/testing.md § 3`).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from random import Random

import pytest

from gitsafety.notebook import unescape
from gitsafety.rules import BUILTIN_RULES
from gitsafety.scanner import _scan_text, scan_path

#: Segredos com prefixo literal, um por família, para o gerador plantar.
SEGREDOS = (
    "AKIAIOSFODNN7EXAMPLE",
    "ghp_" + "a" * 36,
    "ghp_" + "b" * 36,
    "postgresql://app:s3nh4@db.exemplo.com/prod",
    "postgresql://app:senhãSup3r@db.exemplo.com/prod",
)

#: Chaves de mime deliberadamente variadas, incluindo as que o percurso pula.
MIMES = ("text/plain", "text/html", "application/json", "image/png", "image/svg+xml")

#: Sufixos de elemento. O vazio é o que apaga o delimitador entre dois tokens ao juntar,
#: e foi o defeito que sozinho explicava 70% das perdas numa rodada de revisão.
SUFIXOS = ("", "\n", " ", ",")


def _valor(rng: Random, segredo: str) -> object:
    """Um valor de forma variada carregando o segredo."""
    forma = rng.randrange(6)
    sufixo = rng.choice(SUFIXOS)
    if forma == 0:
        return f"k = '{segredo}'{sufixo}"
    if forma == 1:
        return [f"k = '{segredo}'{sufixo}"]
    if forma == 2:  # partido entre elementos — visível só ao parser
        corte = len(segredo) // 2
        return [f"k = '{segredo[:corte]}", f"{segredo[corte:]}'{sufixo}"]
    if forma == 3:  # dois tokens adjacentes — o caso do delimitador
        return [f"{segredo}{sufixo}", f"{rng.choice(SEGREDOS)}{sufixo}"]
    if forma == 4:
        return {"aninhado": [{"mais": f"{segredo}{sufixo}"}]}
    return segredo


def _saida(rng: Random, segredo: str) -> dict:
    tipo = rng.choice(("stream", "execute_result", "display_data", "error", "desconhecido"))
    if tipo == "stream":
        return {"output_type": "stream", "name": "stdout", "text": _valor(rng, segredo)}
    if tipo == "error":
        return {
            "output_type": "error",
            "ename": "ValueError",
            "evalue": "erro",
            "traceback": [f"  chamada({segredo})", "ValueError: bad"],
        }
    return {
        "output_type": tipo,
        "data": {rng.choice(MIMES): _valor(rng, segredo)},
        "metadata": {},
    }


def _celula(rng: Random) -> object:
    if rng.randrange(20) == 0:  # item de forma inesperada
        return f"solto {rng.choice(SEGREDOS)}"

    celula: dict = {"cell_type": rng.choice(("code", "markdown", "raw")), "metadata": {}}
    celula[rng.choice(("source", "input"))] = _valor(rng, rng.choice(SEGREDOS))

    if rng.randrange(3) == 0:
        celula["outputs"] = [
            _saida(rng, rng.choice(SEGREDOS)) for _ in range(rng.randrange(1, 3))
        ]
    if rng.randrange(4) == 0:
        celula["metadata"] = {rng.choice(SEGREDOS): "valor"}
    if rng.randrange(5) == 0:
        celula["attachments"] = {"n.txt": {"text/plain": [rng.choice(SEGREDOS)]}}
    return celula


def _notebook(semente: int) -> str:
    rng = Random(semente)
    documento: dict = {
        "cells": [_celula(rng) for _ in range(rng.randrange(1, 5))],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    if rng.randrange(3) == 0:
        documento["metadata"] = {"papermill": {"parameters": {"k": rng.choice(SEGREDOS)}}}
    if rng.randrange(10) == 0:  # v3: células dentro de worksheets
        documento = {
            "nbformat": 3,
            "nbformat_minor": 0,
            "metadata": documento["metadata"],
            "worksheets": [{"cells": documento["cells"]}],
        }
    return json.dumps(documento, indent=1)


@pytest.mark.parametrize("semente", range(300))
def test_notebook_scan_never_loses_what_the_text_scan_finds(semente, tmp_path):
    """A propriedade que nenhum formato novo pode quebrar."""
    bruto = _notebook(semente)
    alvo = tmp_path / "a.ipynb"
    alvo.write_text(bruto, encoding="utf-8")

    obtido = Counter((f.rule_id, unescape(f.secret)) for f in scan_path(alvo).findings)
    esperado = Counter(
        (f.rule_id, unescape(f.secret)) for f in _scan_text(bruto, Path("a.txt"), BUILTIN_RULES)
    )

    faltando = esperado - obtido
    assert not faltando, f"semente {semente}: perdeu {dict(faltando)}\n{bruto}"


def test_the_generator_actually_plants_secrets():
    """Controle: um gerador que não planta segredo faria o fuzz passar por vacuidade."""
    com_achado = sum(
        1
        for semente in range(300)
        if _scan_text(_notebook(semente), Path("a.txt"), BUILTIN_RULES)
    )
    assert com_achado > 250, f"só {com_achado}/300 documentos têm segredo detectável"

"""T3.1 — o que o parsing de notebook custa, comparado a varrer o mesmo arquivo como texto.

`json.loads` sobre um documento grande é mais caro que iterar linhas, e notebooks são
grandes. Sem medir, "parsear é melhor" é preferência, não engenharia.

O que interessa é a **razão** entre os dois caminhos, não o valor absoluto: a razão é o que
decide se o ganho de localização paga. O teto de 5× vem da Unresolved Question Q3 do plano.

A medição é **pareada** — o mesmo arquivo, os mesmos 53 padrões, variando só o caminho de
código. Comparar notebook parseado com um `.py` diferente mediria o conteúdo, não o método.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from gitsafety.rules import BUILTIN_RULES
from gitsafety.scanner import _scan_text, scan_path

#: Uma célula de notebook de análise real: importe, chamada, e uma saída de algumas linhas.
_CELULA_FONTE = [
    "import pandas as pd\n",
    "df = pd.read_parquet('s3://bucket/eventos.parquet')\n",
    "resumo = df.groupby('categoria').agg({'valor': ['sum', 'mean', 'count']})\n",
    "resumo.sort_values(('valor', 'sum'), ascending=False).head(20)\n",
]
_CELULA_SAIDA = "".join(
    f"  categoria_{i:03d}   {i * 137.5:12.2f}   {i * 3:6d}\n" for i in range(20)
)


def _build_notebook(n_cells: int) -> str:
    """Notebook realista: muitas células, saídas longas.

    Um notebook de três células mediria o custo de importar `json`, não o do parsing.
    """
    celulas = [
        {
            "cell_type": "code",
            "source": _CELULA_FONTE,
            "outputs": [{"output_type": "stream", "name": "stdout", "text": [_CELULA_SAIDA]}],
            "execution_count": i + 1,
            "metadata": {},
        }
        for i in range(n_cells)
    ]
    documento = {"cells": celulas, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    # `indent=1` é o que o Jupyter grava. Sem ele, `json.dumps` produz **uma linha só**, e o
    # caminho de texto pagaria 53 regexes sobre uma linha de 240 KB — um adversário fraco que
    # faria o parsing parecer melhor do que é. O arquivo medido tem de ser o arquivo real.
    return json.dumps(documento, indent=1)


def _melhor(fn, rounds: int) -> float:
    """O menor tempo entre as rodadas — o menos contaminado por ruído da máquina."""
    return min(_cronometrar(fn) for _ in range(rounds))


def _cronometrar(fn) -> float:
    inicio = time.perf_counter()
    fn()
    return time.perf_counter() - inicio


def measure_notebook(n_cells: int, rounds: int = 3) -> dict[str, float]:
    """Mede os dois caminhos sobre o **mesmo** notebook.

    `parsed_s` percorre `scan_path`, que bifurca por extensão. `text_s` chama `_scan_text`
    diretamente sobre o mesmo conteúdo — é exatamente o que o v0.4.0 fazia.
    """
    bruto = _build_notebook(n_cells)

    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "analise.ipynb"
        alvo.write_text(bruto, encoding="utf-8")

        parsed_s = _melhor(lambda: scan_path(alvo), rounds)
        text_s = _melhor(lambda: _scan_text(bruto, alvo, BUILTIN_RULES), rounds)

    return {
        "n_cells": float(n_cells),
        "bytes": float(len(bruto)),
        "parsed_s": parsed_s,
        "text_s": text_s,
        "ratio": parsed_s / text_s if text_s else float("inf"),
    }


def main() -> None:
    print(f"{'células':>8}  {'bytes':>9}  {'parseado':>10}  {'texto':>10}  {'razão':>7}")
    for n in (20, 50, 100, 200):
        m = measure_notebook(n)
        print(
            f"{int(m['n_cells']):>8}  {int(m['bytes']):>9}  "
            f"{m['parsed_s']:>9.4f}s  {m['text_s']:>9.4f}s  {m['ratio']:>6.2f}×"
        )


if __name__ == "__main__":
    main()

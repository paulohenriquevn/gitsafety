"""Benchmark de escala do catálogo — 1 regra vs. o catálogo inteiro.

O M0 mediu ~69.000 arquivos/s com **uma** regra. O motor aplica cada regra a cada linha,
então o custo poderia ser linear no número de regras: com 53, a varredura ficaria 53×
mais lenta e o overhead do hook (0,04 s medido no M1) subiria para perto do teto de 1 s
do `docs/PRD.md § NFR-2`.

**Este é o gargalo do M2, e a pergunta é falsificável:** se o custo por regra for
constante, o pré-filtro por palavra-chave se justifica; se a travessia de arquivo
dominar, o número de regras quase não importa e o pré-filtro é YAGNI
(Unresolved Question Q3 do plano).

Reusa o corpus do M0 para que os números sejam comparáveis com aquele milestone.

    python benchmarks/bench_catalog.py
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from benchmarks.bench_scan import build_corpus
from gitsafety.rules import BUILTIN_RULES
from gitsafety.scanner import scan_path


def measure_with_n_rules(root: Path, n_rules: int, rounds: int = 3) -> dict[str, float]:
    """Mede a varredura usando as `n_rules` primeiras regras do catálogo."""
    regras = BUILTIN_RULES[:n_rules]

    scan_path(root, regras)  # aquecimento: a primeira leitura mede o cache do SO

    tempos: list[float] = []
    for _ in range(rounds):
        inicio = time.perf_counter()
        resultado = scan_path(root, regras)
        tempos.append(time.perf_counter() - inicio)

    total = sum(tempos) / len(tempos)
    return {
        "n_rules": float(n_rules),
        "total_s": round(total, 4),
        "findings": float(len(resultado.findings)),
    }


def main() -> int:
    n_files = 1000
    todas = len(BUILTIN_RULES)

    with tempfile.TemporaryDirectory(prefix="gitsafety-bench-cat-") as tmp:
        raiz = Path(tmp)
        print(f"Gerando corpus: {n_files} arquivos (o mesmo do M0)…")
        build_corpus(raiz, n_files=n_files, secrets_every=100)

        print()
        print("=== gitsafety — escala do catálogo ===")
        print(f"  corpus: {n_files} arquivos · catálogo: {todas} regras")
        print()

        medidas = []
        for n in (1, 10, todas):
            m = measure_with_n_rules(raiz, n)
            medidas.append(m)
            print(f"  {n:>3} regra(s): {m['total_s']:.4f} s   ({int(m['findings'])} findings)")

        base, cheio = medidas[0], medidas[-1]
        fator_regras = todas / 1
        fator_tempo = cheio["total_s"] / base["total_s"] if base["total_s"] else 0.0
        marginal_ms = (cheio["total_s"] - base["total_s"]) / (todas - 1) * 1000

        print()
        print(f"  regras multiplicadas por : {fator_regras:.0f}×")
        print(f"  tempo multiplicado por   : {fator_tempo:.1f}×")
        print(f"  custo marginal por regra : {marginal_ms:.3f} ms / {n_files} arquivos")
        print()
        if fator_tempo < fator_regras / 4:
            print("  → a travessia domina; pré-filtro por palavra-chave é YAGNI")
        else:
            print("  → o custo escala com o número de regras; pré-filtro se justifica")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

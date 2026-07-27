"""Benchmark do custo de carregar a config (M3 T3.1).

A carga tem duas parcelas de forma diferente: o parse do YAML é ~constante, e a
validação de cada regra do usuário (compilar + analisar + sondar) é linear no número de
regras. Medir com 0, 10 e 50 separa as duas.

O número que importa é o **somado ao overhead do hook**: o M1 mediu ~40 ms de custo por
commit, e o `docs/PRD.md § NFR-2` dá 1 s de teto.

    python -m benchmarks.bench_config
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from gitsafety.config import CONFIG_FILENAME, load_config


def write_config(root: Path, n_user_rules: int) -> None:
    linhas = []
    if n_user_rules:
        linhas.append("rules:")
        for i in range(n_user_rules):
            linhas.append(f"  - id: regra-{i:03d}")
            linhas.append(f'    pattern: "PREFIX{i:03d}_[A-Z0-9]{{10,20}}"')
    else:
        linhas.append("ignore:\n  - '*.lock'")
    (root / CONFIG_FILENAME).write_text("\n".join(linhas) + "\n", encoding="utf-8")


def measure_load(n_user_rules: int, rounds: int = 5) -> dict[str, float]:
    with tempfile.TemporaryDirectory(prefix="gitsafety-bench-cfg-") as tmp:
        raiz = Path(tmp)
        write_config(raiz, n_user_rules)

        load_config(start=raiz)  # aquecimento: paga o import do yaml

        tempos = []
        for _ in range(rounds):
            inicio = time.perf_counter()
            load_config(start=raiz)
            tempos.append(time.perf_counter() - inicio)

    return {
        "n_user_rules": float(n_user_rules),
        "total_s": round(sum(tempos) / len(tempos), 5),
    }


def main() -> int:
    print("=== gitsafety — custo de carregar a configuração ===")
    print()
    medidas = [measure_load(n) for n in (0, 10, 50)]
    for m in medidas:
        print(f"  {int(m['n_user_rules']):>2} regras de usuário: {m['total_s'] * 1000:7.3f} ms")

    base, cheio = medidas[0], medidas[-1]
    marginal_ms = (cheio["total_s"] - base["total_s"]) / 50 * 1000
    print()
    print(f"  custo marginal por regra do usuário: {marginal_ms:.4f} ms")
    print(f"  somado ao overhead do hook (M1: ~40 ms): ~{40 + cheio['total_s'] * 1000:.1f} ms")
    print("  teto do NFR-2: 1000 ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

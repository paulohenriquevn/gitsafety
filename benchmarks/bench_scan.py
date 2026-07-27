"""Benchmark de varredura — mede latência com corpus determinístico.

Roda direto:

    python benchmarks/bench_scan.py

O corpus é gerado em disco a cada execução, sem aleatoriedade, para que o número seja
comparável entre máquinas e entre milestones. Três métricas são reportadas; a que
importa entre milestones é `files_per_s`, porque não depende do tamanho do corpus.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from gitsafety.scanner import scan_path

#: Chave AWS de exemplo da documentação da própria AWS — não é credencial real.
SAMPLE_SECRET = "AKIAIOSFODNN7EXAMPLE"

_FILLER = "def funcao_{i}():\n    return {i} * 2\n\n" * 4


def build_corpus(root: Path, n_files: int, secrets_every: int) -> None:
    """Gera `n_files` arquivos, com um segredo a cada `secrets_every`.

    Determinístico de propósito: conteúdo derivado apenas do índice. Corpus aleatório
    tornaria a medição não comparável entre execuções, que é justamente o que um
    benchmark precisa oferecer.

    Os arquivos são distribuídos em subdiretórios para exercer a travessia recursiva,
    e não só a leitura sequencial de um diretório plano.
    """
    root = Path(root)
    for i in range(n_files):
        sub = root / f"pacote_{i // 50:03d}"
        sub.mkdir(parents=True, exist_ok=True)
        corpo = _FILLER.format(i=i)
        if secrets_every and i % secrets_every == 0:
            corpo += f'CHAVE = "{SAMPLE_SECRET}"\n'
        (sub / f"modulo_{i:04d}.py").write_text(corpo, encoding="utf-8")


def measure(root: Path) -> dict[str, float]:
    """Mede uma varredura completa de `root`.

    Usa `perf_counter`, que é monotônico e imune a ajuste de relógio do sistema —
    `time.time()` pode andar para trás e produzir duração negativa.
    """
    inicio = time.perf_counter()
    resultado = scan_path(root)
    total_s = time.perf_counter() - inicio

    # Contado fora da região cronometrada, para não somar ao tempo medido.
    n_arquivos = _count_scanned(root)

    return {
        "total_s": round(total_s, 4),
        "per_file_ms": round((total_s / n_arquivos) * 1000, 4) if n_arquivos else 0.0,
        "files_per_s": round(n_arquivos / total_s, 1) if total_s else 0.0,
        "files_scanned": float(n_arquivos),
        "findings": float(len(resultado.findings)),
    }


def _count_scanned(root: Path) -> int:
    from gitsafety.walker import walk

    arquivos, _ = walk(Path(root))
    return len(arquivos)


def main() -> int:
    n_files, secrets_every = 1000, 100

    with tempfile.TemporaryDirectory(prefix="gitsafety-bench-") as tmp:
        raiz = Path(tmp)
        print(f"Gerando corpus: {n_files} arquivos, 1 segredo a cada {secrets_every}...")
        build_corpus(raiz, n_files=n_files, secrets_every=secrets_every)

        # Uma passada de aquecimento: a primeira leitura paga o cache de página do SO
        # e mediria o disco, não o scanner.
        scan_path(raiz)

        metricas = measure(raiz)

    print()
    print("=== gitsafety — benchmark de varredura ===")
    print(f"  arquivos varridos : {int(metricas['files_scanned'])}")
    print(f"  segredos achados  : {int(metricas['findings'])}")
    print(f"  total_s           : {metricas['total_s']} s")
    print(f"  per_file_ms       : {metricas['per_file_ms']} ms/arquivo")
    print(f"  files_per_s       : {metricas['files_per_s']} arquivos/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

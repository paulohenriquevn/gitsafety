"""Benchmark do hook — mede o custo que o gitsafety impõe ao `git commit`.

O M0 mediu a varredura (0,0145 ms por arquivo) e **concluiu por hipótese** que o custo
dominante do M1 seria o startup do interpretador. Este benchmark falsifica ou confirma
essa hipótese com medição.

O que se mede é a **diferença pareada**: `git commit` com o hook instalado menos
`git commit` sem ele, no mesmo repositório e com o mesmo conteúdo. Medir só
`scan --staged` mediria de novo a varredura, que o M0 já sabe ser irrelevante.

    python benchmarks/bench_hook.py
"""

from __future__ import annotations

import os
import subprocess
import sysconfig
import tempfile
import time
from pathlib import Path

SAMPLE_SECRET = "AKIAIOSFODNN7EXAMPLE"


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> int:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    ).returncode


def _scripts_on_path(path: str | None = None) -> str:
    base = os.environ.get("PATH", "") if path is None else path
    return f"{sysconfig.get_path('scripts')}{os.pathsep}{base}"


def _env_with_gitsafety() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = _scripts_on_path()
    return env


def ensure_gitsafety_on_path() -> None:
    """Satisfaz a pré-condição do ADR D8 no processo do benchmark.

    `install_hook` verifica o PATH **do processo atual** — de propósito, porque é ele que
    o usuário terá quando commitar. O benchmark precisa montar a mesma pré-condição que
    um usuário real monta ao ativar o ambiente; sem isso ele mediria a mensagem de erro.
    """
    os.environ["PATH"] = _scripts_on_path()


def make_repo(root: Path) -> Path:
    repo = root / "bench"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True
    )
    _git(repo, "config", "user.email", "bench@exemplo.invalid")
    _git(repo, "config", "user.name", "Benchmark")
    return repo


def stage_files(repo: Path, n_files: int) -> None:
    """Prepara N arquivos no índice, todos limpos.

    Limpos de propósito: um commit bloqueado sai por caminho diferente e mediria outra
    coisa. O que interessa é o custo no **fluxo normal**, que é o que o usuário paga
    todo dia.
    """
    for i in range(n_files):
        (repo / f"modulo_{i:03d}.py").write_text(
            f"def funcao_{i}():\n    return {i} * 2\n", encoding="utf-8"
        )
    _git(repo, "add", ".")


def time_commit(repo: Path, message: str, env: dict[str, str]) -> float:
    inicio = time.perf_counter()
    _git(repo, "commit", "-q", "-m", message, env=env)
    return time.perf_counter() - inicio


def measure_pair(n_files: int, rounds: int = 3) -> dict[str, float]:
    """Mede commit sem hook e com hook, alternando, e devolve as médias.

    Alterna as duas condições em vez de rodar todas de um lado e depois do outro: assim
    uma variação de carga da máquina no meio da execução contamina as duas medições por
    igual, em vez de enviesar uma delas.
    """
    from gitsafety.hook import install_hook

    ensure_gitsafety_on_path()
    env = _env_with_gitsafety()
    sem: list[float] = []
    com: list[float] = []

    for rodada in range(rounds):
        with tempfile.TemporaryDirectory(prefix="gitsafety-bench-") as tmp:
            repo = make_repo(Path(tmp))
            stage_files(repo, n_files)
            sem.append(time_commit(repo, f"sem hook {rodada}", env))

        with tempfile.TemporaryDirectory(prefix="gitsafety-bench-") as tmp:
            repo = make_repo(Path(tmp))
            install_hook(repo)
            stage_files(repo, n_files)
            com.append(time_commit(repo, f"com hook {rodada}", env))

    media_sem = sum(sem) / len(sem)
    media_com = sum(com) / len(com)
    return {
        "without_hook_s": round(media_sem, 4),
        "with_hook_s": round(media_com, 4),
        "overhead_s": round(media_com - media_sem, 4),
        "files": float(n_files),
    }


def main() -> int:
    print("=== gitsafety — benchmark do hook de pre-commit ===")
    print()
    for n in (1, 20, 200):
        m = measure_pair(n_files=n, rounds=3)
        print(f"  commit de {n:>3} arquivo(s):")
        print(f"    sem hook  : {m['without_hook_s']:.4f} s")
        print(f"    com hook  : {m['with_hook_s']:.4f} s")
        print(f"    overhead  : {m['overhead_s']:.4f} s")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

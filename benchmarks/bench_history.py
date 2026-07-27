"""T4.1 — o que custa varrer o histórico.

A descoberta mediu o **git** em 0,115 s para 5.000 commits. Falta o custo do nosso parsing
e das 53 regras sobre as ~80.000 linhas que ele devolve. Sem esse número, o Risco M5 nº 1
("repositório grande tornar o comando lento a ponto de ninguém rodar") continua sem resposta.

A medição separa `git_s` de `scan_s` porque saber **qual domina** é o que decide onde
otimizar, se um dia for preciso. Um número agregado esconderia exatamente essa informação.

**Este benchmark é um piso, não uma previsão.** As linhas geradas são curtas e uniformes
(~10 caracteres); as de um repositório real têm mediana 42 e conteúdo variado, e o custo de
uma regex cresce com o comprimento. Medido no próprio repositório do gitsafety — 51 commits,
74 mil linhas adicionadas — a varredura leva ~6 s, contra ~0,6 s que este gerador produz
para volume comparável. O número honesto para expectativa de usuário é o do repositório
real; este serve para detectar **regressão de ordem de grandeza** entre versões.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from gitsafety.history import history_diff, scan_history

#: Um segredo a cada N commits — um histórico realista tem poucos, não um por commit.
_A_CADA = 250


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _build_repo(repo: Path, n_commits: int, linhas_por_commit: int = 2) -> None:
    """Histórico sintético: 50 arquivos girando, com segredos esparsos.

    `linhas_por_commit` existe porque a primeira versão media 2 linhas por commit e
    produzia um número bonito e irrelevante: 5.000 commits em 0,24 s. O repositório real do
    gitsafety, com 51 commits, leva ~10 s — porque o custo é **linhas × regras**, e commits
    reais alteram dezenas de linhas, não duas. Medir o eixo errado é pior que não medir.
    """
    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "user.email", "bench@exemplo.com")
    _git(repo, "config", "user.name", "Bench")

    for i in range(n_commits):
        alvo = repo / f"f{i % 50}.py"
        corpo = "".join(f"x{j} = {i * 1000 + j}\n" for j in range(linhas_por_commit))
        if i % _A_CADA == 0:
            # O formato da chave AWS é `AKIA` + 16 caracteres, e o delimitador de fim do
            # padrão recusa qualquer coisa colada depois. Variar DENTRO dos 16 é o que
            # mantém cada segredo distinto e detectável; concatenar o índice ao fim gerava
            # um valor que nenhuma regra casava — e um benchmark de varredura que não acha
            # nada mede a metade errada do trabalho.
            corpo += f"AWS = 'AKIA{i:016d}'\n"
        alvo.write_text(corpo, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "--no-verify", "-m", f"c{i}")


def _melhor(fn, rounds: int) -> float:
    melhor = float("inf")
    for _ in range(rounds):
        inicio = time.perf_counter()
        fn()
        melhor = min(melhor, time.perf_counter() - inicio)
    return melhor


def measure_history(
    n_commits: int, rounds: int = 3, linhas_por_commit: int = 2
) -> dict[str, float]:
    """Mede o git e a varredura completa sobre o mesmo repositório."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _build_repo(repo, n_commits, linhas_por_commit)

        git_s = _melhor(lambda: history_diff(repo), rounds)
        total_s = _melhor(lambda: scan_history(repo), rounds)
        achados = len(scan_history(repo))
        linhas = len(history_diff(repo).splitlines())

    esperado = (n_commits + _A_CADA - 1) // _A_CADA
    if achados != esperado:
        # Falha alto: um benchmark que varre e não acha nada mede o caminho vazio, e o
        # número resultante parece bom justamente por estar errado.
        raise AssertionError(
            f"o gerador plantou {esperado} segredos e a varredura achou {achados}"
        )

    return {
        "commits": float(n_commits),
        "git_s": git_s,
        # O que sobra depois do git: parsing dos commits, do diff, e as 53 regras.
        "scan_s": total_s - git_s,
        "total_s": total_s,
        "linhas": float(linhas),
        "achados": float(achados),
    }


def main() -> None:
    colunas = ("commits", "linhas", "git", "varredura", "total", "achados")
    print("  ".join(f"{c:>9}" for c in colunas))
    # O eixo que importa é LINHAS, não commits: (commits, linhas por commit).
    for n, lpc in ((100, 2), (1000, 2), (5000, 2), (500, 50), (1000, 50)):
        m = measure_history(n, linhas_por_commit=lpc)
        valores = (
            f"{int(m['commits']):>9}",
            f"{int(m['linhas']):>9}",
            f"{m['git_s']:>8.3f}s",
            f"{m['scan_s']:>8.3f}s",
            f"{m['total_s']:>8.3f}s",
            f"{int(m['achados']):>9}",
        )
        print("  ".join(valores))


if __name__ == "__main__":
    main()

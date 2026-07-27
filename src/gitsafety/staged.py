"""Varredura do índice do git — só o que está sendo introduzido (ADR D1).

O comando e as flags vêm de dois peers que convergem:
`knowledge-base/references/gitleaks/sources/git.go:139-142` e
`knowledge-base/references/talisman/gitrepo/gitrepo.go:47`.

**A decisão de produto é maior que a técnica.** `git diff --staged` devolve apenas as
linhas *adicionadas*, não o arquivo inteiro. O hook reclama do que você **introduz**, e
não de segredo preexistente num arquivo que você por acaso tocou. Varrer o arquivo todo
faria a adoção em repositório legado bloquear todo commit até alguém limpar o histórico —
e o hook seria desinstalado na primeira semana. Como a north-star do `ROADMAP.md` é
retenção, essa diferença é existencial.

Segredo preexistente é trabalho do `scan` completo e do `--history` (M5).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from gitsafety.finding import Finding
from gitsafety.git import run_git
from gitsafety.rules import BUILTIN_RULES, Rule
from gitsafety.scanner import ScanResult, is_allowed

if TYPE_CHECKING:  # evita ciclo em runtime; `config` importa deste módulo
    from gitsafety.config import Config

#: `@@ -a,b +c,d @@` — `c` é a primeira linha do lado NOVO, que é o que numeramos.
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,\d+)? @@")

#: `+++ b/caminho` — o nome do arquivo novo. Vem do lado `+++` porque arquivo recém-criado
#: tem `--- /dev/null` do lado antigo.
_NEW_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>.+)$")


@dataclass(frozen=True)
class AddedLine:
    """Uma linha que está sendo introduzida no commit."""

    path: Path
    line: int  # 1-based, no arquivo novo
    text: str


def staged_diff(cwd: Path) -> str:
    """Devolve o diff do índice contra HEAD.

    Cada flag é defensiva:

    - ``--staged``      diferença entre índice e HEAD — o que será commitado, não o disco.
    - ``-U0``           zero linhas de contexto: sem isso, linhas inalteradas ao redor
                        entrariam na varredura e gerariam achado em código não tocado.
    - ``--no-ext-diff`` ignora o driver de diff externo do usuário, que poderia emitir
                        saída arbitrária e quebrar o parsing.
    - ``--src-prefix``/``--dst-prefix`` forçam os prefixos padrão contra um
                        ``diff.noprefix=true`` na config, que quebraria os cabeçalhos.
    """
    return run_git(
        [
            "diff",
            "--staged",
            "-U0",
            "--no-ext-diff",
            "--src-prefix=a/",
            "--dst-prefix=b/",
        ],
        cwd=cwd,
    )


def parse_added_lines(diff: str) -> list[AddedLine]:
    """Extrai as linhas adicionadas de um diff unificado, com o número no arquivo novo.

    A aritmética é a parte delicada: o contador começa no `c` do cabeçalho de hunk e
    avança **apenas** em linhas adicionadas. Com ``-U0`` não há linhas de contexto, e
    linhas removidas não existem no arquivo novo — avançar nelas deslocaria todos os
    números seguintes.
    """
    linhas: list[AddedLine] = []
    caminho_atual: Path | None = None
    numero = 0

    for raw in diff.splitlines():
        novo_arquivo = _NEW_FILE_RE.match(raw)
        if novo_arquivo:
            alvo = novo_arquivo.group("path")
            # `/dev/null` do lado `+++` significa arquivo deletado: nada a varrer.
            caminho_atual = None if alvo == "/dev/null" else Path(alvo)
            continue

        hunk = _HUNK_RE.match(raw)
        if hunk:
            numero = int(hunk.group("start"))
            continue

        if caminho_atual is None:
            continue

        if raw.startswith("+"):
            linhas.append(AddedLine(path=caminho_atual, line=numero, text=raw[1:]))
            numero += 1

    return linhas


def _is_ignored_path(path: Path, ignore) -> bool:
    """`ignore` no modo staged: o caminho do diff já é relativo à raiz do repositório."""
    import fnmatch

    return any(fnmatch.fnmatch(path.as_posix(), padrao) for padrao in ignore)


def scan_staged(
    cwd: Path,
    rules: Sequence[Rule] = BUILTIN_RULES,
    *,
    config: Config | None = None,
) -> ScanResult:
    """Varre o índice e devolve o mesmo `ScanResult` do `scan` de arquivos (ADR D9).

    Reusar o tipo é o que garante que `cli.render` mascare o segredo neste caminho sem
    nenhuma linha nova — o mascaramento mora no `Finding` justamente para que um caminho
    de saída novo não possa esquecê-lo.

    `skipped` é sempre vazio aqui: o git já decide o que entra no diff, então não há
    decisão de pulo nossa a reportar.
    """
    from gitsafety.config import Config, effective_rules

    cfg = config if config is not None else Config()
    regras = effective_rules(cfg, rules)

    findings: list[Finding] = []

    for adicionada in parse_added_lines(staged_diff(cwd)):
        if _is_ignored_path(adicionada.path, cfg.ignore):
            continue
        for rule in regras:
            for match in rule.pattern.finditer(adicionada.text):
                # O hook é onde o falso positivo dói mais — a config precisa valer aqui
                # tanto quanto no `scan` (Unresolved Question Q3 do plano do M3).
                if is_allowed(match.group(0), adicionada.text, cfg.allow):
                    continue
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        path=adicionada.path,
                        line=adicionada.line,
                        secret=match.group(0),
                    )
                )

    return ScanResult(findings=findings, skipped=[])

"""Travessia do sistema de arquivos, com pulos reportados (ADRs D1 e D3).

Duas decisões carregam este módulo:

**D1 — classificação por extensão, nunca por conteúdo.** Os dois peers legíveis
convergem: ggshield compara sufixo contra um conjunto
(`utils/files.py:131-134`), gitleaks delega ao git (`sources/git.go:329`). Sniffing de
byte NUL é o risco nº 2 do `ROADMAP.md § M0` e erra em UTF-16.

**D3 — o pulo é valor de retorno, não efeito colateral.** `walk()` devolve
`(files, skipped)`, seguindo `ggshield/core/scan/file.py:69-77`. O D1 admite que a
heurística erra; o que impede o erro de virar falso negativo silencioso é o pulo
aparecer no resultado.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from gitsafety._binary_extensions import BINARY_EXTENSIONS
from gitsafety.errors import PathNotFoundError

#: Limite de tamanho, em bytes. Fixo — sem flag, per `docs/API.md § Superfície da CLI`
#: (teto de 4 flags) e ADR D4 (nada configurável sem caso de uso). O gitleaks oferece
#: `--max-target-megabytes` (`cmd/root.go:292`) e o deixa **desligado** por padrão;
#: nós preferimos um default sensato a um knob desligado que ninguém liga.
MAX_FILE_BYTES = 1_000_000


class SkipReason(str, Enum):
    """Por que um arquivo não foi varrido.

    Herda de `str` para que o motivo seja legível na saída sem conversão.
    """

    BINARY = "binary"
    TOO_LARGE = "too_large"


@dataclass(frozen=True)
class SkippedFile:
    path: Path
    reason: SkipReason


def is_binary_path(path: Path) -> bool:
    """Decide por extensão, sem abrir o arquivo.

    Não tocar o conteúdo é o ponto: a função responde para caminhos que sequer
    existem, e nenhum byte é lido de um arquivo que será descartado.
    """
    return path.suffix[1:].lower() in BINARY_EXTENSIONS


def _classify(path: Path) -> SkipReason | None:
    """Devolve o motivo do pulo, ou `None` se o arquivo deve ser varrido.

    A ordem importa: extensão primeiro, tamanho depois. Consultar o conjunto de
    extensões não toca o disco; `stat()` toca. Inverter gastaria um `stat()` em todo
    binário — desperdício proporcional ao número de arquivos.
    """
    if is_binary_path(path):
        return SkipReason.BINARY
    if path.stat().st_size > MAX_FILE_BYTES:
        return SkipReason.TOO_LARGE
    return None


def _is_ignored(path: Path, root: Path, ignore: Sequence[str]) -> bool:
    """Casa o caminho relativo POSIX contra os globs de `ignore`.

    `fnmatch` sobre o caminho relativo, e não `Path.match`: o `Path.match` do stdlib não
    trata `**` como o glob do shell, e `tests/fixtures/**` é exatamente a forma que o
    usuário escreve.
    """
    if not ignore:
        return False
    try:
        relativo = path.relative_to(root).as_posix()
    except ValueError:
        relativo = path.as_posix()
    return any(fnmatch.fnmatch(relativo, padrao) for padrao in ignore)


def walk(root: Path, ignore: Sequence[str] = ()) -> tuple[list[Path], list[SkippedFile]]:
    """Percorre `root` e separa o que varrer do que foi pulado.

    Aceita tanto diretório quanto arquivo único — `gitsafety scan arquivo.py` é uso
    legítimo.

    Levanta `PathNotFoundError` quando `root` não existe. Devolver lista vazia faria
    `gitsafety scan /caminho/digitado/errado` sair com 0, e o usuário concluiria que
    está limpo — o falso negativo mais caro que este produto pode produzir
    (`rules/error-handling.md § 2`: validar na fronteira).
    """
    root = Path(root)
    if not root.exists():
        raise PathNotFoundError(str(root))

    candidates = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())

    files: list[Path] = []
    skipped: list[SkippedFile] = []
    for path in candidates:
        # `ignore` age ANTES de qualquer leitura — é onde está o ganho (ADR D5), e o
        # arquivo ignorado NÃO entra em `skipped` (ADR D6): aquela lista existe para
        # mostrar decisão nossa, e ignorar é decisão do usuário. Reportá-la de volta
        # seria ruído, e ruído mina a confiança tanto quanto falso positivo.
        if _is_ignored(path, root, ignore):
            continue
        reason = _classify(path)
        if reason is None:
            files.append(path)
        else:
            skipped.append(SkippedFile(path=path, reason=reason))

    return files, skipped

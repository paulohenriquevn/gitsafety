"""Orquestra travessia e regras, produzindo o resultado da varredura (ADRs D2 e D7).

Camada de aplicação: compõe `walker` (o que varrer), `rules` (o que procurar) e
`finding` (o que reportar). Não imprime nada e não chama `sys.exit` — isso é da
interface (`rules/architecture.md § 1`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING

from gitsafety.finding import Finding
from gitsafety.notebook import is_notebook, parse_notebook
from gitsafety.rules import BUILTIN_RULES, Rule
from gitsafety.walker import SkippedFile, walk

if TYPE_CHECKING:  # evita ciclo em runtime; `config` importa deste módulo
    from gitsafety.config import Config

#: Marcador de supressão por linha (`docs/PRD.md § FR-14`).
#:
#: Procuramos a **substring**, sem exigir o caractere de comentário: linguagens usam
#: `#`, `//`, `--`, `;`, `%`. Exigir um deles obrigaria a saber a linguagem do arquivo, e
#: o falso positivo dessa escolha — a string aparecer fora de um comentário — é
#: irrelevante: quem a escreve está pedindo a supressão de qualquer forma.
INLINE_ALLOW_MARKER = "gitsafety: allow"


def is_allowed(secret: str, line: str, allow: Sequence[Pattern[str]] = ()) -> bool:
    """Diz se um achado deve ser suprimido — por marcador na linha ou por `allow:`.

    Existe **uma vez** e é chamada pelos dois caminhos de varredura (arquivo e index).
    Duplicá-la garantiria divergência na primeira mudança, e as duas cópias tratariam o
    mesmo conhecimento — que é o que o DRY protege.
    """
    if INLINE_ALLOW_MARKER in line:
        return True
    return any(padrao.search(secret) for padrao in allow)


@dataclass(frozen=True)
class ScanResult:
    """Resultado de uma varredura: o que foi achado **e** o que foi pulado (ADR D7).

    Devolver só `findings` tornaria o pulo de arquivo invisível por construção — e o
    `ROADMAP.md § M0` nomeia "pular um arquivo por engano é um falso negativo
    silencioso" como risco. O par é o que torna o pulo auditável pelo chamador.
    """

    findings: list[Finding]
    skipped: list[SkippedFile]

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


def _read_text(path: Path) -> str:
    """Lê o arquivo como UTF-8, substituindo o que não decodificar (ADR D2).

    Sem detector de encoding, deliberadamente: o
    `knowledge-base/references/ggshield/pyproject.toml:36-39` documenta que um bump de
    `charset-normalizer` degradou a detecção de segredos **em silêncio** ao passar a
    mal decodificar UTF-8 válido. Importar essa classe de falha para cobrir uma cauda
    que o M0 não tem seria um mau negócio.

    `errors="replace"` nunca levanta `UnicodeDecodeError`, então um arquivo estranho
    não derruba a varredura dos demais.
    """
    return path.read_text(encoding="utf-8", errors="replace")


def _scan_text(
    text: str,
    path: Path,
    rules: Sequence[Rule],
    allow: Sequence[Pattern[str]] = (),
) -> list[Finding]:
    findings: list[Finding] = []
    # `splitlines()` trata o arquivo com e sem `\n` final de forma idêntica, que é
    # justamente onde o off-by-one clássico aparece. `start=1` porque linha é 1-based.
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in rules:
            # `finditer`, não `search`: dois segredos na mesma linha precisam gerar
            # dois findings. Com `search` o segundo sumiria sem qualquer sinal.
            for match in rule.pattern.finditer(line):
                # `allow` e marcador agem DEPOIS do match (ADR D5): ambos dependem do
                # valor encontrado, então não há como avaliá-los antes de tê-lo.
                if is_allowed(match.group(0), line, allow):
                    continue
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        path=path,
                        line=line_number,
                        secret=match.group(0),
                    )
                )
    return findings


def _scan_notebook(
    raw: str,
    path: Path,
    rules: Sequence[Rule],
    allow: Sequence[Pattern[str]] = (),
) -> list[Finding] | None:
    """Varre um notebook parseado. Devolve `None` para sinalizar degradação (ADR D4).

    A localização — célula e linha **dentro** da célula — é codificada no `path` do
    `Finding`. Codificar ali, em vez de acrescentar campo à dataclass, é o que mantém o
    milestone aditivo: `cli.render` só imprime `f.path` e não precisa saber de notebooks,
    e os quatro milestones que consomem `Finding` seguem intocados.

    A supressão é decidida **aqui e só aqui**. Enquanto existiam dois caminhos varrendo o
    mesmo arquivo, ela era decidida duas vezes de forma independente, e uma supressão de um
    lado apagava uma ocorrência não relacionada do outro — silêncio total num segredo real.
    Uma decisão por ocorrência é o que impede isso, e ela só é possível com um caminho só.
    """
    segmentos = parse_notebook(raw)
    if segmentos is None:
        return None

    findings: list[Finding] = []
    for segmento in segmentos:
        for numero, linha in enumerate(segmento.text.splitlines(), start=1):
            for rule in rules:
                for match in rule.pattern.finditer(linha):
                    if is_allowed(match.group(0), linha, allow):
                        continue
                    findings.append(
                        Finding(
                            rule_id=rule.id,
                            path=Path(segmento.locate(path)),
                            line=numero,
                            secret=match.group(0),
                        )
                    )
    return findings


def scan_path(
    root: Path,
    rules: Sequence[Rule] = BUILTIN_RULES,
    *,
    config: Config | None = None,
) -> ScanResult:
    """Varre `root` (arquivo ou diretório) e devolve findings e pulos.

    Propaga `PathNotFoundError` de `walk` quando o caminho não existe — a validação
    mora na fronteira, e aqui os dados já são confiáveis.
    """
    from gitsafety.config import Config, effective_rules

    cfg = config if config is not None else Config()
    regras = effective_rules(cfg, rules)

    files, skipped = walk(Path(root), cfg.ignore)

    findings: list[Finding] = []
    for path in files:
        bruto = _read_text(path)
        if is_notebook(path):
            do_notebook = _scan_notebook(bruto, path, regras, cfg.allow)
            if do_notebook is not None:
                findings.extend(do_notebook)
                continue
            # `None` = JSON não parseou. Cai para texto, que é o comportamento dos
            # milestones anteriores — degradação para estado conhecido (ADR D4).
        findings.extend(_scan_text(bruto, path, regras, cfg.allow))

    return ScanResult(findings=findings, skipped=skipped)

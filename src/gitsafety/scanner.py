"""Orquestra travessia e regras, produzindo o resultado da varredura (ADRs D2 e D7).

Camada de aplicação: compõe `walker` (o que varrer), `rules` (o que procurar) e
`finding` (o que reportar). Não imprime nada e não chama `sys.exit` — isso é da
interface (`rules/architecture.md § 1`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from gitsafety.finding import Finding
from gitsafety.rules import BUILTIN_RULES, Rule
from gitsafety.walker import SkippedFile, walk


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


def _scan_text(text: str, path: Path, rules: Sequence[Rule]) -> list[Finding]:
    findings: list[Finding] = []
    # `splitlines()` trata o arquivo com e sem `\n` final de forma idêntica, que é
    # justamente onde o off-by-one clássico aparece. `start=1` porque linha é 1-based.
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in rules:
            # `finditer`, não `search`: dois segredos na mesma linha precisam gerar
            # dois findings. Com `search` o segundo sumiria sem qualquer sinal.
            for match in rule.pattern.finditer(line):
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        path=path,
                        line=line_number,
                        secret=match.group(0),
                    )
                )
    return findings


def scan_path(root: Path, rules: Sequence[Rule] = BUILTIN_RULES) -> ScanResult:
    """Varre `root` (arquivo ou diretório) e devolve findings e pulos.

    Propaga `PathNotFoundError` de `walk` quando o caminho não existe — a validação
    mora na fronteira, e aqui os dados já são confiáveis.
    """
    files, skipped = walk(Path(root))

    findings: list[Finding] = []
    for path in files:
        findings.extend(_scan_text(_read_text(path), path, rules))

    return ScanResult(findings=findings, skipped=skipped)

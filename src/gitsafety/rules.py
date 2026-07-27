"""Regras de detecção.

Uma regra é **dado com casos anexos**, não um regex solto. A forma vem do gitleaks
(`cmd/generate/config/rules/adafruit.go`), onde cada regra declara id, descrição,
padrão e é validada contra seus próprios exemplos positivos e negativos. O M0 tem uma
regra só, mas nasce nessa forma porque o M2 vai escalar para ≥ 40 e reescrever 40
regras depois custa muito mais do que acertar o formato agora.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class Rule:
    """Padrão de detecção nomeado.

    Congelada porque regra é dado imutável compartilhado entre todos os arquivos da
    varredura — mutação acidental em um arquivo mudaria o comportamento nos demais.
    """

    id: str
    description: str
    pattern: Pattern[str]


# `AKIA` seguido de exatamente 16 caracteres maiúsculos ou dígitos.
#
# `(?<![A-Z0-9])` e `(?![A-Z0-9])` delimitam sem consumir: sem eles o padrão casaria
# o prefixo de uma cadeia alfanumérica maior e reportaria um segredo inexistente.
# Falso positivo é o que faz o time desinstalar a ferramenta (`docs/PRD.md § 4`).
#
# O padrão é linear — literal + classe com quantificador fixo, sem alternância nem
# grupo aninhado. Não tem backtracking catastrófico por construção, que é o mitigante
# declarado no plano para o risco de travar o commit no M1.
AWS_ACCESS_KEY_ID = Rule(
    id="aws-access-key-id",
    description="Identificador de chave de acesso da AWS",
    pattern=re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
)


BUILTIN_RULES: tuple[Rule, ...] = (AWS_ACCESS_KEY_ID,)

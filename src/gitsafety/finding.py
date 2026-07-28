"""Ocorrência de uma regra em um arquivo, e o mascaramento do segredo.

`docs/API.md § Mascaramento`: o segredo aparece mascarado por padrão em toda saída. O
mascaramento mora aqui, junto do dado que carrega o segredo, e não no renderizador —
assim nenhum caminho de saída futuro (hook do M1, histórico do M5) pode esquecer de
aplicá-lo. Esquecer de mascarar em um caminho novo transformaria o relatório de
segurança no próximo vazamento.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MASK_CHAR = "•"

#: Quantos caracteres preservar em cada ponta. Preservar as bordas permite ao usuário
#: reconhecer QUAL chave é (o prefixo identifica o provedor) sem expor o valor.
DEFAULT_KEEP = 4


def mask(secret: str, *, keep: int = DEFAULT_KEEP) -> str:
    """Oculta o miolo do segredo, preservando `keep` caracteres em cada ponta.

    Quando o segredo é curto demais para ter miolo — `len <= 2 * keep` — oculta tudo.
    Preservar as bordas de um segredo de 8 caracteres com `keep=4` exporia o valor
    inteiro sob aparência de estar mascarado, o que é pior do que não mascarar,
    porque engana quem lê.

    O comprimento é sempre preservado: encolher esconderia o tamanho real, crescer
    confundiria quem compara com o valor que tem em mãos.
    """
    if keep <= 0 or len(secret) <= 2 * keep:
        return MASK_CHAR * len(secret)
    hidden = len(secret) - 2 * keep
    return f"{secret[:keep]}{MASK_CHAR * hidden}{secret[-keep:]}"


@dataclass(frozen=True)
class Finding:
    """Uma ocorrência de regra em um arquivo.

    Guarda o segredo íntegro porque `--show-secrets` (`docs/API.md § Mascaramento`) precisa
    dele; o contrato é que o mascarado seja o **default** de exibição, não que o
    original seja destruído.
    """

    rule_id: str
    path: Path
    line: int
    secret: str

    def __post_init__(self) -> None:
        # Linha 0 não existe em editor nenhum: aceitar 0 mascararia um off-by-one na
        # numeração, que é justamente o defeito clássico deste tipo de ferramenta.
        if self.line < 1:
            raise ValueError(f"line deve ser 1-based, recebido: {self.line}")

    @property
    def masked_secret(self) -> str:
        return mask(self.secret)

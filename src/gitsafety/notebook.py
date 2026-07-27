"""Parsing de notebooks Jupyter (ADRs D1-D4 do M4).

Transformação pura de documento em segmentos varreríveis. **Não importa nada do pacote
`gitsafety`** — o que a torna testável sem tocar o scanner, e mantém o formato isolado
num lugar só.

**Por que parsear, se varrer como texto já achava.** A medição do blueprint foi clara: um
notebook com 5 segredos plantados produzia 4 achados, e **nenhum** localizável — as linhas
reportadas eram do JSON, e um notebook aberto no Jupyter não tem linha 53. O gitleaks tem
a mesma lacuna e a resolve na apresentação (`detect/utils.go:41-43`, acrescentando
`?plain=1` ao link), o que só serve a quem escreve links; nós escrevemos caminhos locais.

`json` da stdlib, não `nbformat`: `.ipynb` é JSON, o `docs/PRD.md § NFR-1` já gastou sua
única dependência no M3, e a validação de esquema do `nbformat` é justamente o que **não**
queremos — um notebook que ele rejeita ainda pode conter a credencial.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

#: Chaves onde o código da célula pode estar. `input` é o nome no `nbformat` v3; tratar só
#: `source` produziria falso negativo **silencioso** em notebook antigo — o Risco nº 1 do
#: `ROADMAP.md § M4`. Aceitar as duas custa uma entrada nesta tupla; migrar o documento
#: custaria uma dependência.
_CODE_KEYS = ("source", "input")

#: Onde o texto mora em cada tipo de saída — verificado por execução no blueprint (Q3).
#:
#: Cobrir só `stream` seria o erro óbvio: é o tipo do `print`, o mais citado, mas
#: `execute_result` é o que aparece quando a **última expressão da célula** é o valor —
#: `os.environ` sozinho numa célula produz `execute_result`, não `stream`.
#:
#: `error` importa mais do que parece: um traceback salvo carrega a linha que falhou, com
#: os valores. Uma exceção durante uma chamada autenticada deixa a credencial ali.
#:
#: É uma **tabela de dados**, não uma cadeia de `if`, para que um tipo novo do formato seja
#: uma linha e não um ramo.
#: O separador faz parte do extrator porque o formato mistura duas convenções. `source` e
#: `stream.text` são `multiline_string` no schema — os elementos já trazem o `\n`, e juntar
#: com um inseriria quebra onde não há. `traceback` é `array of string`, uma entrada por
#: linha e SEM `\n`: juntar sem separador gruda `token=AKIA...` em `ValueError`, e o
#: delimitador de fim de padrão deixa de casar — falso negativo por concatenação.
_OUTPUT_TEXT_PATHS: dict[str, tuple[tuple[tuple[str, ...], str], ...]] = {
    "stream": ((("text",), ""),),
    "execute_result": ((("data", "text/plain"), ""),),
    "display_data": ((("data", "text/plain"), ""),),
    "error": ((("traceback",), "\n"), (("evalue",), "")),
}

CODE_ORIGIN = "código"
OUTPUT_ORIGIN = "saída"


@dataclass(frozen=True)
class Segment:
    """Um trecho varrível do notebook, com sua localização."""

    text: str
    cell_index: int  # 1-based, na ordem do arquivo
    origin: str  # CODE_ORIGIN ou OUTPUT_ORIGIN
    ordinal: int = 0  # >0 numera saídas da mesma célula, que senão seriam indistinguíveis

    def locate(self, path: Path) -> str:
        """Localização legível: o que o usuário precisa para achar o segredo no Jupyter.

        **Não** inclui o número da linha: `cli.render` já anexa `:{finding.line}` ao
        caminho, e incluí-lo aqui produzia `linha 1:1` na saída. A linha vem do `Finding`,
        que é onde ela pertence; aqui fica só o que o `Finding` não sabe representar.
        """
        sufixo = f" {self.ordinal}" if self.ordinal else ""
        return f"{path} :: célula {self.cell_index} ({self.origin}{sufixo})"


def is_notebook(path: Path) -> bool:
    return path.suffix.lower() == ".ipynb"


def _as_text(valor: object, sep: str = "") -> str:
    """Normaliza para texto o que o formato permite ser lista **ou** string.

    `source` e `text` são listas de linhas na prática, mas o formato aceita string, e
    ferramentas que geram notebook variam. Tratar só lista quebra em arquivo real.

    A junção é **sem separador** (ADR D2): os elementos já trazem o `\\n` quando há quebra,
    e o Jupyter pode partir no meio de uma linha. Juntar com `\\n` inseriria quebra onde
    não há e deslocaria a numeração; foi exatamente o valor partido entre elementos que
    produziu o único falso negativo medido no blueprint.
    """
    if isinstance(valor, str):
        return valor
    if isinstance(valor, list):
        return sep.join(item for item in valor if isinstance(item, str))
    return ""


def _dig(dados: object, caminho: tuple[str, ...]) -> object:
    for chave in caminho:
        if not isinstance(dados, dict):
            return None
        dados = dados.get(chave)
    return dados


def _segments_from_outputs(outputs: object, cell_index: int) -> list[Segment]:
    """Extrai os segmentos das saídas salvas de uma célula.

    Tolera forma inesperada **campo a campo**: `outputs` que não é lista, saída que não é
    dicionário, `data` sem `text/plain`. Um campo estranho não invalida os demais — abortar
    o notebook inteiro por causa de uma saída malformada seria trocar um achado parcial por
    nenhum.
    """
    if not isinstance(outputs, list):
        return []

    segmentos: list[Segment] = []
    for ordem, saida in enumerate(outputs, start=1):
        if not isinstance(saida, dict):
            continue
        for caminho, sep in _OUTPUT_TEXT_PATHS.get(saida.get("output_type", ""), ()):
            texto = _as_text(_dig(saida, caminho), sep)
            if texto:
                segmentos.append(
                    Segment(texto, cell_index, OUTPUT_ORIGIN, len(outputs) > 1 and ordem or 0)
                )
    return segmentos


def _extract_cells(documento: dict) -> list | None:
    """Localiza as células, no topo (v4) ou dentro de `worksheets` (v3).

    O schema do v3 exige `worksheets` no topo e guarda as células em
    `worksheets[].cells[]`. Aceitar só `cells` fazia todo notebook v3 **real** cair na
    degradação para texto — o segredo era achado, mas sem a localização por célula, que é o
    valor deste milestone. A chave `input` sozinha não bastava: ela nunca era alcançada.
    """
    celulas = documento.get("cells")
    if isinstance(celulas, list):
        return celulas

    folhas = documento.get("worksheets")
    if isinstance(folhas, list):
        reunidas: list = []
        for folha in folhas:
            if isinstance(folha, dict) and isinstance(folha.get("cells"), list):
                reunidas.extend(folha["cells"])
        return reunidas

    return None


def parse_notebook(raw: str) -> list[Segment] | None:
    """Devolve os segmentos varreríveis, ou `None` para sinalizar degradação.

    `None` significa "não consegui parsear, varra como texto" (ADR D4). Um `.ipynb`
    truncado ainda pode conter a credencial, e ela ainda importa: falhar recusaria o
    arquivo, e pular em silêncio é o falso negativo que o ADR D3 do M0 proíbe. Texto é o
    comportamento dos milestones anteriores — degradação para um estado **conhecido**.
    """
    try:
        documento = json.loads(raw)
    except (ValueError, RecursionError):
        # `ValueError` cobre `JSONDecodeError`. `RecursionError` é o que `json.loads`
        # levanta em JSON profundamente aninhado, e sem ele um único `.ipynb` estranho
        # derrubava a varredura dos DEMAIS arquivos do diretório — o oposto do contrato
        # que `_read_text` documenta e que `rules/error-handling.md § 2` exige.
        return None

    if not isinstance(documento, dict):
        return None

    celulas = _extract_cells(documento)
    if celulas is None:
        return None

    segmentos: list[Segment] = []
    for indice, celula in enumerate(celulas, start=1):
        if not isinstance(celula, dict):
            continue

        for chave in _CODE_KEYS:
            # A parada é por CONTEÚDO, não por presença: uma célula com `source: []` vazio
            # e o código em `input` (v3) fazia o `break` disparar antes de olhar `input`.
            texto = _as_text(celula.get(chave))
            if texto:
                segmentos.append(Segment(texto, indice, CODE_ORIGIN))
                break

        segmentos.extend(_segments_from_outputs(celula.get("outputs"), indice))

    return segmentos

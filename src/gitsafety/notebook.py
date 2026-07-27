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

#: Chaves cujo valor é `array of string` — uma entrada por LINHA, sem `\n` (schema
#: `nbformat`). Tudo o mais que é lista de strings é `multiline_string`: os elementos já
#: trazem o `\n` quando há quebra. A distinção é material: juntar `traceback` sem separador
#: gruda `token=AKIA...` no `ValueError:` da linha seguinte, e o delimitador de fim do
#: padrão deixa de casar — falso negativo por concatenação. E juntar `source` COM separador
#: inseriria quebra onde não há, mantendo o falso negativo do valor partido.
_LINE_ARRAY_KEYS = frozenset({"traceback"})

#: Mime-types pulados: imagem **rasterizada**. Base64 de PNG não é segredo — nossos 53
#: padrões são ancorados em marcadores literais (`AKIA`, `ghp_`, `postgresql://`), que não
#: ocorrem em base64 — e um PNG embutido é a maior parte dos bytes de um notebook.
#:
#: `+xml` escapa da exclusão porque SVG **é texto**: `image/svg+xml` carrega o conteúdo
#: legível, e pulá-lo era uma lacuna de cobertura disfarçada de otimização.
_SKIPPED_MIME_PREFIX = "image/"
_TEXTUAL_MIME_MARKER = "+xml"


def _is_skipped_mime(chave: object) -> bool:
    return (
        isinstance(chave, str)
        and chave.startswith(_SKIPPED_MIME_PREFIX)
        and _TEXTUAL_MIME_MARKER not in chave
    )


CODE_ORIGIN = "código"
OUTPUT_ORIGIN = "saída"
METADATA_ORIGIN = "metadados"
ATTACHMENT_ORIGIN = "anexo"
OTHER_ORIGIN = "conteúdo"

#: Rótulo por chave da célula. Serve só à MENSAGEM: a cobertura não depende desta tabela,
#: porque o que não estiver aqui cai em `OTHER_ORIGIN` e é percorrido do mesmo jeito.
_CELL_ORIGINS = {
    "outputs": OUTPUT_ORIGIN,
    "metadata": METADATA_ORIGIN,
    "attachments": ATTACHMENT_ORIGIN,
}


@dataclass(frozen=True)
class Segment:
    """Um trecho varrível do notebook, com sua localização."""

    text: str
    cell_index: int  # 1-based na ordem do arquivo; 0 = fora de qualquer célula
    origin: str  # CODE_ORIGIN ou OUTPUT_ORIGIN
    ordinal: int = 0  # >0 numera saídas da mesma célula, que senão seriam indistinguíveis

    def locate(self, path: Path) -> str:
        """Localização legível: o que o usuário precisa para achar o segredo no Jupyter.

        **Não** inclui o número da linha: `cli.render` já anexa `:{finding.line}` ao
        caminho, e incluí-lo aqui produzia `linha 1:1` na saída. A linha vem do `Finding`,
        que é onde ela pertence; aqui fica só o que o `Finding` não sabe representar.
        """
        if not self.cell_index:
            return f"{path} :: {self.origin}"
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


def _collect(
    node: object,
    cell_index: int,
    origin: str,
    ordinal: int,
    out: list[Segment],
    key: str = "",
) -> None:
    """Percorre qualquer subárvore do JSON e emite um segmento por texto encontrado.

    **Por que percorrer tudo em vez de extrair campos conhecidos.** A primeira versão do M4
    listava os campos a varrer — `source`, `input`, e quatro `output_type`. A lista estava
    errada, e a forma garantia que estivesse: o schema define `data` como *mimebundle*,
    dicionário de qualquer mime-type, e `text/plain` não é obrigatório. Um segredo em
    `text/html` (o `repr` de um DataFrame), em `application/json`, nos parâmetros do
    papermill em `metadata`, num `attachments` de markdown, ou num `output_type` que o
    Jupyter ainda vai inventar — nenhum estava na lista.

    Toda lista de formatos conhecidos é uma lista desatualizada, e num detector de segredos
    o custo de esquecer um item é um vazamento silencioso. Percorrer tudo troca "lembrar de
    incluir" por "decidir excluir" — e a única exclusão é `image/*`, que é justificável.
    """
    if isinstance(node, str):
        if node:
            out.append(Segment(node, cell_index, origin, ordinal))
        return

    if isinstance(node, list):
        if node and all(isinstance(item, str) for item in node):
            texto = _as_text(node, "\n" if key in _LINE_ARRAY_KEYS else "")
            if texto:
                out.append(Segment(texto, cell_index, origin, ordinal))
            return
        for item in node:
            _collect(item, cell_index, origin, ordinal, out, key)
        return

    if isinstance(node, dict):
        for chave, valor in node.items():
            if _is_skipped_mime(chave):
                continue
            if isinstance(valor, str) and isinstance(chave, str):
                # Emite `chave: valor` junto, não o valor sozinho. No arquivo bruto os dois
                # aparecem na mesma linha (`"aws_secret_key": "wJalr..."`), e as regras da
                # família keyword_assignment precisam do par — o nome é o que identifica um
                # segredo que não tem prefixo próprio. Separá-los perderia esses achados, e
                # é o que sobrava para a varredura de texto compensar.
                #
                # De quebra cobre o segredo usado como CHAVE, que a recursão sobre valores
                # nunca alcançaria.
                if valor:
                    out.append(Segment(f"{chave}: {valor}", cell_index, origin, ordinal))
                else:
                    out.append(Segment(chave, cell_index, origin, ordinal))
                continue
            _collect(valor, cell_index, origin, ordinal, out, chave)


def _segments_from_cell(celula: dict, cell_index: int) -> list[Segment]:
    """Segmentos de uma célula: o código primeiro, depois tudo o mais que ela carregue."""
    out: list[Segment] = []

    for chave in _CODE_KEYS:
        # A parada é por CONTEÚDO, não por presença: uma célula com `source: []` vazio e o
        # código em `input` (v3) faria um `break` por presença pular o `input`.
        texto = _as_text(celula.get(chave))
        if texto:
            out.append(Segment(texto, cell_index, CODE_ORIGIN))
            break

    for chave, valor in celula.items():
        if chave in _CODE_KEYS:
            continue
        if chave == "outputs" and isinstance(valor, list):
            # A saída é numerada porque duas saídas na mesma célula seriam indistinguíveis
            # na localização — e o usuário precisa saber de qual remover.
            for ordem, saida in enumerate(valor, start=1):
                _collect(saida, cell_index, OUTPUT_ORIGIN, ordem if len(valor) > 1 else 0, out)
            continue
        _collect(valor, cell_index, _CELL_ORIGINS.get(chave, OTHER_ORIGIN), 0, out, chave)

    return out


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
        if isinstance(celula, dict):
            segmentos.extend(_segments_from_cell(celula, indice))

    # O que vive fora das células — `metadata` do notebook é onde o papermill grava os
    # parâmetros da execução, e um deles pode ser a credencial. `cell_index=0` porque não
    # pertence a célula nenhuma, e dizer "célula 0" seria mentira.
    for chave, valor in documento.items():
        if chave in ("cells", "worksheets"):
            continue
        rotulo = f"{METADATA_ORIGIN} do notebook" if chave == "metadata" else OTHER_ORIGIN
        _collect(valor, 0, rotulo, 0, segmentos, chave)

    return segmentos


def unescape(secret: str) -> str:
    """O valor como existe no documento, não como o JSON o grafou.

    O arquivo bruto grafa `ã` como `\\u00e3` e uma barra invertida como `\\\\`. Comparar as
    duas visões sem desfazer isso trata a mesma ocorrência como duas coisas diferentes.
    """
    try:
        return json.loads(f'"{secret}"')
    except ValueError:
        # Aspas ou barra soltas: não é literal JSON válido, então não houve escape a desfazer.
        return secret


def written_forms(secret: str) -> set[str]:
    """As grafias com que este valor pode aparecer no arquivo bruto.

    A mesma ocorrência tem grafia diferente nas duas visões: o arquivo escreve `ã` como
    `\\u00e3` e uma barra invertida como `\\\\`, o documento parseado traz o caractere.
    Comparar sem considerar as duas trata uma ocorrência como duas coisas distintas.
    """
    return {secret, json.dumps(secret)[1:-1]}

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
from gitsafety.notebook import (
    is_notebook,
    parse_notebook,
    unescape,
    written_forms,
)
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
) -> list[tuple[Finding, bool]] | None:
    """Varre o notebook parseado. Devolve `(finding, suprimido)`; `None` degrada (ADR D4).

    A localização — célula e linha **dentro** da célula — é codificada no `path` do
    `Finding`. Codificar ali, em vez de acrescentar campo à dataclass, é o que mantém o
    milestone aditivo: `cli.render` só imprime `f.path` e não precisa saber de notebooks,
    e os quatro milestones que consomem `Finding` seguem intocados.

    Os suprimidos vêm junto, marcados, em vez de descartados. Um `# gitsafety: allow` que o
    Jupyter separou do segredo ao quebrar a linha só é visível **aqui** — no arquivo bruto o
    marcador está numa linha e o segredo noutra. Mas a supressão não pode ser aplicada aqui:
    apagar por valor foi o que fez um `allow` numa célula silenciar uma ocorrência não
    relacionada em outra. Ela é aplicada em `_localise`, sobre a ocorrência já pareada.
    """
    segmentos = parse_notebook(raw)
    if segmentos is None:
        return None

    achados: list[tuple[Finding, bool]] = []
    for segmento in segmentos:
        for numero, linha in enumerate(segmento.text.splitlines(), start=1):
            for rule in rules:
                for match in rule.pattern.finditer(linha):
                    achados.append(
                        (
                            Finding(
                                rule_id=rule.id,
                                path=Path(segmento.locate(path)),
                                line=numero,
                                secret=match.group(0),
                            ),
                            is_allowed(match.group(0), linha, allow),
                        )
                    )
    return achados


def _pair_with_notebook(
    do_texto: list[Finding],
    do_notebook: list[tuple[Finding, bool]] | None,
    raw: str,
    rules: Sequence[Rule],
) -> tuple[list[Finding | None], list[tuple[Finding, int | None]]]:
    """Pareia cada achado bruto com o achado localizado da MESMA ocorrência.

    Devolve `(alinhados, sobras)`:

    - `alinhados` tem **um item por achado de texto, na ordem de entrada** — o achado
      localizado, ou o próprio bruto quando o percurso não o alcançou, ou `None` quando a
      ocorrência foi deliberadamente suprimida. Manter o alinhamento é o que permite ao
      chamador remapear para as próprias chaves sem adivinhar.
    - `sobras` são achados do parser sem contrapartida no texto, **com a linha bruta que
      lhes coube**. São duas classes, e só uma não tem linha: valor que o Jupyter partiu
      entre elementos (`None`, porque não existe em nenhuma linha isolada) e ocorrência que
      o texto suprimiu demais (tem linha, e é por ela que o relatório a ordena).

    O pareamento é pela **linha bruta**, nunca pelo valor nem pela ordem. Parear por valor
    esconde uma ocorrência quando o mesmo segredo está em dois lugares; parear por ordem
    quebra quando um dos lados suprimiu algo que o outro não viu — foi exatamente esse o
    defeito que o review pegou no `--history`, onde a contagem de introduções acabava
    atribuída ao segredo errado.
    """
    if do_notebook is None:
        return list(do_texto), []

    linhas = raw.splitlines()
    localizados = _assign_raw_lines(do_notebook, linhas, rules)

    alinhados: list[Finding | None] = []
    usados: set[int] = set()
    for bruto in do_texto:
        par = next(
            (
                indice
                for indice, (finding, _, linha) in enumerate(localizados)
                if indice not in usados
                and linha == bruto.line
                and finding.rule_id == bruto.rule_id
                and finding.secret == unescape(bruto.secret)
            ),
            None,
        )
        if par is None:
            # O texto achou algo que o percurso não alcançou. Vale com a localização bruta.
            alinhados.append(bruto)
            continue
        usados.add(par)
        finding, suprimido, _ = localizados[par]
        alinhados.append(None if suprimido else finding)

    sobras = [
        (finding, linha)
        for indice, (finding, suprimido, linha) in enumerate(localizados)
        if indice not in usados and not suprimido
    ]
    return alinhados, sobras


def _localise(
    do_texto: list[Finding],
    do_notebook: list[tuple[Finding, bool]] | None,
    raw: str,
    rules: Sequence[Rule],
) -> list[Finding]:
    """Relatório do `scan`: achados localizados, mais as sobras, na ordem do arquivo.

    A varredura do arquivo bruto é a linha de base e **sempre roda**. Isso é o que torna a
    cobertura um mecanismo em vez de uma afirmação: qualquer coisa que o percurso do JSON
    não alcance — um mime que ele pule, um campo de forma inesperada, uma chave duplicada
    que o `json` descarta — continua sendo reportada, com a linha do JSON em vez da célula.
    Localização pior, nunca silêncio.

    Essa distinção custou três rodadas de revisão para ficar clara. Duas vezes o parser foi
    promovido a fonte da cobertura — primeiro com uma tabela de campos, depois com um
    percurso "completo" — e as duas vezes ele deixou passar formas válidas que ninguém tinha
    listado. A completude do percurso é uma crença; a da varredura de texto é o comportamento
    que os milestones anteriores já entregavam.

    As sobras entram aqui porque este caminho vê o arquivo **inteiro**: toda sobra é um valor
    partido pelo Jupyter, ou uma ocorrência que o texto suprimiu demais. Os caminhos que veem
    só parte do arquivo usam `_pair_with_notebook` direto e as descartam — ver `staged.py`.
    """
    alinhados, sobras = _pair_with_notebook(do_texto, do_notebook, raw, rules)

    if do_notebook is None:
        return [f for f in alinhados if f is not None]

    linhas = raw.splitlines()
    ordenado: list[tuple[int, Finding]] = [
        (bruto.line, finding)
        for bruto, finding in zip(do_texto, alinhados, strict=True)
        if finding is not None
    ]
    # Sobra COM linha conhecida entra na posição dela; sem linha, vai para o fim. Jogar
    # todas para o fim desordenava o relatório em 13% dos notebooks medidos — e um relatório
    # fora da ordem do arquivo é mais difícil de conferir, que é o que se faz com ele.
    ordenado.extend(
        (linha if linha is not None else len(linhas) + 1, finding) for finding, linha in sobras
    )

    # `sorted` é estável: empates mantêm a ordem do documento, que é a ordem das células.
    return [finding for _, finding in sorted(ordenado, key=lambda par: par[0])]


def _rule_matches_per_line(
    rule: Rule,
    secret: str,
    linhas: list[str],
) -> dict[int, int]:
    """Quantas vezes ESTA regra casa ESTE valor em cada linha bruta — 1-based.

    Conta casamento de regra, não ocorrência de substring. A diferença é material: um
    `AKIAIOSFODNN7EXAMPLE-old` num nome de arquivo contém o valor mas **não é** um segredo,
    porque o delimitador de fim do padrão o recusa. Contado como substring, ele criaria uma
    vaga de linha que o ponteiro consumiria, desalinhando todas as ocorrências seguintes —
    o que produzia achado duplicado e, num arranjo específico, fazia o `allow` do usuário
    ser ignorado.

    A vaga tem de corresponder ao que a varredura de texto de fato reportaria naquela linha.
    Qualquer aproximação aqui é um desalinhamento à espera de acontecer.
    """
    grafias = written_forms(secret)
    contagem: dict[int, int] = {}
    for numero, linha in enumerate(linhas, start=1):
        total = sum(1 for match in rule.pattern.finditer(linha) if match.group(0) in grafias)
        if total:
            contagem[numero] = total
    return contagem


def _assign_raw_lines(
    do_notebook: list[tuple[Finding, bool]],
    linhas: list[str],
    rules: Sequence[Rule],
) -> list[tuple[Finding, bool, int | None]]:
    """Diz, para cada achado do parser, em que linha bruta ESTA ocorrência está.

    Saber apenas que o valor aparece nas linhas 8 e 22 não basta: com o mesmo segredo em
    dois lugares, o achado da célula 1 casaria com a linha do segundo, e uma supressão no
    primeiro apagaria o segundo. A atribuição precisa ser 1-para-1.

    O percurso do documento e o arquivo bruto estão na **mesma ordem** — `json.loads`
    preserva a ordem das chaves, e listas são ordenadas. Então basta avançar um ponteiro por
    segredo: cada ocorrência toma a primeira linha ainda disponível a partir da anterior. A
    capacidade por linha é a contagem de ocorrências ali, para que duas na mesma linha não
    briguem pela mesma vaga.

    `None` significa que a ocorrência não existe em nenhuma linha isolada — valor partido
    entre elementos pelo Jupyter.
    """
    por_id = {regra.id: regra for regra in rules}
    capacidades: dict[tuple[str, str], dict[int, int]] = {}
    ponteiros: dict[tuple[str, str], int] = {}

    atribuidos: list[tuple[Finding, bool, int | None]] = []
    for finding, suprimido in do_notebook:
        segredo = (finding.rule_id, finding.secret)
        if segredo not in capacidades:
            regra = por_id.get(finding.rule_id)
            capacidades[segredo] = (
                _rule_matches_per_line(regra, finding.secret, linhas) if regra else {}
            )
            ponteiros[segredo] = 0

        capacidade = capacidades[segredo]
        escolhida = next(
            (
                numero
                for numero in sorted(capacidade)
                if numero >= ponteiros[segredo] and capacidade[numero] > 0
            ),
            None,
        )
        if escolhida is not None:
            capacidade[escolhida] -= 1
            ponteiros[segredo] = escolhida
        atribuidos.append((finding, suprimido, escolhida))

    return atribuidos


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
        do_texto = _scan_text(bruto, path, regras, cfg.allow)
        if is_notebook(path):
            findings.extend(
                _localise(
                    do_texto, _scan_notebook(bruto, path, regras, cfg.allow), bruto, regras
                )
            )
        else:
            findings.extend(do_texto)

    return ScanResult(findings=findings, skipped=skipped)

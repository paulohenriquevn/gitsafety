"""Travessia do histórico do git (ADRs D1–D4 do M5).

Camada de aplicação: compõe `git` (de onde vem o texto), `staged` (como o diff vira linhas)
e `rules` (o que procurar). Não imprime e não chama `sys.exit` — isso é da interface
(`rules/architecture.md § 1`).

**Por que o comando não é o do gitleaks.** Ele usa
`git log -p -U0 --full-history --all --diff-filter=tuxdb` (`sources/git.go:93-94`), e a
descoberta do M5 mediu que esse comando devolve **0 ocorrências onde há 1 real** quando o
segredo é colado na resolução de um conflito de merge. A causa é comportamento documentado
do git: `log -p` não emite diff para commit de merge. Quem cola uma credencial ao resolver
conflito fica invisível.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from gitsafety.errors import GitsafetyError
from gitsafety.finding import Finding
from gitsafety.git import run_git
from gitsafety.rules import BUILTIN_RULES, Rule
from gitsafety.scanner import is_allowed
from gitsafety.staged import _is_ignored_path, parse_added_lines

if TYPE_CHECKING:  # evita ciclo em runtime; `config` importa de `scanner`
    from gitsafety.config import Config

#: Separador de campos no cabeçalho de commit — UNIT SEPARATOR (0x1f).
#:
#: Um caractere de controle, e não `|` ou `\t`: assunto de commit contém barra e tabulação
#: com frequência, e um separador que ocorre no dado é um parser que desalinha em silêncio.
SEPARADOR = "\x1f"

#: `%H` sha, `%an` autor, `%aI` data ISO-8601, `%s` assunto. O assunto vem por último porque
#: é o único campo que pode conter qualquer coisa — deixá-lo no fim permite fatiar com limite
#: e absorver o resto nele.
_FORMATO = f"%H{SEPARADOR}%an{SEPARADOR}%aI{SEPARADOR}%s"

_CAMPOS = 4


@dataclass(frozen=True)
class CommitInfo:
    """Quem introduziu, quando e com que mensagem."""

    sha: str
    author: str
    date: str  # ISO-8601, de `%aI`
    subject: str

    @property
    def short_sha(self) -> str:
        return self.sha[:8]


@dataclass(frozen=True)
class HistoryFinding:
    """Um segredo no histórico: onde foi introduzido e em quantos commits aparece."""

    finding: Finding
    commit: CommitInfo
    #: Em quantos commits a linha foi **introduzida** — não em quantos ela existe.
    #:
    #: A distinção é do mecanismo, não da preferência: `-U0` mostra apenas linhas alteradas,
    #: então um segredo que entra no commit 1 e permanece intocado nos commits 2 e 3 é
    #: introduzido **uma** vez. Saber em quantos commits ele *existe* exigiria varrer a
    #: árvore inteira de cada commit — outro custo e outra decisão.
    #:
    #: O número maior que 1 significa algo específico e útil: a linha foi adicionada de novo
    #: depois de sair. Alguém removeu e recolocou a credencial, ou ela foi reintroduzida em
    #: outro ramo.
    introductions: int


def history_diff(cwd: Path) -> str:
    """Devolve o histórico como uma sequência de cabeçalhos e diffs.

    Cada flag é uma decisão, não um enfeite:

    - `--all` — todas as refs, não só `HEAD`. Também é o que faz um repositório **sem
      commits** sair com 0 e saída vazia; sem ela o git sai 128 com `fatal: does not have
      any commits yet`, e o DoD nº 4 viraria um caso especial no código (ADR D4).
    - `--diff-merges=first-parent` — emite o diff dos merges contra o primeiro pai. Sem ela,
      um segredo colado na resolução de um conflito é **invisível** (medido: 0 de 1). Com
      `-m` também apareceria, mas uma vez por pai, dobrando o achado.
    - `-p` com `-U0` — só as linhas adicionadas, sem contexto. Mesma escolha do `staged.py`.
    - `--no-ext-diff`, `--text` e `--no-textconv` — as três formas de o próprio repositório
      desligar a verificação. Ver o comentário no corpo: um `.gitattributes` com `-diff`
      fazia o hook deixar passar o commit da credencial.
    """
    return run_git(
        [
            "log",
            "-p",
            "-U0",
            "--all",
            "--diff-merges=first-parent",
            "--no-ext-diff",
            # `--text` e `--no-textconv` fecham três formas de o PRÓPRIO repositório
            # desligar a verificação, todas medidas:
            #
            # - `.gitattributes` com `-diff` faz o git emitir `Binary files differ` em vez
            #   do conteúdo. Com o hook instalado, o commit da credencial PASSAVA.
            # - Um byte NUL no arquivo dispara a mesma heurística de binário — acontece em
            #   dump, keystore e arquivo em UTF-16.
            # - Um driver `textconv` reescreve o que o diff mostra, e pode redigir o valor.
            #
            # `--no-ext-diff` sozinho era meia defesa: fechava o `diff.external` e deixava
            # os outros dois abertos, configuráveis do mesmo jeito e por quem commita.
            "--text",
            "--no-textconv",
            f"--format={_FORMATO}",
        ],
        cwd=cwd,
    )


def _e_cabecalho(linha: str) -> bool:
    """Diz se a linha abre um commit.

    Exigir o número exato de campos é o que impede que uma linha de conteúdo contendo o
    separador abra um commit falso — e que um cabeçalho truncado desalinhe os seguintes.
    """
    return linha.count(SEPARADOR) >= _CAMPOS - 1 and not linha.startswith(("+", "-", " "))


def parse_commits(raw: str) -> list[tuple[CommitInfo, str]]:
    """Fatia a saída de `history_diff` em `(commit, diff daquele commit)`.

    O fatiamento existe para que `staged.parse_added_lines` — o parser do M1, reusado sem
    cópia (ADR D3) — receba apenas diff. Sem ele, o cabeçalho seria lido como conteúdo e o
    achado perderia o commit, que é justamente o que o `ROADMAP.md § M5` manda reportar.
    """
    commits: list[tuple[CommitInfo, str]] = []
    atual: CommitInfo | None = None
    corpo: list[str] = []

    for linha in raw.splitlines():
        if _e_cabecalho(linha):
            # `maxsplit` é o que protege o assunto: `%s` é o último campo do formato, então
            # tudo o que vier depois do terceiro separador pertence a ele. Sem o limite, um
            # assunto contendo o separador deslocaria os campos seguintes.
            partes = linha.split(SEPARADOR, _CAMPOS - 1)
            if len(partes) == _CAMPOS:
                if atual is not None:
                    commits.append((atual, "\n".join(corpo)))
                atual = CommitInfo(*partes)
                corpo = []
                continue

        if atual is not None:
            corpo.append(linha)

    if atual is not None:
        commits.append((atual, "\n".join(corpo)))

    return commits


def _localizar_notebooks(
    introducao: dict,
    ordem: list,
    cwd: Path,
    regras,
    allow,
) -> dict:
    """Troca a linha do JSON pela célula, nos achados que estão em notebook.

    Mesmo mecanismo do `--staged` e do `scan`: `scanner._localise` pareia o achado bruto
    com o achado do documento parseado **pela linha do arquivo**. O conteúdo vem do commit
    da introdução (`git show <sha>:<caminho>`), que é onde o achado está.

    Este módulo NÃO usava `_localise` — e uma mensagem de commit minha afirmou que usava.
    Era falso, e o review pegou. A issue #6 estava fechada para dois dos três alvos.

    Custo: uma chamada ao git por notebook **que tenha achado**.
    """
    from gitsafety.notebook import is_notebook
    from gitsafety.scanner import _localise, _scan_notebook

    resultado = {chave: introducao[chave][0] for chave in ordem}

    por_arquivo: dict[tuple[str, str], list] = {}
    for chave in ordem:
        finding, commit = introducao[chave]
        if is_notebook(finding.path):
            por_arquivo.setdefault((commit.sha, str(finding.path)), []).append(chave)

    for (sha, caminho), chaves in por_arquivo.items():
        try:
            bruto = run_git(["show", f"{sha}:{caminho}"], cwd=cwd)
        except GitsafetyError:
            # Caminho que o git não resolve naquele commit (rename, por exemplo): fica com
            # a localização bruta, que é pior mas nunca silêncio.
            continue
        achados = [introducao[c][0] for c in chaves]
        melhorados = _localise(
            achados,
            _scan_notebook(bruto, Path(caminho), regras, allow),
            bruto,
            regras,
            incluir_extras=False,
        )
        # `incluir_extras=False` porque este caminho vê só as linhas ADICIONADAS de cada
        # commit, não o arquivo inteiro: com ele ligado, todo segredo preexistente do
        # notebook viraria "sobra" e seria reportado como se tivesse sido introduzido ali.
        # Assim a função é enriquecimento puro — melhora a localização, nunca cria achado.
        #
        # `_localise` devolve na ordem dos achados de texto, então o pareamento posicional
        # é seguro.
        # `strict=False` de propósito: `_localise` pode devolver sobras (valor partido entre
        # elementos) que não têm chave correspondente. Emparelhar até o menor é o correto.
        for chave, melhorado in zip(chaves, melhorados, strict=False):
            resultado[chave] = melhorado

    return resultado


def rewritten_commits(cwd: Path) -> int:
    """Quantos commits existem só no reflog local, fora de qualquer referência.

    Serve a um risco específico e grave: alguém reescreve o histórico para "remover" a
    chave, roda `--history`, vê "nenhum segredo encontrado" e acredita que resolveu. O
    commit saiu das referências, mas o objeto continua no repositório local por cerca de 90
    dias — e reescrever histórico nunca desfez uma exposição. Falsa sensação de segurança é
    o pior resultado que uma ferramenta de segurança pode produzir.

    **Por que contar em vez de varrer.** O reflog é local e pessoal: ele registra o que
    *você* fez nesta máquina, não o que está no repositório compartilhado. Um achado vindo
    dali afirma "esta chave passou pelo seu disco", não "está no histórico do projeto" — e
    misturar as duas afirmações num relatório só é pior que não ter a segunda. Além disso o
    reflog **não existe num clone novo nem em CI**, então varrê-lo por padrão faria a mesma
    revisão do mesmo repositório dar respostas diferentes em máquinas diferentes.

    Contar custa 8 ms e permite avisar sobre a lacuna exatamente quando ela existe, sem
    gastar uma flag (`docs/PRD.md § NFR-3` limita o `scan` a quatro) nem prometer o que não
    entregamos.
    """
    try:
        saida = run_git(["rev-list", "--reflog", "--not", "--all", "--count"], cwd=cwd)
        return int(saida.strip() or 0)
    except (GitsafetyError, ValueError):
        # Repositório sem reflog, ou git que não entende a combinação: a ausência do aviso
        # é aceitável; um erro aqui não pode derrubar a varredura, que é o que importa.
        return 0


def scan_history(
    cwd: Path,
    rules: Sequence[Rule] = BUILTIN_RULES,
    *,
    config: Config | None = None,
) -> list[HistoryFinding]:
    """Varre o histórico e devolve os segredos, deduplicados por ocorrência.

    A dedup é por `(regra, segredo, arquivo)` e o commit reportado é o **mais antigo** em
    que a ocorrência aparece (ADR D2). O mesmo segredo repetido a cada commit é o ruído que
    o Risco M5 nº 2 nomeia; e a ação que o produto pede — revogar a chave no provedor — é
    única por segredo, não por commit. O commit mais antigo responde "desde quando está
    exposta?", que é o que decide a urgência.

    A contagem viaja junto **porque colapso silencioso esconde informação** — foi a lição
    mais cara do M4. A interface a mostra quando é maior que 1.

    **Correção de contrato vinda da implementação.** O ADR D2 do plano dizia "em quantos
    commits a ocorrência aparece". Uma travessia por diff não pode saber isso: `-U0` mostra
    linhas alteradas, então uma linha que entra e permanece é vista uma vez. O que o número
    mede é **introduções**, e essa é a informação que o mecanismo entrega honestamente.
    """
    from gitsafety.config import Config, effective_rules

    cfg = config if config is not None else Config()
    regras = effective_rules(cfg, rules)

    # `git log` emite do mais novo para o mais antigo, então a ÚLTIMA ocorrência vista de
    # uma chave é a introdução. Sobrescrever a cada visita é mais barato que `--reverse`,
    # cujo custo a descoberta não mediu.
    introducao: dict[tuple[str, str, str], tuple[Finding, CommitInfo]] = {}
    entradas: dict[tuple[str, str, str], int] = defaultdict(int)
    ordem: list[tuple[str, str, str]] = []

    for commit, diff in parse_commits(history_diff(cwd)):
        vistos_no_commit: set[tuple[str, str, str]] = set()
        for adicionada in parse_added_lines(diff):
            # `ignore:` do `.gitsafety.yml` vale nos TRÊS alvos. O helper vem do M1 em vez
            # de ser reescrito aqui: o caminho do diff é relativo à raiz do repositório nos
            # dois casos, e duplicar a regra garantiria divergência na primeira mudança.
            if _is_ignored_path(adicionada.path, cfg.ignore):
                continue
            for regra in regras:
                for match in regra.pattern.finditer(adicionada.text):
                    if is_allowed(match.group(0), adicionada.text, cfg.allow):
                        continue
                    chave = (regra.id, match.group(0), str(adicionada.path))
                    if chave not in introducao:
                        ordem.append(chave)
                    introducao[chave] = (
                        Finding(
                            rule_id=regra.id,
                            path=adicionada.path,
                            line=adicionada.line,
                            secret=match.group(0),
                        ),
                        commit,
                    )
                    # Contar por COMMIT, não por linha: o mesmo segredo duas vezes no mesmo
                    # commit é uma exposição só, e contá-lo duas vezes inflaria a métrica
                    # que o usuário lê para decidir urgência.
                    vistos_no_commit.add(chave)
        for chave in vistos_no_commit:
            entradas[chave] += 1

    localizados = _localizar_notebooks(introducao, ordem, cwd, regras, cfg.allow)

    return [
        HistoryFinding(
            finding=localizados[chave],
            commit=introducao[chave][1],
            introductions=entradas[chave],
        )
        for chave in ordem
    ]

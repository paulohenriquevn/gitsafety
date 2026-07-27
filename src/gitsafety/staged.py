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

from gitsafety.errors import GitsafetyError
from gitsafety.finding import Finding
from gitsafety.git import run_git
from gitsafety.notebook import is_notebook
from gitsafety.rules import BUILTIN_RULES, Rule
from gitsafety.scanner import ScanResult, is_allowed
from gitsafety.walker import MAX_FILE_BYTES

if TYPE_CHECKING:  # evita ciclo em runtime; `config` importa deste módulo
    from gitsafety.config import Config

#: `@@ -a,b +c,d @@` — `c` é a primeira linha do lado NOVO, que é o que numeramos.
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,\d+)? @@")

#: `+++ b/caminho` — o nome do arquivo novo. Vem do lado `+++` porque arquivo recém-criado
#: tem `--- /dev/null` do lado antigo.
#:
#: O `b/` **não** é consumido aqui: quando o git escreve o nome entre aspas, o prefixo fica
#: DENTRO delas. Retirá-lo é trabalho de `_decode_path`, depois de desfazer o escape.
_NEW_FILE_RE = re.compile(r"^\+\+\+ (?P<path>.+)$")


def _decode_path(bruto: str) -> str:
    """Devolve o nome do arquivo como o usuário o vê, não como o git o escreveu.

    O git aplica *C-quoting* a nome com caractere não-ASCII, aspas, barra invertida ou
    controle: `configuração.env` sai como `"b/configura\\303\\247\\303\\243o.env"`. E
    acrescenta um tab ao fim de nome com espaço, para delimitá-lo.

    Sem desfazer isso, o achado exibe uma string que não localiza o arquivo — e, pior,
    `ignore:` compara contra ela e falha em **silêncio**. Um `ignore:` que vale para nome
    ASCII e não para nome acentuado é pior que um que não existe: o usuário configura,
    confere num arquivo qualquer e supõe que vale para todos. Num projeto brasileiro, acento
    em nome de arquivo é o caso comum, não a cauda.

    A decodificação usa `unicode_escape` da stdlib (`rules/parsimony-ladder.md` rung 2), que
    desfaz o octal `\\NNN` e os escapes de aspa e barra. O resultado sai com um byte por
    caractere (latin-1) e é reinterpretado como UTF-8, que é o que o git de fato gravou.
    """
    nome = bruto.rstrip("\t")

    if nome.startswith('"') and nome.endswith('"') and len(nome) > 1:
        nome = (
            nome[1:-1]
            .encode("latin-1", "backslashreplace")
            .decode("unicode_escape")
            .encode("latin-1", "replace")
            # `errors="replace"` pelo mesmo motivo de `scanner._read_text`: um nome que não
            # decodifica não pode derrubar a varredura dos demais arquivos.
            .decode("utf-8", "replace")
        )

    return nome.removeprefix("b/")


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
            alvo = _decode_path(novo_arquivo.group("path"))
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


#: Acima de quanto um arquivo BINÁRIO deixa de ser varrido no index.
#:
#: O teto é sobre binário, não sobre bytes. Copiar o limite de tamanho do `scan` para o
#: hook seria a saída óbvia e errada: um `.env` de 2 MB com uma credencial deixaria de
#: bloquear o commit, e isso é perda de cobertura no único caminho que não pode perder.
#:
#: Quem decide o que é binário é o **git**, não uma heurística nossa — `--numstat` marca
#: esses arquivos com `-` no lugar da contagem de linhas. Usar a decisão dele torna o teto
#: explicável ao usuário ("binário acima de 1 MB") e consistente com o `scan`, que já pula
#: binário por extensão e qualquer arquivo acima deste mesmo limite.
#:
#: A primeira versão contava bytes das linhas do diff e **não funcionava**: 5 MB de arquivo
#: viram 703 KB depois do diff, então o teto nunca era cruzado. Media a quantidade errada.
#:
#: E o pulo é REPORTADO. É o que separa este teto do fail-open que o M5 corrigiu: lá o git
#: escondia o conteúdo sem avisar ninguém.
_TETO_BINARIO_BYTES = MAX_FILE_BYTES


def _binarios_grandes(cwd: Path) -> list[Path]:
    """Arquivos que o git considera binários e que passam do teto, pelo tamanho no index."""
    grandes: list[Path] = []
    for linha in run_git(["diff", "--staged", "--numstat"], cwd=cwd).splitlines():
        partes = linha.split("\t", 2)
        # `-` no lugar da contagem de linhas é como o git marca binário.
        if len(partes) != 3 or partes[0] != "-":
            continue
        caminho = _decode_path(partes[2])
        try:
            tamanho = int(run_git(["cat-file", "-s", f":{caminho}"], cwd=cwd))
        except (GitsafetyError, ValueError):
            # Caminho que o git não resolve (arquivo removido, por exemplo): na dúvida,
            # varre. Pular por engano seria falso negativo; varrer por engano custa tempo.
            continue
        if tamanho > _TETO_BINARIO_BYTES:
            grandes.append(Path(caminho))
    return grandes


def scan_staged_diff(
    diff: str,
    rules: Sequence[Rule] = BUILTIN_RULES,
    *,
    config: Config | None = None,
    pular: Sequence[Path] = (),
) -> ScanResult:
    """Varre um diff já obtido. Existe separada para ser testável sem repositório.

    `scan_staged` e o caminho do histórico compartilham esta função — o mesmo diff, o mesmo
    matcher, o mesmo teto. Duplicar aqui garantiria divergência na primeira mudança, e o M4
    mediu o preço de dois caminhos sobre a mesma coisa.
    """
    from gitsafety.config import Config, effective_rules
    from gitsafety.walker import SkippedFile, SkipReason

    cfg = config if config is not None else Config()
    regras = effective_rules(cfg, rules)

    findings: list[Finding] = []
    a_pular = set(pular)
    pulados = [SkippedFile(path=caminho, reason=SkipReason.TOO_LARGE) for caminho in pular]

    for adicionada in parse_added_lines(diff):
        if _is_ignored_path(adicionada.path, cfg.ignore):
            continue
        if adicionada.path in a_pular:
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

    return ScanResult(findings=findings, skipped=pulados)


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

    `skipped` traz o que o teto de binário deixou de fora — nunca vazio por construção.
    """
    resultado = scan_staged_diff(
        staged_diff(cwd), rules, config=config, pular=_binarios_grandes(cwd)
    )
    return _com_localizacao_de_notebook(resultado, cwd, rules, config=config)


def _com_localizacao_de_notebook(
    resultado: ScanResult,
    cwd: Path,
    rules: Sequence[Rule],
    *,
    config: Config | None,
) -> ScanResult:
    """Troca a linha do JSON pela célula, nos achados que estão em notebook.

    O ADR D5 do M4 decidiu que `--staged` NÃO parsearia notebooks, e estava certo naquele
    momento: mapear a linha do diff de volta para a célula exigiria um segundo caminho de
    varredura, e o M4 gastou cinco rodadas de review consertando defeitos nascidos
    exatamente disso.

    O M5 mudou o cálculo. `scanner._localise` já pareia achado bruto com achado de notebook
    **pela linha do arquivo**, e é o que o `--history` usa. Reusá-lo aqui não cria caminho
    novo: a varredura continua sendo uma só, e o parsing apenas melhora a localização.

    O conteúdo vem do **index** (`git show :caminho`), não do disco: o hook verifica o que
    está sendo commitado, e o arquivo em disco pode já ter sido editado depois do `git add`.

    Custo: uma chamada ao git por notebook **que tenha achado**. Notebook sem segredo não
    paga nada.
    """
    from gitsafety.config import effective_rules
    from gitsafety.scanner import _localise, _scan_notebook

    if not resultado.findings:
        return resultado

    from gitsafety.config import Config as _Config

    cfg = config if config is not None else _Config()
    regras = effective_rules(cfg, rules)

    por_arquivo: dict[Path, list[Finding]] = {}
    for finding in resultado.findings:
        por_arquivo.setdefault(finding.path, []).append(finding)

    localizados: list[Finding] = []
    for caminho, achados in por_arquivo.items():
        if not is_notebook(caminho):
            localizados.extend(achados)
            continue
        try:
            bruto = run_git(["show", f":{caminho}"], cwd=cwd)
        except GitsafetyError:
            # Caminho que o git não resolve no index: fica com a localização bruta, que é
            # pior mas nunca silêncio.
            localizados.extend(achados)
            continue
        localizados.extend(
            _localise(achados, _scan_notebook(bruto, caminho, regras, cfg.allow), bruto, regras)
        )

    return ScanResult(findings=localizados, skipped=resultado.skipped)

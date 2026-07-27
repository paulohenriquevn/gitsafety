"""Construtores de padrão de detecção (ADRs D1 e D2).

Duas famílias, precedente em
`knowledge-base/references/gitleaks/cmd/generate/config/utils/generate.go:34,69`:

- **token único** — o valor carrega a própria identidade (`AKIA…`, `ghp_…`); basta
  delimitá-lo. Intrinsecamente seguro contra falso positivo.
- **semi-genérica** — o valor não é reconhecível sozinho; a regra exige palavra-chave,
  operador de atribuição e delimitador ao redor. É onde o falso positivo mora.

Montar os padrões a partir de partes verificadas, em vez de escrever 40 regexes à mão,
é o que faz a disciplina do ADR D2 valer **por construção** e não por revisão.

**A diferença de motor que motiva tudo isto.** O gitleaks roda em RE2, que não faz
backtracking: para eles, quantificador limitado é higiene. Nós rodamos em `re`, que faz —
e desde o M1 a regex roda dentro do `git commit`. Aqui, quantificador limitado é defesa.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from re import Pattern


@dataclass(frozen=True)
class Rule:
    """Padrão de detecção nomeado, com seus próprios casos de teste.

    Mora aqui, junto dos construtores que a produzem, e não em `rules.py`: aquele módulo
    acumulava o **tipo** e o **registro**, duas responsabilidades cujo acoplamento
    produzia import circular assim que o catálogo passou a ser um módulo à parte. O
    grafo agora é acíclico — `patterns` → `catalog` → `rules`.

    Congelada porque regra é dado imutável compartilhado por toda a varredura: mutação
    acidental num arquivo mudaria o comportamento nos demais.

    `true_positives` e `false_positives` têm default vazio para não quebrar construção
    existente, **mas** `tests/unit/test_catalog.py` exige que sejam não-vazios para toda
    regra do catálogo. Sem essa exigência, o default seria a porta pela qual uma regra
    entraria sem exemplo nenhum.
    """

    id: str
    description: str
    pattern: Pattern[str]
    true_positives: tuple[str, ...] = ()
    false_positives: tuple[str, ...] = ()


#: Delimitador que pode preceder um segredo: aspas, crase, espaço, `=`.
#: Verificado por **lookbehind**, que não consome — ver `_SUFFIX`.
_PREFIX = r"(?<![\w./+-])"

#: Delimitador que pode seguir um segredo. Usa **lookahead**, divergindo do precedente
#: (`generate.go:31`), que consome. Com `finditer` sobre a linha inteira, consumir o
#: espaço entre dois segredos adjacentes faria o segundo desaparecer.
_SUFFIX = r"(?![\w./+-])"

#: Janela entre a palavra-chave e o valor, na família semi-genérica. Limitada a 20 —
#: o precedente usa o mesmo teto (`generate.go:22`).
_GAP = r"[ \t]{0,20}"

#: Operadores de atribuição aceitos. Alternância simples de literais: não aninha
#: quantificador, então não degrada.
_OPERATOR = r"(?:=|:=|:|=>|\?=)"

#: Aspas opcionais ao redor do valor. Teto de 3, como em `generate.go:22`.
_QUOTE = r"['\"`]{0,3}"

#: `{n,}` sem teto superior, fora de classe de caracteres.
_OPEN_REPEAT_RE = re.compile(r"\{\d+,\}")


def has_free_quantifier(pattern: str) -> bool:
    """Diz se o padrão contém quantificador sem teto superior.

    Percorre o padrão caractere a caractere em vez de usar uma regex, porque `*` e `+`
    mudam de significado conforme o contexto e uma regex não distingue os três casos:

    - **escapado** (`a\\*`) — asterisco literal, não quantificador;
    - **dentro de classe** (`[\\w./+-]`) — o `+` ali é um caractere literal do conjunto;
    - **fora de classe e não escapado** (`a*`) — aí sim é quantificador.

    Confundir os dois primeiros com o terceiro torna o detector ruidoso, e um detector
    ruidoso acaba desligado — que é como uma defesa morre. Este caso não é hipotético:
    o próprio `unique_token` gera `[\\w./+-]`, e a primeira versão deste detector o
    acusou.

    É a rede mecânica do ADR D2 e **não substitui** a medição de tempo (ADR D6): há
    construção patológica sem quantificador livre, e há quantificador livre que na
    prática não degrada. As duas verificações são complementares.
    """
    dentro_de_classe = False
    i = 0
    while i < len(pattern):
        c = pattern[i]

        if c == "\\":
            i += 2  # o próximo caractere é literal, seja qual for
            continue

        if dentro_de_classe:
            if c == "]":
                dentro_de_classe = False
            i += 1
            continue

        if c == "[":
            dentro_de_classe = True
            i += 1
            continue

        if c in "*+":
            return True

        if c == "{" and _OPEN_REPEAT_RE.match(pattern, i):
            return True

        i += 1

    return False


def has_nested_quantifier(pattern: str) -> bool:
    """Diz se um grupo que **contém** quantificador é ele próprio quantificado.

    `(a{1,50}){1,50}`, `(a+)+`, `(\\d{2,4})*` — é a forma clássica de backtracking
    catastrófico. Todos os quantificadores podem estar limitados, então
    `has_free_quantifier` não a alcança: `(a{1,50}){1,50}` tem teto em ambos e ainda
    assim tenta um número astronômico de partições da entrada.

    **Por que a detecção precisa ser estática.** A alternativa óbvia — rodar a regex
    numa entrada de teste e cronometrar — não funciona como defesa primária: uma regex
    patológica explode **durante a própria medição**, e a verificação de tempo só é
    alcançada depois que a busca retorna. A defesa não pode depender de executar aquilo
    de que ela protege. Isto foi descoberto na implementação do M3: a primeira versão
    media com uma sonda de 4.000 caracteres e pendurou a suíte de testes.

    A medição continua existindo como rede **secundária**, com sonda curta e progressiva
    (ver `config._probe_is_fast_enough`), para formas que esta análise não preveja.
    """
    profundidade_de_classe = False
    pilha: list[bool] = []  # por grupo aberto: contém quantificador?
    i = 0
    while i < len(pattern):
        c = pattern[i]

        if c == "\\":
            i += 2
            continue

        if profundidade_de_classe:
            if c == "]":
                profundidade_de_classe = False
            i += 1
            continue

        if c == "[":
            profundidade_de_classe = True
            i += 1
            continue

        if c == "(":
            pilha.append(False)
            i += 1
            # Consome o prefixo de grupo especial — `(?:`, `(?=`, `(?!`, `(?<=`, `(?<!`,
            # `(?P<nome>`. Sem isto, o `?` do prefixo seria contado como quantificador e
            # todo grupo não-capturante viraria falso positivo: o nosso próprio
            # `unique_token` gera `(?<!…)` e `(?!…)`, e o catálogo usa `(?:…)` em quase
            # toda regra.
            if i < len(pattern) and pattern[i] == "?":
                prefixo = re.match(r"\?(?:P<[^>]*>|P=|[:=!>#]|<[=!])", pattern[i:])
                i += len(prefixo.group(0)) if prefixo else 1
            continue

        if c == ")":
            continha_quantificador = pilha.pop() if pilha else False
            # O que vem depois do fecha-parênteses decide: se o grupo é quantificado e
            # já continha quantificador dentro, é a forma perigosa.
            resto = pattern[i + 1 :]
            quantificado = bool(re.match(r"[*+?]|\{\d+(?:,\d*)?\}", resto))
            if continha_quantificador and quantificado:
                return True
            # Um grupo quantificado conta como quantificador para o grupo que o contém.
            if pilha and (continha_quantificador or quantificado):
                pilha[-1] = True
            i += 1
            continue

        eh_quantificador = c in "*+?" or (
            c == "{" and re.match(r"\{\d+(?:,\d*)?\}", pattern[i:])
        )
        if eh_quantificador and pilha:
            pilha[-1] = True

        i += 1

    return False


def unique_token(secret_regex: str, *, case_insensitive: bool = False) -> Pattern[str]:
    """Padrão para segredo cujo valor carrega a própria identidade.

    Envolve `secret_regex` em delimitadores que **não consomem**, de modo que dois
    segredos adjacentes sejam ambos encontrados.

    Levanta `ValueError` se o padrão puder começar por caractere não-word: o delimitador
    à esquerda nunca casaria e a regra seria falso negativo permanente e invisível —
    muito pior que falhar aqui, na construção.
    """
    if not secret_regex:
        raise ValueError("secret_regex vazio")
    primeiro = secret_regex[0]
    if not (primeiro.isalnum() or primeiro in "_[(\\"):
        raise ValueError(
            f"secret_regex começa com {primeiro!r}: o delimitador à esquerda nunca casaria, "
            f"e a regra seria falso negativo permanente"
        )

    flags = "(?i)" if case_insensitive else ""
    return re.compile(f"{flags}{_PREFIX}({secret_regex}){_SUFFIX}")


def literal_marker(secret_regex: str) -> Pattern[str]:
    """Padrão cujo **próprio literal** é a âncora — sem delimitador de palavra.

    Existe para casos como `-----BEGIN RSA PRIVATE KEY-----` e
    `PuTTY-User-Key-File-3:`, cujo texto é inconfundível e cujo primeiro caractere não é
    word. `unique_token` recusa esses padrões de propósito, porque para ele o
    delimitador à esquerda nunca casaria.

    Enfraquecer a guarda do `unique_token` para acomodá-los seria pior: ela protege
    contra a regra que nunca casa, que é falso negativo permanente e invisível. Um
    construtor estreito e nomeado deixa explícito **quais** padrões dispensam a
    delimitação, em vez de abrir uma exceção que qualquer regra futura poderia usar sem
    perceber.

    A disciplina do ADR D2 continua valendo: o teste do catálogo verifica quantificador
    livre em todos os padrões, venham do construtor que vierem.
    """
    if not secret_regex:
        raise ValueError("secret_regex vazio")
    return re.compile(f"({secret_regex})")


def keyword_assignment(keywords: Sequence[str], secret_regex: str) -> Pattern[str]:
    """Padrão para segredo sem identidade própria, ancorado por palavra-chave.

    Exige três âncoras — palavra-chave, operador de atribuição e delimitador —, que é o
    que impede um valor alfanumérico solto de virar finding. As palavras-chave são
    sempre case-insensitive, como em `generate.go:36-37`.
    """
    if not keywords:
        raise ValueError("keywords vazio: sem âncora, o padrão viraria genérico demais")

    alternativa = "|".join(re.escape(k) for k in keywords)
    return re.compile(
        rf"(?i:{alternativa}){_GAP}{_OPERATOR}{_GAP}{_QUOTE}({secret_regex}){_QUOTE}"
    )

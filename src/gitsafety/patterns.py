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
from typing import Pattern

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

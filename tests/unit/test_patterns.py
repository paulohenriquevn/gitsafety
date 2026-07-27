"""T1.1 — construtores de padrão (ADRs D1 e D2).

Escrever 40 regexes à mão garante que ao menos uma sai sem delimitação ou com
quantificador livre — erro de digitação com consequência de segurança. Os construtores
fazem a disciplina valer **por construção**, não por revisão.

`has_free_quantifier` é a rede do ADR D2: no `re` do Python, ao contrário do RE2 em que o
gitleaks roda, um quantificador livre pode produzir backtracking catastrófico. E desde o
M1 a regex roda dentro do `git commit` — patologia aqui não é lentidão, é o commit do
usuário pendurado.
"""

from __future__ import annotations

import pytest

from gitsafety.patterns import has_free_quantifier, keyword_assignment, unique_token

AWS = r"AKIA[0-9A-Z]{16}"
AWS_SAMPLE = "AKIAIOSFODNN7EXAMPLE"


# --- Família 1: token único ----------------------------------------------------


def test_unique_token_matches_the_value_alone():
    assert unique_token(AWS).search(AWS_SAMPLE)


@pytest.mark.parametrize(
    "contexto",
    [
        f'AWS_KEY = "{AWS_SAMPLE}"',
        f"AWS_KEY='{AWS_SAMPLE}'",
        f"export AWS_ACCESS_KEY_ID={AWS_SAMPLE}",
        f'{{"key": "{AWS_SAMPLE}"}}',
        f"aws_key: {AWS_SAMPLE}",
        f"# chave antiga: {AWS_SAMPLE}",
    ],
)
def test_unique_token_matches_the_value_in_real_code_contexts(contexto):
    """ADR D5: é assim que o segredo aparece de verdade, não como valor nu.

    Um padrão que casa o valor solto mas falha entre aspas passaria no teste e falharia
    no uso real — porque o sufixo delimitador precisa aceitar a aspa.
    """
    assert unique_token(AWS).search(contexto), contexto


@pytest.mark.parametrize(
    "quase",
    [
        f"X{AWS_SAMPLE}",  # colado à esquerda
        f"{AWS_SAMPLE}X",  # colado à direita
        "AKIAIOSFODNN7EXAMPL",  # 19 caracteres
        "akiaiosfodnn7example",  # minúsculas
    ],
)
def test_unique_token_does_not_match_near_misses(quase):
    """Caso negativo: é a delimitação que impede o falso positivo."""
    assert unique_token(AWS).fullmatch(quase) is None


def test_unique_token_finds_two_adjacent_secrets():
    """Divergência consciente do precedente.

    O gitleaks **consome** o delimitador no sufixo (`generate.go:31`). Em Python, com
    `finditer` sobre a linha inteira, consumir o espaço entre dois segredos faria o
    segundo desaparecer. Usamos lookahead, que verifica sem consumir.
    """
    texto = f"{AWS_SAMPLE} AKIA1234567890ABCDEF"
    assert len(unique_token(AWS).findall(texto)) == 2


def test_unique_token_rejects_a_prefix_starting_with_non_word():
    """Caso negativo: `\\b` antes de não-word gera padrão que nunca casa.

    Falhar na construção é muito melhor que gerar em silêncio uma regra morta — uma
    regra que nunca casa é falso negativo permanente e invisível.
    """
    with pytest.raises(ValueError):
        unique_token(r"-abc[0-9]{5}")


def test_unique_token_is_case_sensitive_by_default():
    assert unique_token(AWS).search(AWS_SAMPLE.lower()) is None


def test_unique_token_honours_case_insensitive_flag():
    assert unique_token(AWS, case_insensitive=True).search(AWS_SAMPLE.lower())


# --- Família 2: semi-genérica --------------------------------------------------


def test_keyword_assignment_matches_keyword_operator_value():
    p = keyword_assignment(["senha", "password"], r"[A-Za-z0-9]{8,32}")
    assert p.search('password = "hunter2abc"')


def test_keyword_assignment_requires_an_assignment_operator():
    """Caso negativo: sem operador é prosa, não atribuição."""
    p = keyword_assignment(["senha", "password"], r"[A-Za-z0-9]{8,32}")
    assert p.search("password hunter2abc") is None


def test_keyword_assignment_requires_the_keyword_nearby():
    """Caso negativo: valor sem palavra-chave por perto não é segredo identificável."""
    p = keyword_assignment(["senha", "password"], r"[A-Za-z0-9]{8,32}")
    assert p.search('algumacoisa = "hunter2abc"') is None


def test_keyword_assignment_is_case_insensitive_on_the_keyword():
    p = keyword_assignment(["password"], r"[A-Za-z0-9]{8,32}")
    assert p.search('PASSWORD = "hunter2abc"')


# --- A rede do ADR D2 ----------------------------------------------------------


@pytest.mark.parametrize("livre", [r"a*", r"a+", r"a{2,}", r"(ab)*", r"[a-z]+", r"x{10,}"])
def test_has_free_quantifier_detects_unbounded(livre):
    assert has_free_quantifier(livre) is True


@pytest.mark.parametrize(
    "limitado",
    [
        r"a{0,50}?",
        r"a{1,3}",
        r"[A-Z]{16}",
        r"AKIA[0-9A-Z]{16}",
        r"a\*",
        r"a\+",
        r"\{2,\}",
        # Regressão: `+` e `*` DENTRO de classe de caracteres são literais, não
        # quantificadores. A primeira versão do detector acusou este caso — e ele é
        # gerado pelo próprio `unique_token`.
        r"[\w./+-]",
        r"[*+]",
        r"[a-z*]{4,8}",
    ],
)
def test_has_free_quantifier_accepts_bounded_and_escaped(limitado):
    """Casos negativos do detector.

    `a\\*` é asterisco **literal**, não quantificador. Acusar aqui tornaria o detector
    ruidoso e alguém acabaria desligando-o — que é como uma defesa morre.
    """
    assert has_free_quantifier(limitado) is False


def test_constructors_never_introduce_a_free_quantifier():
    """A garantia que importa: o construtor não pode ser a origem do problema."""
    assert not has_free_quantifier(unique_token(AWS).pattern)
    assert not has_free_quantifier(keyword_assignment(["k"], r"[a-z]{4,16}").pattern)

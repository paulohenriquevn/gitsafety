"""T2.1 e T2.2 — provas mecânicas sobre o catálogo inteiro (ADRs D2, D3, D6).

Adaptação de `gitleaks/cmd/generate/config/utils/validate.go:16-39`, que verifica os dois
lados de cada regra e **mata o processo** se qualquer um falhar. Não podemos matar na
importação — seria hostil —, mas podemos tornar impossível uma regra chegar ao `main` sem
ter seus dois lados verificados: este teste falha e o CI barra.

Com 40+ regras, escrever um teste por regra à mão garante que alguém esquecerá o da 41ª —
e o esquecimento é silencioso, que é o pior tipo. Percorrer a tupla resolve por construção.
"""

from __future__ import annotations

import time

import pytest

from gitsafety.catalog import CATEGORIES
from gitsafety.patterns import has_free_quantifier
from gitsafety.rules import BUILTIN_RULES

#: `id=rule.id` para que a saída de falha diga qual regra quebrou, não "caso 27".
CASOS = [pytest.param(r, id=r.id) for r in BUILTIN_RULES]

#: Entradas construídas para forçar backtracking: **quase** casam. Uma cadeia que
#: satisfaz o prefixo e falha no fim é o que faz o motor voltar atrás repetidamente.
ADVERSARIAL = (
    "A" * 2000,
    "AKIA" + "A" * 2000,
    "sk-" + "a" * 2000,
    "ghp_" + "z" * 2000,
    "-----BEGIN " + "A" * 2000,
    "postgres://" + "u" * 500 + ":" + "p" * 500 + "@" + "h" * 500,
    "eyJ" + "a" * 1000 + "." + "b" * 1000,
    ("=" * 500) + ("'" * 500),
)

#: Unresolved Question Q1 do plano. Folgado o bastante para não ser flaky em CI,
#: apertado o bastante para pegar degradação de ordem de grandeza.
TETO_SEGUNDOS = 0.05


# --- ADR D3: os dois lados de cada regra ---------------------------------------


@pytest.mark.parametrize("rule", CASOS)
def test_every_rule_matches_all_of_its_true_positives(rule):
    for tp in rule.true_positives:
        assert rule.pattern.search(tp), f"{rule.id} não casou seu próprio exemplo: {tp!r}"


@pytest.mark.parametrize("rule", CASOS)
def test_every_rule_rejects_all_of_its_false_positives(rule):
    """A metade que a maioria das suítes esquece — e a que protege contra o Risco nº 1."""
    for fp in rule.false_positives:
        assert rule.pattern.search(fp) is None, f"{rule.id} casou indevidamente: {fp!r}"


@pytest.mark.parametrize("rule", CASOS)
def test_every_rule_carries_examples_on_both_sides(rule):
    """Sem isto, o default de tupla vazia deixa uma regra entrar sem exemplo nenhum."""
    assert rule.true_positives, f"{rule.id} sem true_positives"
    assert rule.false_positives, f"{rule.id} sem false_positives"


@pytest.mark.parametrize("rule", CASOS)
def test_every_rule_has_a_description(rule):
    assert rule.description.strip(), f"{rule.id} sem descrição"


# --- ADR D2: nenhum quantificador livre ----------------------------------------


@pytest.mark.parametrize("rule", CASOS)
def test_no_rule_uses_a_free_quantifier(rule):
    """Em `re` do Python isto é defesa, não estilo.

    O gitleaks roda em RE2, que não faz backtracking — para eles, quantificador limitado
    é higiene. Desde o M1 nossa regex roda dentro do `git commit`: aqui, uma regex
    patológica não é lentidão, é o commit do usuário pendurado.
    """
    assert not has_free_quantifier(rule.pattern.pattern), (
        f"{rule.id} tem quantificador sem teto: {rule.pattern.pattern}"
    )


# --- ADR D6: teto de tempo -----------------------------------------------------


@pytest.mark.parametrize("rule", CASOS)
def test_no_rule_takes_too_long_on_adversarial_input(rule):
    """A análise estática do D2 não pega tudo; só a medição prova.

    Há construção patológica sem quantificador livre (alternância aninhada com prefixos
    comuns, por exemplo). As duas verificações são complementares.
    """
    for entrada in ADVERSARIAL:
        inicio = time.perf_counter()
        rule.pattern.search(entrada)
        decorrido = time.perf_counter() - inicio
        assert decorrido < TETO_SEGUNDOS, (
            f"{rule.id} levou {decorrido:.4f}s em {entrada[:24]!r}…"
        )


# --- Invariantes do catálogo ---------------------------------------------------


def test_catalog_has_at_least_forty_rules():
    assert len(BUILTIN_RULES) >= 40, f"apenas {len(BUILTIN_RULES)} regras"


def test_rule_ids_are_unique():
    ids = [r.id for r in BUILTIN_RULES]
    duplicados = {i for i in ids if ids.count(i) > 1}
    assert not duplicados, f"ids duplicados: {duplicados}"


def test_every_readme_category_is_covered():
    """As 6 categorias que o `README.md § O que ele detecta` promete."""
    vazias = [nome for nome, regras in CATEGORIES.items() if not regras]
    assert not vazias, f"categorias sem regra: {vazias}"


def test_every_rule_id_is_kebab_case():
    """Id é identificador público — aparece na saída e no futuro `allow:` do M3."""
    import re as _re

    invalidos = [
        r.id for r in BUILTIN_RULES if not _re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", r.id)
    ]
    assert not invalidos, f"ids fora do padrão kebab-case: {invalidos}"


def test_no_rule_matches_another_rules_false_positive_by_accident():
    """Sobreposição entre regras é sinal de padrão largo demais.

    Não é falha da regra isolada — por isso teste separado —, mas um fp de A casando em B
    indica que B alcança mais do que deveria, que é o Risco nº 1 do M2 em outra forma.
    """
    sobreposicoes = []
    for a in BUILTIN_RULES:
        for fp in a.false_positives:
            for b in BUILTIN_RULES:
                if a.id != b.id and b.pattern.search(fp):
                    sobreposicoes.append((a.id, b.id, fp))
    assert not sobreposicoes, f"sobreposição entre regras: {sobreposicoes[:5]}"

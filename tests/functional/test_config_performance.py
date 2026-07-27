"""T3.1 — orçamento de carga da config.

A validação adversarial do ADR D3 acontece **na carga**, uma vez por invocação. Como é
justamente ela que protege o commit, é preciso saber que ela própria não o atrasa.
"""

from __future__ import annotations

from benchmarks.bench_config import measure_load

#: O hook tem 1 s de teto (`NFR-2`) e já gasta ~40 ms (medido no M1). 200 ms de folga
#: para a config é generoso e ainda deixa 4× de margem.
BUDGET_SECONDS = 0.2


def test_config_load_is_fast_enough_for_the_hook():
    assert measure_load(n_user_rules=10)["total_s"] < BUDGET_SECONDS


def test_validation_cost_grows_gently_with_user_rules():
    """A validação é linear no número de regras; o teste guarda a ordem de grandeza."""
    dez = measure_load(n_user_rules=10)
    cinquenta = measure_load(n_user_rules=50)
    assert cinquenta["total_s"] < dez["total_s"] * 10


def test_empty_config_is_essentially_free():
    assert measure_load(n_user_rules=0)["total_s"] < 0.05

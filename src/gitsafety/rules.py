"""Fachada pública das regras de detecção.

Existe para que `scanner.py` e `staged.py` continuem importando `BUILTIN_RULES` daqui
sem qualquer edição — o M2 é aditivo por construção.

O grafo real é `patterns` (o tipo `Rule` e os construtores) → `catalog` (os dados) →
`rules` (esta fachada). Quando `rules.py` acumulava o tipo **e** o registro, o catálogo
não podia ser um módulo à parte sem produzir import circular; separar as duas
responsabilidades resolveu a causa, não o sintoma.
"""

from __future__ import annotations

from gitsafety.catalog import BUILTIN_RULES, CATEGORIES
from gitsafety.patterns import Rule

#: A regra da AWS segue acessível pelo nome, como no M0.
AWS_ACCESS_KEY_ID = BUILTIN_RULES[0]

__all__ = ["AWS_ACCESS_KEY_ID", "BUILTIN_RULES", "CATEGORIES", "Rule"]

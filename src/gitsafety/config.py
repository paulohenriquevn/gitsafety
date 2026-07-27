"""Carregamento e validação de `.gitsafety.yml` (ADRs D1-D4).

Fronteira de entrada do usuário. Depois daqui, os dados são confiáveis — que é
exatamente o contrato de `rules/architecture.md § 1` para validação de borda.

**A decisão sem precedente deste módulo** está em `_compile_user_pattern`. Nenhum peer
legível protege contra regex patológica vinda da config: gitleaks usa `MustCompile`
(`config.go:124,127`), que entra em pânico com regex inválida e não tem defesa nenhuma
contra patologia — porque RE2 não faz backtracking e o problema não existe para eles.
ggshield não executa regex de usuário no cliente. Nós rodamos `re` dentro do `git commit`
desde o M1: aqui, regex patológica na config não é bug do usuário, é o nosso hook
pendurando o commit dele.
"""

from __future__ import annotations

import difflib
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from re import Pattern

import yaml
import yaml.parser
import yaml.scanner

from gitsafety.errors import ConfigError
from gitsafety.patterns import Rule, has_free_quantifier, has_nested_quantifier

CONFIG_FILENAME = ".gitsafety.yml"

#: As três chaves do `docs/PRD.md § FR-20`. Qualquer outra é erro (ADR D4).
KNOWN_KEYS = ("ignore", "allow", "rules")

#: Sonda **progressiva**: comprimentos crescentes, com aborto ao primeiro que exceder o
#: teto. A progressão é o que torna a medição segura — nunca se roda uma entrada longa
#: numa regex que já foi lenta numa curta, então o custo do pior caso fica limitado pelo
#: primeiro degrau, não pelo último.
#:
#: A primeira versão deste módulo media com uma sonda única de 4.000 caracteres e
#: **pendurou a suíte de testes**: uma regex patológica explode durante a própria
#: medição, e a verificação de tempo só é alcançada depois que a busca retorna. Daí a
#: defesa primária ser estática (`has_nested_quantifier`) e esta ser secundária.
_PROBE_LENGTHS = (16, 32, 64)

#: O mesmo teto do catálogo embutido (M2). Usar outro número exigiria justificar por que
#: a regra do usuário pode ser mais lenta que a nossa.
_USER_PATTERN_BUDGET_S = 0.05


@dataclass(frozen=True)
class Config:
    """Configuração efetiva. Vazia é o estado normal — a ferramenta é útil sem config."""

    ignore: tuple[str, ...] = ()
    allow: tuple[Pattern[str], ...] = field(default=())
    rules: tuple[Rule, ...] = ()


def find_config(start: Path) -> Path | None:
    """Procura `.gitsafety.yml` a partir da raiz do repositório.

    A config pertence ao repositório, não ao diretório de onde o usuário chamou —
    precedente `ggshield/core/config/utils.py:113-121`. Sem git, cai para `start`, porque
    o `scan` funciona fora de repositório desde o M0.
    """
    from gitsafety.git import is_git_repository, repo_root

    base = repo_root(start) if is_git_repository(start) else start
    candidato = base / CONFIG_FILENAME
    return candidato if candidato.is_file() else None


def _compile_user_pattern(raw: str, *, contexto: str) -> Pattern[str]:
    """Compila um padrão do usuário depois de três verificações (ADR D3).

    1. **Compila** — regex inválida vira erro tipado nomeando a origem, nunca stack trace.
    2. **Analisa** — quantificador livre é recusado, como no catálogo embutido (M2 D2).
    3. **Analisa a forma aninhada** — `(a{1,50}){1,50}` tem todos os limites definidos,
       então a verificação de quantificador livre não a alcança; a de aninhamento sim.
       Esta é a defesa **primária** contra patologia, e é estática de propósito.
    4. **Mede** — sonda curta e progressiva, como rede secundária para formas que a
       análise não preveja.

    Rejeitar na carga é o ponto: uma vez aceito, o padrão roda dentro do `git commit`.
    """
    if not isinstance(raw, str):
        raise ConfigError(f"{contexto}: o padrão precisa ser texto, e não {type(raw).__name__}")

    try:
        compilado = re.compile(raw)
    except re.error as exc:
        raise ConfigError(f"{contexto}: expressão regular inválida — {exc}") from exc

    if has_free_quantifier(raw):
        raise ConfigError(
            f"{contexto}: o padrão tem quantificador sem teto (`*`, `+` ou `{{n,}}`).\n"
            f"Use um limite superior, como `{{1,20}}`: um padrão sem teto pode fazer a "
            f"verificação demorar indefinidamente no meio de um commit."
        )

    # Defesa PRIMÁRIA e estática: a forma perigosa é reconhecida sem ser executada.
    if has_nested_quantifier(raw):
        raise ConfigError(
            f"{contexto}: o padrão tem um grupo repetido dentro de outro grupo repetido "
            f"— por exemplo `(a{{1,50}}){{1,50}}`.\n"
            f"Essa forma pode levar tempo exponencial e travar a verificação durante um "
            f"commit, mesmo com todos os limites definidos. Reescreva sem o aninhamento."
        )

    # Rede SECUNDÁRIA: cobre formas que a análise estática não preveja. Progressiva e com
    # aborto no primeiro degrau lento, para que a própria medição não possa explodir.
    for comprimento in _PROBE_LENGTHS:
        for sonda in ("a" * comprimento, "ab" * (comprimento // 2), "=" * comprimento):
            inicio = time.perf_counter()
            compilado.search(sonda)
            decorrido = time.perf_counter() - inicio
            if decorrido >= _USER_PATTERN_BUDGET_S:
                raise ConfigError(
                    f"{contexto}: o padrão levou {decorrido:.3f}s numa entrada de teste de "
                    f"apenas {comprimento} caracteres (limite {_USER_PATTERN_BUDGET_S}s).\n"
                    f"Numa entrada real, de milhares de caracteres, isso travaria a "
                    f"verificação durante um commit. Simplifique o padrão."
                )

    return compilado


def _require_list(valor: object, *, chave: str) -> list:
    if not isinstance(valor, list):
        raise ConfigError(
            f"a chave `{chave}` precisa ser uma lista, e não {type(valor).__name__}"
        )
    return valor


def _parse_rules(bruto: object) -> tuple[Rule, ...]:
    regras: list[Rule] = []
    for indice, item in enumerate(_require_list(bruto, chave="rules")):
        contexto = f"rules[{indice}]"
        if not isinstance(item, dict):
            raise ConfigError(
                f"{contexto}: cada regra precisa ser um mapeamento com `id` e `pattern`"
            )

        rule_id = item.get("id")
        if not rule_id or not isinstance(rule_id, str):
            raise ConfigError(f"{contexto}: falta o campo `id`")

        contexto = f"rules[{indice}] (`{rule_id}`)"
        bruto_pattern = item.get("pattern")
        if bruto_pattern is None:
            raise ConfigError(f"{contexto}: falta o campo `pattern`")

        regras.append(
            Rule(
                id=rule_id,
                description=item.get("description") or f"Regra do usuário: {rule_id}",
                pattern=_compile_user_pattern(bruto_pattern, contexto=contexto),
            )
        )
    return tuple(regras)


def _parse_allow(bruto: object) -> tuple[Pattern[str], ...]:
    compilados = []
    for indice, item in enumerate(_require_list(bruto, chave="allow")):
        compilados.append(_compile_user_pattern(item, contexto=f"allow[{indice}]"))
    return tuple(compilados)


def _parse_ignore(bruto: object) -> tuple[str, ...]:
    itens = _require_list(bruto, chave="ignore")
    for indice, item in enumerate(itens):
        if not isinstance(item, str):
            raise ConfigError(f"ignore[{indice}]: cada entrada precisa ser texto")
    return tuple(itens)


def _reject_unknown_keys(dados: dict) -> None:
    """Chave desconhecida é erro, com sugestão da mais próxima (ADR D4).

    Ignorar em silêncio faria a config nunca ser lida, e o usuário concluiria que o
    gitsafety não funciona — quando o problema é uma letra trocada.
    """
    for chave in dados:
        if chave in KNOWN_KEYS:
            continue
        proximas = difflib.get_close_matches(str(chave), KNOWN_KEYS, n=1)
        sugestao = f" Você quis dizer `{proximas[0]}`?" if proximas else ""
        raise ConfigError(
            f"chave desconhecida `{chave}`.{sugestao}\n"
            f"As chaves aceitas são: {', '.join(KNOWN_KEYS)}."
        )


def load_config(path: Path | None = None, *, start: Path | None = None) -> Config:
    """Carrega a configuração efetiva.

    Dois contratos diferentes, de propósito:

    - `path` explícito (`--config`) — o arquivo é **obrigatório**; ausente é erro de uso.
    - descoberta implícita — ausente é normal e devolve config vazia (`FR-22`).
    """
    if path is not None:
        alvo: Path | None = Path(path)
        if not alvo.is_file():  # type: ignore[union-attr]
            raise ConfigError(f"arquivo de configuração não encontrado: {alvo}")
    else:
        alvo = find_config(Path(start) if start is not None else Path.cwd())

    if alvo is None:
        return Config()

    try:
        # `safe_load`, nunca `load`: `load` executa construtores arbitrários e seria a
        # porta de execução de código via arquivo de configuração (ADR D1).
        dados = yaml.safe_load(alvo.read_text(encoding="utf-8")) or {}
    except (yaml.parser.ParserError, yaml.scanner.ScannerError) as exc:
        # As DUAS classes: estrutura inválida levanta ParserError, token inválido levanta
        # ScannerError. Capturar só a primeira deixa metade dos malformados escapar.
        # O `str(exc)` do PyYAML já traz arquivo, linha e coluna — não reconstruir.
        raise ConfigError(f"{alvo} não é um YAML válido:\n{exc}") from exc

    if not isinstance(dados, dict):
        raise ConfigError(
            f"{alvo}: o conteúdo precisa ser um mapeamento de chaves, "
            f"e não {type(dados).__name__}"
        )

    _reject_unknown_keys(dados)

    return Config(
        ignore=_parse_ignore(dados["ignore"]) if "ignore" in dados else (),
        allow=_parse_allow(dados["allow"]) if "allow" in dados else (),
        rules=_parse_rules(dados["rules"]) if "rules" in dados else (),
    )


def effective_rules(config: Config, builtin: Sequence[Rule]) -> tuple[Rule, ...]:
    """Catálogo embutido mais as regras do usuário.

    O usuário **acrescenta**, não substitui: desligar um padrão embutido é o que o
    `allow:` faz, e para um valor específico em vez de para a regra inteira.
    """
    return (*builtin, *config.rules)

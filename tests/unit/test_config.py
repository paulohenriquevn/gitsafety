"""T1.1 e T1.2 — carga da config e validação de regex do usuário (ADRs D1-D4).

O teste que carrega o milestone é
`test_pathological_user_regex_is_rejected_before_execution`. Ele cobre a decisão **sem
precedente** do M3: nenhum peer legível protege contra regex patológica de usuário, porque
nenhum precisa — gitleaks roda em RE2 (sem backtracking) e ggshield não executa regex de
usuário no cliente. Nós rodamos `re` dentro do `git commit`, então uma regex patológica na
config não é bug do usuário: é o nosso hook pendurando o commit dele.
"""

from __future__ import annotations

import pytest

from gitsafety.config import CONFIG_FILENAME, Config, load_config
from gitsafety.errors import ConfigError, ExitCode


def _write(tmp_path, conteudo: str):
    (tmp_path / CONFIG_FILENAME).write_text(conteudo, encoding="utf-8")


# --- Carga: os três estados que o código óbvio confunde ------------------------


def test_missing_config_file_returns_empty_config(tmp_path):
    """`docs/PRD.md § FR-22`: a ferramenta é útil com zero configuração."""
    cfg = load_config(start=tmp_path)
    assert cfg == Config()


def test_empty_config_file_returns_empty_config(tmp_path):
    """Edge case: `safe_load` de arquivo em branco devolve `None`, não `{}`."""
    _write(tmp_path, "")
    assert load_config(start=tmp_path) == Config()


def test_config_with_only_comments_returns_empty_config(tmp_path):
    _write(tmp_path, "# só um comentário\n")
    assert load_config(start=tmp_path) == Config()


# --- Casos negativos de forma ---------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "conteudo"),
    [
        ("aspas nao fechadas", 'ignore: "nao fecha\n'),  # ScannerError
        ("colchete aberto", "ignore: [a, b\n"),  # ParserError
        ("dois-pontos duplo", "a: b: c\n"),  # ScannerError
    ],
)
def test_malformed_yaml_raises_with_the_line_number(tmp_path, nome, conteudo):
    """`FR-23`: erro apontando a linha. O `str(e)` do PyYAML já a traz.

    Os três casos cobrem as **duas** classes de exceção do PyYAML: `ScannerError` (token
    inválido) e `ParserError` (estrutura inválida). Capturar só uma deixaria metade dos
    arquivos malformados escapar como exceção não tratada — que é o motivo de o
    precedente (`ggshield/core/config/utils.py:52`) capturar as duas.
    """
    _write(tmp_path, conteudo)
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "line" in str(exc.value).lower(), f"{nome}: mensagem sem a linha"


def test_top_level_list_is_rejected(tmp_path):
    """YAML sintaticamente válido, forma errada — passa pelo parser e explodiria adiante."""
    _write(tmp_path, "- a\n- b\n")
    with pytest.raises(ConfigError):
        load_config(start=tmp_path)


def test_unknown_key_is_rejected_with_a_suggestion(tmp_path):
    """O silêncio aqui custaria uma sessão de depuração ao usuário.

    Ignorar `ignroe:` faria a config nunca ser lida, e a pessoa concluiria que o
    gitsafety não funciona.
    """
    _write(tmp_path, "ignroe:\n  - a\n")
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "ignore" in str(exc.value)


def test_ignore_must_be_a_list(tmp_path):
    _write(tmp_path, 'ignore: "uma string"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "ignore" in str(exc.value)


def test_config_error_carries_the_usage_exit_code():
    assert ConfigError("qualquer").exit_code == ExitCode.USAGE_ERROR


# --- Caminho feliz --------------------------------------------------------------


def test_ignore_entries_are_loaded(tmp_path):
    _write(tmp_path, "ignore:\n  - 'tests/fixtures/**'\n  - '*.lock'\n")
    assert load_config(start=tmp_path).ignore == ("tests/fixtures/**", "*.lock")


def test_allow_entries_are_compiled(tmp_path):
    _write(tmp_path, 'allow:\n  - "AKIAIOSFODNN7EXAMPLE"\n')
    cfg = load_config(start=tmp_path)
    assert len(cfg.allow) == 1
    assert cfg.allow[0].search("AKIAIOSFODNN7EXAMPLE")


def test_user_rule_is_loaded_and_usable(tmp_path):
    _write(tmp_path, 'rules:\n  - id: chave-interna\n    pattern: "INT_[A-Z0-9]{10}"\n')
    cfg = load_config(start=tmp_path)
    assert len(cfg.rules) == 1
    assert cfg.rules[0].id == "chave-interna"
    assert cfg.rules[0].pattern.search('k = "INT_ABCDE12345"')


def test_explicit_path_is_used(tmp_path):
    outro = tmp_path / "outro.yml"
    outro.write_text("ignore:\n  - 'x/**'\n", encoding="utf-8")
    assert load_config(path=outro).ignore == ("x/**",)


def test_explicit_missing_path_is_an_error(tmp_path):
    """Contrato diferente do implícito: pedir um arquivo que não existe é erro de uso."""
    with pytest.raises(ConfigError):
        load_config(path=tmp_path / "nao-existe.yml")


# --- ADR D3: regex do usuário é entrada não confiável --------------------------


def test_invalid_user_regex_raises_naming_the_rule(tmp_path):
    """Caso negativo: o gitleaks entraria em pânico aqui (`config.go:124,127`)."""
    _write(tmp_path, 'rules:\n  - id: quebrada\n    pattern: "[unclosed"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "quebrada" in str(exc.value)


def test_user_regex_with_free_quantifier_is_rejected(tmp_path):
    """A defesa do M2, aplicada a uma origem não confiável."""
    _write(tmp_path, 'rules:\n  - id: larga\n    pattern: ".*"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "larga" in str(exc.value)


def test_pathological_user_regex_is_rejected_before_execution(tmp_path):
    """O NÚCLEO DO RISCO Nº 2 — a decisão sem precedente deste milestone.

    `(a{1,50}){1,50}b` tem todos os quantificadores limitados, então `has_free_quantifier`
    do M2 **não** a pega — é `has_nested_quantifier` que a alcança, e ela é **estática**
    de propósito.

    A primeira implementação deste módulo tentou pegar o caso **medindo**, com uma sonda
    de 4.000 caracteres, e pendurou a suíte de testes: uma regex patológica explode
    durante a própria medição, e a verificação de tempo só é alcançada depois que a busca
    retorna. A defesa não pode depender de executar aquilo de que protege.
    """
    _write(tmp_path, 'rules:\n  - id: patologica\n    pattern: "(a{1,50}){1,50}b"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "patologica" in str(exc.value)


def test_allow_entries_go_through_the_same_checks(tmp_path):
    """Um `allow` patológico penduraria o commit igual a um `rules` patológico."""
    _write(tmp_path, 'allow:\n  - "(a{1,50}){1,50}b"\n')
    with pytest.raises(ConfigError):
        load_config(start=tmp_path)


def test_user_rule_without_id_is_rejected(tmp_path):
    _write(tmp_path, 'rules:\n  - pattern: "INT_[A-Z0-9]{10}"\n')
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "id" in str(exc.value)


def test_user_rule_without_pattern_is_rejected(tmp_path):
    _write(tmp_path, "rules:\n  - id: sem-padrao\n")
    with pytest.raises(ConfigError) as exc:
        load_config(start=tmp_path)
    assert "pattern" in str(exc.value)

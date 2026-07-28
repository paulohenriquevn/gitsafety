"""T3.1 — métrica de falso positivo contra corpus limpo (ADR D7).

`ROADMAP.md § M2` DoD nº 3 e `docs/API.md § Limitações`: falso positivo é a métrica
que decide se a ferramenta é tolerável. Um catálogo que acusa código legítimo é
desinstalado na segunda semana, e ferramenta desinstalada tem taxa de detecção zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures.clean_corpus import NEAR_MISS_SHAPES, build_clean_corpus  # noqa: E402

from gitsafety.scanner import scan_path  # noqa: E402


def test_clean_corpus_produces_zero_findings(tmp_path):
    """A métrica do DoD. A mensagem de falha diz **qual** regra acusou e **o quê**."""
    # Arrange
    build_clean_corpus(tmp_path)

    # Act
    resultado = scan_path(tmp_path)

    # Assert
    acusacoes = [
        f"{f.rule_id} em {f.path.name}:{f.line} → {f.secret!r}" for f in resultado.findings
    ]
    assert resultado.findings == [], acusacoes


def test_clean_corpus_contains_the_near_miss_shapes(tmp_path):
    """Um corpus trivial passaria mesmo com um catálogo cheio de padrões largos.

    Este teste garante que o corpus continua sendo um teste de verdade quando alguém
    editar o gerador no futuro.
    """
    # Arrange
    build_clean_corpus(tmp_path)
    conteudo = "\n".join(
        p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file()
    ).lower()

    # Assert — as formas que um padrão largo demais confundiria com credencial.
    for forma in ("sha256", "uuid" if "uuid" in conteudo else "550e8400", "base64", "ssh-rsa"):
        assert forma.lower() in conteudo, f"corpus perdeu a forma {forma!r}"


def test_clean_corpus_has_files_in_subdirectories(tmp_path):
    n = build_clean_corpus(tmp_path)
    assert n == len(NEAR_MISS_SHAPES)
    assert len(list(tmp_path.rglob("*.py"))) >= 5


def test_public_key_headers_do_not_trigger_the_private_key_rule(tmp_path):
    """Caso negativo dirigido: a diferença entre PUBLIC e PRIVATE é uma palavra."""
    # Arrange
    (tmp_path / "chaves.py").write_text(
        'PUB = "-----BEGIN PUBLIC KEY-----"\nCERT = "-----BEGIN CERTIFICATE-----"\n',
        encoding="utf-8",
    )

    # Act / Assert
    assert scan_path(tmp_path).findings == []


def test_local_connection_strings_without_password_do_not_trigger(tmp_path):
    """Caso negativo dirigido: URL de banco sem senha é config de desenvolvimento."""
    (tmp_path / "cfg.py").write_text(
        'A = "postgresql://localhost:5432/dev"\nB = "redis://localhost:6379"\n',
        encoding="utf-8",
    )
    assert scan_path(tmp_path).findings == []


def test_connection_string_is_detected_when_followed_by_a_path(tmp_path):
    """Regressão: encontrado na validação de integração do M2.

    `postgresql://app:senha@db.com/prod` NÃO era detectado. O lookahead final de
    `unique_token` rejeita `/`, e no uso real o host é sempre seguido do caminho do
    banco. Strings de conexão são auto-ancoradas pelo próprio esquema, como os blocos
    PEM — o `unique_token` era o construtor errado para elas.

    Falso negativo silencioso é a categoria mais cara para este produto, e este passou
    por todos os testes unitários porque os exemplos da regra terminavam no host.
    """
    # Arrange
    (tmp_path / "cfg.py").write_text(
        'DB = "postgresql://app:s3nh4Sup3r@db.exemplo.com/prod"\n'
        'MONGO = "mongodb+srv://u:p4ssw0rd@cluster.mongodb.net/app?retryWrites=true"\n',
        encoding="utf-8",
    )

    # Act
    resultado = scan_path(tmp_path)

    # Assert
    ids = {f.rule_id for f in resultado.findings}
    assert "postgres-connection-string" in ids
    assert "mongodb-connection-string" in ids

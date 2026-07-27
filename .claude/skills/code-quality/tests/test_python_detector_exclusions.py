"""Regressão: o detector de dead code não pode auditar código de terceiros.

Defeito encontrado em 2026-07-27 no gitsafety: `PythonDetector.detect_dead_code`
invocava `vulture <repo_root>` sem nenhuma exclusão, varrendo `.venv/` (bibliotecas
de terceiros), `knowledge-base/references/` (repositórios clonados para estudo) e
`.claude/skills/` (ferramental do ecossistema).

O resultado eram 147 achados HARD e veredito `FAIL_HARD` — bloqueando `/review` — em
um projeto cujo código de produto tinha **zero** símbolos mortos. Um gate que reprova
por código que não é do projeto é pior do que gate nenhum: ensina o time a ignorá-lo.

`code-quality-golden-rule.md § 8` declara que a regra existe para impedir que
"exports mortos se acumulem" no código do projeto. Virtualenv não é código do projeto.
"""

from __future__ import annotations

from pathlib import Path

from detectors.python import PythonDetector

# Diretórios que nunca contêm código de autoria do projeto sob auditoria.
THIRD_PARTY_DIRS = [
    ".venv",
    "venv",
    "node_modules",
    "knowledge-base/references",
    "site-packages",
]


def test_dead_code_command_excludes_third_party_directories():
    # Arrange
    detector = PythonDetector()

    # Act
    cmd = detector.build_dead_code_command(Path("/repo"))

    # Assert — a exclusão precisa chegar ao vulture, não ficar só na intenção.
    joined = " ".join(cmd)
    assert "--exclude" in joined, f"vulture invocado sem exclusão: {joined}"
    for directory in THIRD_PARTY_DIRS:
        assert directory in joined, f"diretório de terceiros não excluído: {directory}"


def test_dead_code_command_still_targets_the_repo_root():
    # A exclusão não pode ter o efeito colateral de deixar de auditar o projeto.
    detector = PythonDetector()
    cmd = detector.build_dead_code_command(Path("/repo"))
    assert "/repo" in " ".join(cmd)


def test_dead_code_command_invokes_vulture():
    detector = PythonDetector()
    assert detector.build_dead_code_command(Path("/repo"))[0] == "vulture"

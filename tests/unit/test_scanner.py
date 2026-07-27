"""T2.4 — orquestração da varredura (ADRs D2 e D7).

Dois defeitos clássicos deste tipo de código são cobertos explicitamente:

- **Off-by-one em arquivo sem newline final** — a divergência entre `splitlines()` e
  iterar o file object aparece justamente quando o arquivo não termina em `\\n`.
- **Segundo segredo na mesma linha perdido** — usar `search` em vez de `finditer`
  acha só o primeiro, e o segundo some sem qualquer sinal.

Ambos produzem falso negativo silencioso, que é a categoria de defeito mais cara para
um detector de segredos.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from gitsafety.scanner import ScanResult, scan_path
from gitsafety.walker import MAX_FILE_BYTES, SkipReason

SECRET = "AKIAIOSFODNN7EXAMPLE"
OTHER_SECRET = "AKIA1234567890ABCDEF"


def test_scan_finds_the_secret_and_reports_a_one_based_line(tmp_path):
    # Arrange
    (tmp_path / "cfg.py").write_text(f'x = 1\nkey = "{SECRET}"\n')

    # Act
    result = scan_path(tmp_path)

    # Assert
    assert len(result.findings) == 1
    assert result.findings[0].line == 2
    assert result.findings[0].secret == SECRET
    assert result.findings[0].rule_id == "aws-access-key-id"


def test_line_number_is_correct_when_file_has_no_trailing_newline(tmp_path):
    """Edge case: arquivo que não termina em `\\n`."""
    # Arrange — sem \n final, de propósito.
    (tmp_path / "a.txt").write_text(f"primeira\n{SECRET}")

    # Act
    result = scan_path(tmp_path)

    # Assert
    assert result.findings[0].line == 2


def test_secret_on_the_very_first_line_is_line_one(tmp_path):
    # Edge case da outra ponta: garantir que a numeração começa em 1, não em 0.
    (tmp_path / "a.txt").write_text(f"{SECRET}\nresto\n")
    assert scan_path(tmp_path).findings[0].line == 1


def test_two_secrets_on_the_same_line_produce_two_findings(tmp_path):
    """Caso negativo para `search`: ele acharia só o primeiro."""
    # Arrange
    (tmp_path / "a.txt").write_text(f"{SECRET} e também {OTHER_SECRET}\n")

    # Act
    result = scan_path(tmp_path)

    # Assert
    assert len(result.findings) == 2
    assert {f.secret for f in result.findings} == {SECRET, OTHER_SECRET}


def test_secrets_in_different_files_are_all_reported(tmp_path):
    # Arrange
    (tmp_path / "a.py").write_text(f"{SECRET}\n")
    (tmp_path / "b.py").write_text(f"{OTHER_SECRET}\n")

    # Act / Assert
    assert len(scan_path(tmp_path).findings) == 2


def test_clean_directory_reports_no_findings(tmp_path):
    # Arrange
    (tmp_path / "ok.py").write_text("print('hello')\n")

    # Act
    result = scan_path(tmp_path)

    # Assert
    assert result.findings == []
    assert result.has_findings is False


def test_scan_result_carries_skipped_files_through(tmp_path):
    """ADR D7: o `skipped` do walker chega intacto ao chamador."""
    # Arrange
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    (tmp_path / "ok.py").write_text("x = 1\n")

    # Act
    result = scan_path(tmp_path)

    # Assert
    assert [s.reason for s in result.skipped] == [SkipReason.BINARY]


def test_oversized_file_is_never_scanned_even_if_it_holds_a_secret(tmp_path):
    """O custo declarado do limite de tamanho, tornado explícito por teste."""
    # Arrange
    grande = tmp_path / "dump.txt"
    grande.write_text(f"{SECRET}\n" + "x" * MAX_FILE_BYTES)

    # Act
    result = scan_path(tmp_path)

    # Assert — o segredo não é achado, MAS o arquivo aparece como pulado.
    assert result.findings == []
    assert [s.reason for s in result.skipped] == [SkipReason.TOO_LARGE]


def test_undecodable_bytes_do_not_abort_the_scan(tmp_path):
    """ADR D2: `errors="replace"` nunca levanta, então nenhum arquivo derruba a varredura."""
    # Arrange
    (tmp_path / "weird.txt").write_bytes(b"\xff\xfe caf\xe9\n" + SECRET.encode() + b"\n")

    # Act
    result = scan_path(tmp_path)

    # Assert
    assert result.has_findings


def test_one_undecodable_file_does_not_hide_secrets_in_the_others(tmp_path):
    """O modo de falha que importa: um arquivo problemático não pode cegar os demais."""
    # Arrange
    (tmp_path / "weird.bin_txt").write_bytes(b"\xff\xfe\xff\xfe")
    (tmp_path / "app.py").write_text(f"{SECRET}\n")

    # Act
    result = scan_path(tmp_path)

    # Assert
    assert len(result.findings) == 1


def test_has_findings_is_true_when_something_was_found(tmp_path):
    (tmp_path / "a.py").write_text(f"{SECRET}\n")
    assert scan_path(tmp_path).has_findings is True


def test_scan_result_is_immutable(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    result = scan_path(tmp_path)
    with pytest.raises(FrozenInstanceError):
        result.findings = []  # type: ignore[misc]


def test_scan_result_type_is_returned(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    assert isinstance(scan_path(tmp_path), ScanResult)

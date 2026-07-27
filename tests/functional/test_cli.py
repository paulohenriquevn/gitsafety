"""T3.1 — a CLI: contrato de saída e de exit code.

Este é o **wiring** do M0: sem ele os módulos anteriores são código morto. Os testes
aqui exercem `main()` de ponta a ponta — é a fronteira que o usuário toca.

O teste mais importante do arquivo é
`test_output_masks_the_secret_by_default`: um detector de segredos cujo relatório
vaza o segredo transformou-se no problema que ele deveria resolver.
"""

from __future__ import annotations

import pytest

from gitsafety.cli import main
from gitsafety.errors import ExitCode

SECRET = "AKIAIOSFODNN7EXAMPLE"


@pytest.fixture
def dir_limpo(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n")
    return tmp_path


@pytest.fixture
def dir_com_segredo(tmp_path):
    (tmp_path / "config.py").write_text(f'API_KEY = "{SECRET}"\n')
    return tmp_path


# --- Exit codes (PRD FR-18) ----------------------------------------------------


def test_exit_code_is_zero_when_nothing_is_found(dir_limpo):
    assert main(["scan", str(dir_limpo)]) == ExitCode.SUCCESS


def test_exit_code_is_one_when_a_secret_is_found(dir_com_segredo):
    assert main(["scan", str(dir_com_segredo)]) == ExitCode.SECRETS_FOUND


def test_exit_code_is_two_when_path_does_not_exist(tmp_path):
    """Caso negativo: caminho errado é erro, nunca 'limpo'."""
    assert main(["scan", str(tmp_path / "inexistente")]) == ExitCode.USAGE_ERROR


def test_error_message_names_the_missing_path(tmp_path, capsys):
    # Act
    main(["scan", str(tmp_path / "fantasma")])

    # Assert — mensagem específica, não "erro inesperado".
    err = capsys.readouterr().err
    assert "fantasma" in err


# --- Mascaramento (PRD NFR-4) --------------------------------------------------


def test_output_masks_the_secret_by_default(dir_com_segredo, capsys):
    """O relatório não pode virar o próximo vazamento."""
    # Act
    main(["scan", str(dir_com_segredo)])

    # Assert
    out = capsys.readouterr().out
    assert SECRET not in out
    assert "AKIA" in out  # o prefixo fica: identifica o provedor sem expor a chave


def test_show_secrets_flag_reveals_the_full_value(dir_com_segredo, capsys):
    # Act
    main(["scan", str(dir_com_segredo), "--show-secrets"])

    # Assert
    assert SECRET in capsys.readouterr().out


# --- Forma da saída (PRD FR-15) ------------------------------------------------


def test_output_reports_file_line_and_rule(dir_com_segredo, capsys):
    # Act
    main(["scan", str(dir_com_segredo)])

    # Assert
    out = capsys.readouterr().out
    assert "config.py" in out
    assert ":1" in out
    assert "aws-access-key-id" in out


def test_output_reports_how_many_files_were_skipped(tmp_path, capsys):
    """ADR D3 na superfície: o pulo precisa ser visível para o usuário."""
    # Arrange
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    (tmp_path / "app.py").write_text("x = 1\n")

    # Act
    main(["scan", str(tmp_path)])

    # Assert
    assert "pulado" in capsys.readouterr().out.lower()


def test_clean_scan_does_not_mention_skipped_files_when_there_are_none(dir_limpo, capsys):
    # Ruído desnecessário mina a confiança tanto quanto falso positivo.
    main(["scan", str(dir_limpo)])
    assert "pulado" not in capsys.readouterr().out.lower()


def test_output_tells_the_user_to_revoke_the_key(dir_com_segredo, capsys):
    """PRD FR-19: remover a linha não desfaz a exposição."""
    main(["scan", str(dir_com_segredo)])
    assert "revogue" in capsys.readouterr().out.lower()


# --- Superfície da CLI ---------------------------------------------------------


def test_help_advertises_staged_now_that_it_exists(capsys):
    """`--staged` passou a existir no M1 — o `--help` deve anunciá-la.

    Este teste era `test_help_does_not_advertise_flags_that_do_not_exist_yet` no M0 e
    assertava o oposto. A mudança é intencional, e o teste existe justamente para forçar
    que ela seja consciente: alterar o contrato público sem tocar num teste vermelho é
    como um contrato muda por acidente.
    """
    # Act
    with pytest.raises(SystemExit):
        main(["scan", "--help"])

    # Assert
    assert "--staged" in capsys.readouterr().out


def test_help_still_does_not_advertise_history(capsys):
    """`--history` continua sendo M5 — anunciá-la agora seria mentir."""
    with pytest.raises(SystemExit):
        main(["scan", "--help"])
    assert "--history" not in capsys.readouterr().out


def test_version_flag_prints_the_version(capsys):
    # Act
    codigo = main(["--version"])

    # Assert
    assert codigo == ExitCode.SUCCESS
    assert "gitsafety" in capsys.readouterr().out


def test_scan_without_path_defaults_to_current_directory(dir_limpo, monkeypatch):
    """PRD FR-3: sem argumento posicional, o alvo é o diretório atual."""
    # Arrange
    monkeypatch.chdir(dir_limpo)

    # Act / Assert
    assert main(["scan"]) == ExitCode.SUCCESS


def test_unknown_flag_is_a_usage_error(dir_limpo):
    # Caso negativo: argparse sai com 2, que é exatamente o nosso USAGE_ERROR.
    with pytest.raises(SystemExit) as exc:
        main(["scan", str(dir_limpo), "--flag-que-nao-existe"])
    assert exc.value.code == ExitCode.USAGE_ERROR

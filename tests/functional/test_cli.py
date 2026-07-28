"""T3.1 — a CLI: contrato de saída e de exit code.

Este é o **wiring** do M0: sem ele os módulos anteriores são código morto. Os testes
aqui exercem `main()` de ponta a ponta — é a fronteira que o usuário toca.

O teste mais importante do arquivo é
`test_output_masks_the_secret_by_default`: um detector de segredos cujo relatório
vaza o segredo transformou-se no problema que ele deveria resolver.
"""

from __future__ import annotations

import argparse

import pytest

from gitsafety.cli import build_parser, main
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


# --- Exit codes (`docs/API.md` § Códigos de saída) ------------------------------


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


# --- Mascaramento (`docs/API.md` § Mascaramento) --------------------------------


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


# --- Forma da saída (`docs/API.md` § Formato de saída) --------------------------


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
    """`docs/API.md` § Formato de saída: remover a linha não desfaz a exposição."""
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


def test_help_advertises_history_now_that_it_exists(capsys):
    """`--history` chegou no M5.

    A versão anterior deste teste afirmava o **oposto** — que a flag não podia aparecer na
    ajuda — porque anunciar o que não existe é mentir para quem lê o `--help`. Ele cumpriu
    seu papel de M0 a M4 e agora inverte, que é o que um teste de contrato deve fazer quando
    o contrato muda.
    """
    with pytest.raises(SystemExit):
        main(["scan", "--help"])
    assert "--history" in capsys.readouterr().out


def test_version_flag_prints_the_version(capsys):
    # Act
    codigo = main(["--version"])

    # Assert
    assert codigo == ExitCode.SUCCESS
    assert "gitsafety" in capsys.readouterr().out


def test_scan_without_path_defaults_to_current_directory(dir_limpo, monkeypatch):
    """`docs/API.md` § `gitsafety scan`: sem posicional, o alvo é o diretório atual."""
    # Arrange
    monkeypatch.chdir(dir_limpo)

    # Act / Assert
    assert main(["scan"]) == ExitCode.SUCCESS


def test_unknown_flag_is_a_usage_error(dir_limpo):
    # Caso negativo: argparse sai com 2, que é exatamente o nosso USAGE_ERROR.
    with pytest.raises(SystemExit) as exc:
        main(["scan", str(dir_limpo), "--flag-que-nao-existe"])
    assert exc.value.code == ExitCode.USAGE_ERROR


# --- M3: configuração -----------------------------------------------------------


def test_config_flag_loads_the_given_file(tmp_path, capsys):
    """`FR-21`: `--config PATH` aponta outro arquivo."""
    (tmp_path / "config.py").write_text(f'K = "{SECRET}"\n')
    outro = tmp_path / "meu.yml"
    outro.write_text(f'allow:\n  - "{SECRET}"\n')
    assert main(["scan", str(tmp_path), "--config", str(outro)]) == ExitCode.SUCCESS


def test_missing_explicit_config_is_a_usage_error(tmp_path):
    """Caso negativo: pedir um arquivo que não existe é erro; o implícito ausente não é."""
    assert (
        main(["scan", str(tmp_path), "--config", str(tmp_path / "nao-existe.yml")])
        == ExitCode.USAGE_ERROR
    )


def test_malformed_config_exits_two(tmp_path):
    (tmp_path / "ruim.yml").write_text('ignore: "nao fecha\n')
    assert main(["scan", str(tmp_path), "--config", str(tmp_path / "ruim.yml")]) == 2


def test_inline_marker_suppresses_only_its_own_line(tmp_path, capsys):
    """`FR-14`: a supressão é da LINHA, não do arquivo."""
    (tmp_path / "a.py").write_text(f'ok = "{SECRET}"  # gitsafety: allow\nruim = "{SECRET}"\n')
    assert main(["scan", str(tmp_path)]) == ExitCode.SECRETS_FOUND
    saida = capsys.readouterr().out
    assert "1 segredo encontrado" in saida


def test_help_now_advertises_config(capsys):
    with pytest.raises(SystemExit):
        main(["scan", "--help"])
    assert "--config" in capsys.readouterr().out


def test_scan_has_at_most_four_flags():
    """`docs/API.md § Superfície da CLI`: teto de 4 flags no `scan`.

    Conta as opções do subparser, descontando o `--help` que o argparse adiciona.
    """
    parser = build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    scan = sub.choices["scan"]
    flags = {o for a in scan._actions for o in a.option_strings if o.startswith("--")}
    flags.discard("--help")
    assert len(flags) <= 4, flags


# --- M5: `scan --history` -------------------------------------------------------


def _repo_com_segredo(tmp_path):
    import subprocess

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main", ".")
    git("config", "user.email", "t@exemplo.com")
    git("config", "user.name", "Teste")
    (tmp_path / "config.py").write_text("AWS = 'AKIAIOSFODNN7EXAMPLE'\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "adiciona credencial")
    return tmp_path


def test_history_flag_is_mutually_exclusive_with_staged(capsys, tmp_path):
    """Caso negativo: os dois alvos juntos são incoerentes, e o argparse já diz isso."""
    with pytest.raises(SystemExit) as exc:
        main(["scan", "--staged", "--history"])
    assert exc.value.code == 2


def test_history_output_contains_commit_author_and_date(capsys, tmp_path, monkeypatch):
    repo = _repo_com_segredo(tmp_path)
    monkeypatch.chdir(repo)

    codigo = main(["scan", "--history"])
    saida = capsys.readouterr().out

    assert codigo == 1
    assert "Teste" in saida
    assert "aws-access-key-id" in saida
    assert "20" in saida  # a data ISO


def test_history_masks_the_secret_by_default(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(_repo_com_segredo(tmp_path))
    main(["scan", "--history"])
    assert "AKIAIOSFODNN7EXAMPLE" not in capsys.readouterr().out


def test_history_show_secrets_reveals(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(_repo_com_segredo(tmp_path))
    main(["scan", "--history", "--show-secrets"])
    assert "AKIAIOSFODNN7EXAMPLE" in capsys.readouterr().out


def test_history_exit_code_is_0_on_clean_history(capsys, tmp_path, monkeypatch):
    import subprocess

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main", ".")
    git("config", "user.email", "t@exemplo.com")
    git("config", "user.name", "Teste")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "limpo")
    monkeypatch.chdir(tmp_path)

    assert main(["scan", "--history"]) == 0
    assert "Nenhum segredo encontrado" in capsys.readouterr().out


def test_history_shows_introduction_count_only_when_greater_than_one(
    capsys, tmp_path, monkeypatch
):
    """Colapso silencioso esconde informação — a lição mais cara do M4."""
    import subprocess

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main", ".")
    git("config", "user.email", "t@exemplo.com")
    git("config", "user.name", "Teste")
    for conteudo, msg in [
        ("AWS = 'AKIAIOSFODNN7EXAMPLE'\n", "c1"),
        ("limpo\n", "c2"),
        ("AWS = 'AKIAIOSFODNN7EXAMPLE'\n", "c3"),
    ]:
        (tmp_path / "a.py").write_text(conteudo, encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "--no-verify", "-m", msg)
    monkeypatch.chdir(tmp_path)

    main(["scan", "--history"])
    assert "2 introduções" in capsys.readouterr().out


def test_history_outside_a_repository_fails_clearly(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["scan", "--history"]) == 2
    assert "repositório" in capsys.readouterr().err.lower()


# --- A config é a do alvo, não a de onde você está (#9) --------------------------


def _repo(base, nome):
    import subprocess

    d = base / nome
    d.mkdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True, capture_output=True)
    return d


def test_config_of_the_caller_does_not_silence_the_target(tmp_path, monkeypatch):
    """O `allow:` de um repositório não pode calar o achado de outro.

    Falso negativo por ambiente é o pior modo de falha deste produto: quem varre o repo
    do vizinho recebe "nenhum segredo encontrado" porque o SEU repositório tinha um
    `allow:` sem nenhuma relação com o alvo.
    """
    de_onde_chamo = _repo(tmp_path, "a")
    (de_onde_chamo / ".gitsafety.yml").write_text(
        f'allow:\n  - "{SECRET}"\n', encoding="utf-8"
    )
    alvo = _repo(tmp_path, "b")
    (alvo / "config.py").write_text(f'API_KEY = "{SECRET}"\n', encoding="utf-8")

    monkeypatch.chdir(de_onde_chamo)

    assert main(["scan", str(alvo)]) == ExitCode.SECRETS_FOUND


def test_the_targets_own_config_is_the_one_that_applies(tmp_path, monkeypatch):
    """E o inverso: o `allow:` do alvo vale mesmo chamando de fora.

    Sem este par, a correção poderia ser "ignore toda config quando há caminho" — que
    conserta o falso negativo criando um falso positivo.
    """
    de_onde_chamo = _repo(tmp_path, "a")
    alvo = _repo(tmp_path, "b")
    (alvo / ".gitsafety.yml").write_text(f'allow:\n  - "{SECRET}"\n', encoding="utf-8")
    (alvo / "config.py").write_text(f'API_KEY = "{SECRET}"\n', encoding="utf-8")

    monkeypatch.chdir(de_onde_chamo)

    assert main(["scan", str(alvo)]) == ExitCode.SUCCESS


def test_explicit_config_flag_still_wins(tmp_path, monkeypatch):
    """`--config PATH` é pedido direto e continua vencendo a descoberta automática."""
    alvo = _repo(tmp_path, "b")
    (alvo / ".gitsafety.yml").write_text(f'allow:\n  - "{SECRET}"\n', encoding="utf-8")
    (alvo / "config.py").write_text(f'API_KEY = "{SECRET}"\n', encoding="utf-8")
    vazia = tmp_path / "vazia.yml"
    vazia.write_text("ignore: []\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert main(["scan", str(alvo), "--config", str(vazia)]) == ExitCode.SECRETS_FOUND

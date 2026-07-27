"""T1.1 — o pacote instalado expõe o comando `gitsafety`.

Estes testes existem para pegar o modo de falha que o layout `src/` previne (ADR D6):
o pacote resolver a partir do diretório de trabalho em vez do que foi instalado. Por
isso o subprocesso roda com `cwd` fora da raiz do repositório — dentro dela, um pacote
mal empacotado ainda importaria e o teste passaria por engano.
"""

from __future__ import annotations

import subprocess
import sys
import sysconfig
from pathlib import Path

import gitsafety


def _console_script() -> Path:
    """Caminho do script instalado pelo `[project.scripts]` deste interpretador.

    Resolver por `sysconfig` em vez de confiar no `PATH` é o que torna o teste
    honesto: ele verifica o script que ESTE ambiente instalou, e não um homônimo
    que por acaso esteja no PATH do desenvolvedor.
    """
    name = "gitsafety.exe" if sys.platform == "win32" else "gitsafety"
    return Path(sysconfig.get_path("scripts")) / name


def test_installed_command_reports_version_from_outside_the_repo(tmp_path):
    # Arrange — cwd fora da raiz do repositório: só o pacote instalado pode resolver.
    script = _console_script()
    assert script.exists(), f"console script não instalado em {script}"

    # Act
    result = subprocess.run(
        [str(script), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # Assert
    assert result.returncode == 0, result.stderr
    assert gitsafety.__version__ in result.stdout


def test_package_runs_as_a_module_from_outside_the_repo(tmp_path):
    """`python -m gitsafety` é o caminho de quem instalou sem o script no PATH."""
    # Arrange / Act
    result = subprocess.run(
        [sys.executable, "-m", "gitsafety", "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # Assert
    assert result.returncode == 0, result.stderr
    assert gitsafety.__version__ in result.stdout


def test_package_exposes_a_version_string():
    # Assert — versão precisa existir e não ser vazia; o empacotamento a lê daqui.
    assert gitsafety.__version__
    assert isinstance(gitsafety.__version__, str)

"""M6 — o pacote publicado precisa conferir com o que o README promete.

O DoD do `ROADMAP.md § M6` pede "README confere com o pacote publicado — nenhuma flag
documentada que não exista". Uma conferência manual apodrece no primeiro commit; esta é a
versão que falha sozinha quando alguém documenta uma flag que não implementou, ou implementa
uma que não documentou.

Publicar no PyPI é irreversível: uma versão não pode ser substituída, só retirada de
circulação. O que sai errado fica errado.
"""

from __future__ import annotations

import re
import subprocess
import sys
import sysconfig
from importlib.metadata import entry_points, metadata
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: Flags que o README cita e que pertencem ao **git**, não a nós.
_DO_GIT = {"--no-verify", "--amend"}
#: Universais do argparse, que não precisam estar no README.
_UNIVERSAIS = {"--help", "-h"}


def _flags_do_readme() -> set[str]:
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    return set(re.findall(r"--[a-z][a-z-]+", texto)) - _DO_GIT - _UNIVERSAIS


def _flags_da_cli() -> set[str]:
    binario = Path(sysconfig.get_path("scripts")) / "gitsafety"
    flags: set[str] = set()
    for args in (["--help"], ["scan", "--help"], ["install", "--help"]):
        saida = subprocess.run(
            [str(binario), *args], capture_output=True, text=True, check=False
        ).stdout
        flags |= set(re.findall(r"--[a-z][a-z-]+", saida))
    return flags - _UNIVERSAIS


def test_readme_documents_no_flag_that_does_not_exist():
    """DoD nº 2 do M6 — a direção que mente para quem lê antes de instalar."""
    inventadas = _flags_do_readme() - _flags_da_cli()
    assert not inventadas, f"o README documenta flags inexistentes: {sorted(inventadas)}"


def test_every_cli_flag_is_documented():
    """A direção oposta: uma flag que ninguém documenta é uma flag que ninguém usa."""
    nao_documentadas = _flags_da_cli() - _flags_do_readme()
    assert not nao_documentadas, f"flags sem documentação: {sorted(nao_documentadas)}"


# --- Metadados de publicação ----------------------------------------------------


@pytest.fixture(scope="module")
def projeto() -> dict:
    """Os metadados do pacote **instalado**, não a declaração no `pyproject.toml`.

    `importlib.metadata` lê o que o build de fato produziu, que é o que vai para o PyPI.
    Ler o fonte testaria a intenção; ler o artefato testa a entrega — e a diferença entre os
    dois é exatamente onde mora o erro que só aparece depois de publicar.

    (E `tomllib` é 3.11+, enquanto o nosso piso declarado é 3.10: um teste com ele quebraria
    justamente na versão mínima que o README promete.)
    """
    bruto = metadata("gitsafety")
    return {
        "version": bruto["Version"],
        "requires-python": bruto["Requires-Python"],
        "dependencies": bruto.get_all("Requires-Dist") or [],
        "urls": dict(
            linha.split(", ", 1) for linha in (bruto.get_all("Project-URL") or [])
        ),
        "scripts": {
            ep.name: ep.value for ep in entry_points(group="console_scripts") if ep.name == "gitsafety"
        },
    }


def test_package_declares_the_repository_url(projeto):
    """Sem `[project.urls]`, a página no PyPI não tem link para o código.

    Quem instala uma ferramenta de segurança quer poder ler o que ela faz antes de rodar.
    """
    assert projeto["urls"]["Repository"].startswith("https://")


def test_console_script_points_at_a_real_entry_point(projeto):
    """Um entry point errado só aparece depois de instalar — e o pacote já está publicado."""
    alvo = projeto["scripts"]["gitsafety"]
    modulo, funcao = alvo.split(":")
    importado = __import__(modulo, fromlist=[funcao])
    assert callable(getattr(importado, funcao))


def test_version_matches_the_changelog(projeto):
    """A versão do pacote e a do CHANGELOG são a mesma coisa dita duas vezes."""
    changelog = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    versoes = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    assert versoes[0] == projeto["version"]


def test_python_requires_matches_the_readme(projeto):
    """O README promete uma versão mínima; `pip` a impõe. Divergir gera erro de instalação."""
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    minima = re.search(r">=\s*(\d+\.\d+)", projeto["requires-python"]).group(1)
    assert f"Python {minima}" in readme


def test_declared_dependency_is_the_only_one(projeto):
    """`docs/PRD.md § NFR-1` autoriza UMA dependência de runtime. Ela é o pyyaml.

    Filtra os `extra ==` porque o que o usuário instala não inclui o ambiente de dev.
    """
    # O metadado construído normaliza o especificador (`pyyaml<7,>=6.0.1`), então a
    # comparação é sobre o NOME do pacote — que é a afirmação do NFR-1.
    runtime = [d.split()[0] for d in projeto["dependencies"] if "extra ==" not in d]
    assert runtime == ["pyyaml<7,>=6.0.1"], runtime


def test_the_package_imports_without_its_dev_extras():
    """O que o usuário instala é o pacote, não o ambiente de desenvolvimento."""
    saida = subprocess.run(
        [sys.executable, "-c", "import gitsafety.cli; print('ok')"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert saida.stdout.strip() == "ok", saida.stderr


def test_the_version_the_cli_prints_is_the_version_of_the_package(projeto):
    """`--version` precisa dizer a versão que o usuário instalou.

    Achado na instalação em ambiente limpo: o pacote era 0.6.0 e o comando imprimia 0.4.0.
    A versão estava escrita em DOIS lugares — `pyproject.toml` e `__init__.py` — e divergiu
    na primeira oportunidade, sem nada para acusar.

    Num produto de segurança isso é pior que cosmético: a primeira coisa que se pede a quem
    reporta um problema é a versão, e a resposta estaria errada. E publicar no PyPI é
    irreversível — a versão errada ficaria gravada naquele artefato para sempre.
    """
    binario = Path(sysconfig.get_path("scripts")) / "gitsafety"
    impressa = subprocess.run(
        [str(binario), "--version"], capture_output=True, text=True, check=False
    ).stdout.strip()

    assert impressa == f"gitsafety {projeto['version']}"

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

#: Flags que o README cita e que pertencem a **outras ferramentas**, não a nós.
#:
#: O README precisa mostrar comandos vizinhos — `git commit --no-verify` para a saída de
#: emergência, `pip install --user pipx` para quem não tem o pipx. Sem esta lista, o teste
#: acusaria o README de documentar flag inexistente por citar o ecossistema em volta.
_DE_OUTRAS_FERRAMENTAS = {"--no-verify", "--amend", "--user"}
#: Universais do argparse, que não precisam estar no README.
_UNIVERSAIS = {"--help", "-h"}


def _flags_do_readme() -> set[str]:
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    return set(re.findall(r"--[a-z][a-z-]+", texto)) - _DE_OUTRAS_FERRAMENTAS - _UNIVERSAIS


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
        "urls": dict(linha.split(", ", 1) for linha in (bruto.get_all("Project-URL") or [])),
        "scripts": {
            ep.name: ep.value
            for ep in entry_points(group="console_scripts")
            if ep.name == "gitsafety"
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
    """`docs/API.md § Dependências` autoriza UMA dependência de runtime: o pyyaml.

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


#: Marcadores que o README usou para dizer "isto ainda não existe".
_MARCADORES_DE_PENDENCIA = ("em construção", "⏳", "em breve", "planejado", "TODO")


def test_no_shipped_flag_is_marked_as_pending():
    """Uma flag que existe não pode estar anunciada como pendente.

    Os dois testes acima comparam **presença**: flag documentada que não existe, e flag que
    existe sem documentação. Nenhum dos dois olha o que o texto **afirma** ao lado da flag —
    e foi exatamente por aí que passou uma linha dizendo `--history ⏳ em construção` por
    duas versões depois de a flag ter sido lançada.

    Mentir dizendo que algo não existe é mais barato que o contrário, mas custa igual: quem
    lê o README decide não usar um recurso que está pronto.
    """
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")

    mentiras = [
        (flag, linha.strip())
        for linha in readme.splitlines()
        if any(marcador in linha for marcador in _MARCADORES_DE_PENDENCIA)
        for flag in _flags_da_cli()
        if flag in linha
    ]

    assert not mentiras, f"flags que existem, anunciadas como pendentes: {mentiras}"


def test_the_readme_has_no_leftover_pending_markers():
    """Nenhum marcador de pendência sobrando — nem a legenda que explicava um deles.

    Quando o último item pendente é entregue, a legenda vira ruído que sugere que ainda há
    algo por vir.
    """
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")

    sobrando = [
        linha.strip()
        for linha in readme.splitlines()
        if any(marcador in linha for marcador in _MARCADORES_DE_PENDENCIA)
    ]

    assert not sobrando, f"marcadores de pendência no README: {sobrando}"


# --- A referência citada pelo código precisa existir -----------------------------


def _secoes_da_referencia() -> set[str]:
    texto = (RAIZ / "docs" / "API.md").read_text(encoding="utf-8")
    return {m.group(1).strip() for m in re.finditer(r"^#{2,3} (.+)$", texto, re.M)}


def _citacoes_no_codigo() -> set[tuple[str, str]]:
    """Toda citação de seção da referência em código, teste ou README, com sua origem."""
    alvos = [
        *(RAIZ / "src").rglob("*.py"),
        *(RAIZ / "tests").rglob("*.py"),
        RAIZ / "README.md",
    ]
    achadas = set()
    for arquivo in alvos:
        for m in re.finditer(
            r"docs/API\.md`? § ([^`\n:,.)]+)", arquivo.read_text(encoding="utf-8")
        ):
            achadas.add((str(arquivo.relative_to(RAIZ)), m.group(1).strip()))
    return achadas


def test_every_reference_citation_resolves_to_a_real_section():
    """Citação que não resolve é a mesma falha que o `⏳ em construção` de flag entregue.

    O código aponta para seções da referência em mais de vinte arquivos. Renomear uma
    delas quebraria todas essas citações em silêncio — o leitor procura a seção, não acha,
    e passa a desconfiar das outras também. Este teste faz o rename doer na hora.
    """
    secoes = _secoes_da_referencia()

    orfas = sorted(
        f"{origem} -> § {alvo}" for origem, alvo in _citacoes_no_codigo() if alvo not in secoes
    )

    assert not orfas, f"citações que não resolvem em docs/API.md: {orfas}"


def test_the_reference_declares_the_version_that_is_installed(projeto):
    """A referência declara a versão que documenta — e ela precisa ser a atual.

    Uma referência que diz "versão 0.7.3" sobre um pacote 0.9.0 documenta o passado sem
    avisar. O leitor não tem como saber quais contratos mudaram desde então.
    """
    texto = (RAIZ / "docs" / "API.md").read_text(encoding="utf-8")

    declarada = re.search(r"referência da versão \*\*([\d.]+)\*\*", texto)

    assert declarada, "docs/API.md não declara a versão que documenta"
    assert declarada.group(1) == projeto["version"]

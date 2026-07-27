"""gitsafety — não deixa você commitar uma chave de API."""

from importlib.metadata import PackageNotFoundError, version

try:
    #: A versão vem do PACOTE INSTALADO, não de uma constante escrita à mão.
    #:
    #: Ela estava duplicada — aqui e no `pyproject.toml` — e divergiu na primeira
    #: oportunidade: o pacote virou 0.6.0 e o `--version` seguiu dizendo 0.4.0, sem nada
    #: para acusar. Num produto de segurança isso não é cosmético: a primeira coisa que se
    #: pede a quem reporta um problema é a versão.
    #:
    #: `importlib.metadata` é stdlib desde o 3.8 (`rules/parsimony-ladder.md` rung 2), e a
    #: duplicação deixa de existir em vez de precisar ser sincronizada.
    __version__ = version("gitsafety")
except PackageNotFoundError:  # pragma: no cover
    # Rodando do fonte sem instalar (`python -m gitsafety` num clone). Não é erro: o
    # comando funciona, só não sabe se dizer.
    __version__ = "0.0.0+desconhecida"

__all__ = ["__version__"]

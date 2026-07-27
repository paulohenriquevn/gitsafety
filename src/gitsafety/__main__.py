"""Ponto de entrada do console e de `python -m gitsafety`.

Mantido deliberadamente fino: a única responsabilidade aqui é traduzir o código de
retorno de `cli.main` em código de saída de processo. Toda a lógica vive em `cli.py`
(`rules/architecture.md § 1` — a interface roteia, não decide).
"""
from __future__ import annotations

import sys

from gitsafety import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if "--version" in args:
        print(f"gitsafety {__version__}")
        return 0
    print(f"gitsafety {__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

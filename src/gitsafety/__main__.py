"""Ponto de entrada do console e de `python -m gitsafety`.

Fino de propósito: a única responsabilidade é aplicar o código que `cli.main`
devolve. Toda decisão vive em `cli.py` — a interface roteia, não decide
(`rules/architecture.md § 1`).
"""
from __future__ import annotations

import sys

from gitsafety.cli import main


if __name__ == "__main__":
    sys.exit(main())

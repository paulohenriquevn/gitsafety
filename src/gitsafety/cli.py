"""Interface de linha de comando (ADRs D4 e D5).

Única camada que conhece `argparse`, `print` e códigos de saída
(`rules/architecture.md § 1`). A regra de negócio inteira vive em `scanner`; aqui só
se traduz resultado em texto e em código de processo.

`argparse` da stdlib, não `click` (ADR D5): `docs/PRD.md § NFR-1` autoriza uma
dependência externa e ela está reservada ao parser de YAML do M3.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from gitsafety import __version__
from gitsafety.config import load_config
from gitsafety.errors import ExitCode, GitsafetyError
from gitsafety.history import HistoryFinding, scan_history
from gitsafety.hook import install_hook
from gitsafety.scanner import ScanResult, scan_path
from gitsafety.staged import scan_staged


def build_parser() -> argparse.ArgumentParser:
    """Monta o parser com **apenas** as flags que existem no M0.

    `--staged` (M1) e `--history` (M5) estão no README como contrato futuro, mas
    anunciá-las no `--help` antes de existirem seria mentir para quem lê a ajuda.
    """
    parser = argparse.ArgumentParser(
        prog="gitsafety",
        description="Não deixa você commitar uma chave de API.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="mostra a versão e sai",
    )

    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="verifica arquivos em busca de segredos")
    # `--staged` e um caminho posicional são incoerentes juntos: o índice é sempre o do
    # repositório atual. O grupo mutuamente exclusivo produz mensagem melhor que uma
    # validação manual depois do parse.
    alvo = scan.add_mutually_exclusive_group()
    alvo.add_argument(
        "path",
        nargs="?",
        default=".",
        help="arquivo ou diretório a verificar (padrão: diretório atual)",
    )
    alvo.add_argument(
        "--staged",
        action="store_true",
        help="verifica o que está no index do git, e não o disco",
    )
    alvo.add_argument(
        "--history",
        action="store_true",
        help="procura segredos que já foram commitados no histórico",
    )
    scan.add_argument(
        "--show-secrets",
        action="store_true",
        help="mostra o segredo completo em vez de mascarado",
    )
    scan.add_argument(
        "--config",
        metavar="PATH",
        help="arquivo de configuração (padrão: .gitsafety.yml na raiz do repositório)",
    )

    sub.add_parser("install", help="instala o hook de pre-commit neste repositório")

    return parser


def render(result: ScanResult, *, show_secrets: bool) -> str:
    """Formata o resultado para leitura humana.

    O segredo sai **mascarado por padrão** (`docs/PRD.md § NFR-4`) — o valor íntegro
    só aparece sob pedido explícito. E a saída sempre instrui a revogar a chave
    (`FR-19`): apagar a linha não desfaz a exposição, e quem não souber disso vai
    "resolver" o incidente deixando a credencial ativa.
    """
    linhas: list[str] = []

    for f in result.findings:
        segredo = f.secret if show_secrets else f.masked_secret
        linhas.append(f"  {f.path}:{f.line}   {f.rule_id}   {segredo}")

    if result.findings:
        linhas.append("")
        total = len(result.findings)
        plural = "s" if total > 1 else ""
        linhas.append(f"  {total} segredo{plural} encontrado{plural}.")
        linhas.append("  Revogue a chave no provedor antes de qualquer outra coisa.")
    else:
        linhas.append("  Nenhum segredo encontrado.")

    if result.skipped:
        total = len(result.skipped)
        plural = "s" if total > 1 else ""
        linhas.append("")
        linhas.append(f"  {total} arquivo{plural} pulado{plural} (binário ou acima de 1 MB).")

    return "\n".join(linhas)


def render_history(achados: Sequence[HistoryFinding], *, show_secrets: bool) -> str:
    """Formata achados do histórico: onde o segredo entrou, e por quem.

    O commit é o da **introdução** — "desde quando esta chave está exposta?" é a pergunta
    que decide a urgência, e é a que o número responde.

    A contagem de introduções só aparece quando é maior que 1, e aí significa algo
    específico: a credencial voltou depois de ter saído. Mostrá-la sempre seria ruído;
    escondê-la quando existe seria colapso silencioso, que é a lição mais cara do M4.
    """
    linhas: list[str] = []

    for h in achados:
        segredo = h.finding.secret if show_secrets else h.finding.masked_secret
        repeticao = f"   ({h.introductions} introduções)" if h.introductions > 1 else ""
        linhas.append(f"  {h.finding.path}:{h.finding.line}   {h.finding.rule_id}   {segredo}")
        linhas.append(
            f"      {h.commit.short_sha}  {h.commit.author}  {h.commit.date}{repeticao}"
        )

    if achados:
        total = len(achados)
        plural = "s" if total > 1 else ""
        linhas.append("")
        linhas.append(f"  {total} segredo{plural} encontrado{plural} no histórico.")
        linhas.append("  Revogue a chave no provedor antes de qualquer outra coisa.")
        # Apagar o arquivo não desfaz nada: o objeto continua no histórico de todo mundo
        # que já clonou. Quem não souber disso vai "resolver" deixando a chave ativa.
        linhas.append("  Remover o arquivo agora NÃO apaga o segredo do histórico.")
    else:
        linhas.append("  Nenhum segredo encontrado.")

    return "\n".join(linhas)


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada. Devolve o código de saída, não o aplica.

    Captura **apenas** `GitsafetyError`. O que não for erro previsto é defeito nosso
    e deve subir com traceback: um `except Exception` aqui transformaria bug em
    mensagem amigável e o defeito nunca seria corrigido
    (`rules/error-handling.md § 5`).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"gitsafety {__version__}")
        return ExitCode.SUCCESS

    if args.command not in ("scan", "install"):
        parser.print_help()
        return ExitCode.SUCCESS

    # Um único `try` para os dois subcomandos: o código de saída vem sempre da própria
    # exceção (ADR D4 do M0), então não há cadeia de `if isinstance` aqui — e nunca um
    # `except Exception`, que transformaria defeito nosso em mensagem amigável.
    try:
        if args.command == "install":
            destino = install_hook(Path.cwd())
            print(f"  hook instalado em {destino}")
            print("  A partir de agora o commit é verificado.")
            print("  Emergência: git commit --no-verify")
            return ExitCode.SUCCESS

        # A config é carregada ANTES da varredura: um erro nela precisa aparecer
        # imediatamente, e não depois de percorrer mil arquivos.
        cfg = load_config(Path(args.config) if args.config else None)
        if args.history:
            achados = scan_history(Path.cwd(), config=cfg)
            print(render_history(achados, show_secrets=args.show_secrets))
            return ExitCode.SECRETS_FOUND if achados else ExitCode.SUCCESS

        result = (
            scan_staged(Path.cwd(), config=cfg)
            if args.staged
            else scan_path(args.path, config=cfg)
        )
    except GitsafetyError as exc:
        print(f"erro: {exc.message}", file=sys.stderr)
        return exc.exit_code

    print(render(result, show_secrets=args.show_secrets))
    return ExitCode.SECRETS_FOUND if result.has_findings else ExitCode.SUCCESS

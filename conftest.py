"""Raiz de configuração do pytest.

Existe para que a raiz do repositório entre em `sys.path` e `benchmarks/` seja
importável pelos testes. O pacote de produto vive em `src/` e é resolvido pela
instalação editável (ADR D6) — `benchmarks/` não é distribuído, então precisa deste
gancho para ser alcançável a partir dos testes.
"""

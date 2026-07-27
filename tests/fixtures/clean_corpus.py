"""Corpus limpo de referência para a métrica de falso positivo (ADR D7).

Gerado por código, não commitado como árvore: evita trazer licença de terceiro para
dentro da métrica e mantém o conteúdo legível no diff.

O corpus contém justamente o que **quase** parece segredo — hash, UUID, base64, chave
pública, identificadores longos. Um corpus de código trivial não provaria nada: ele
passaria mesmo com um catálogo cheio de padrões largos demais.

O `ROADMAP.md § M2` pede "repositório limpo de referência produz zero findings"; sem
corpus nomeado a métrica não é reprodutível, e métrica não reprodutível não detecta
regressão.
"""

from __future__ import annotations

from pathlib import Path

#: Formas que se parecem com segredo e **não** são. Cada uma existe porque um padrão
#: largo demais a acusaria.
NEAR_MISS_SHAPES = {
    "hashes.py": '''"""Hashes e digests — alfanuméricos longos que não são credenciais."""

SHA256_VAZIO = (
    "e3b0c44298fc1c149afbf4c8996fb924"
    "27ae41e4649b934ca495991b7852b855"
)
SHA1_COMMIT = "356032dabc1234567890abcdef1234567890abcd"
MD5_ARQUIVO = "d41d8cd98f00b204e9800998ecf8427e"
CRC32 = "a1b2c3d4"
''',
    "identificadores.py": '''"""UUIDs e identificadores opacos."""

REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000"
TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN_ID = "00f067aa0ba902b7"
CORRELATION = "01HQ8Z9K2M3N4P5Q6R7S8T9V0W"
''',
    "encoding.py": '''"""Base64 de dados legítimos — o formato mais confundido com credencial."""

import base64

PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
JSON_CODIFICADO = base64.b64encode(b'{"ok": true, "items": [1, 2, 3]}').decode()
''',
    "chaves_publicas.py": '''"""Chaves PÚBLICAS — parecem chave privada mas podem ser distribuídas."""

SSH_PUBLICA = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDhA2Nq6Zs8bK3lPl0hV6QF5"
    " usuario@maquina"
)
PEM_PUBLICA = "-----BEGIN PUBLIC KEY-----"
CERTIFICADO = "-----BEGIN CERTIFICATE-----"
''',
    "config_exemplo.py": '''"""Configuração de desenvolvimento — sem credencial real."""

DATABASE_URL = "postgresql://localhost:5432/desenvolvimento"
REDIS_URL = "redis://localhost:6379/0"
MONGO_URL = "mongodb://localhost:27017/app"
API_BASE = "https://api.exemplo.com/v1"
TIMEOUT_SEGUNDOS = 30
''',
    "app.py": '''"""Código de aplicação comum."""

from dataclasses import dataclass


@dataclass
class Pedido:
    id: int
    total_centavos: int

    def com_desconto(self, percentual: float) -> int:
        return round(self.total_centavos * (1 - percentual))


def processar(pedidos: list[Pedido]) -> int:
    return sum(p.total_centavos for p in pedidos)
''',
    "notas.md": """# Documentação

Para configurar, exporte as variáveis de ambiente. Nunca coloque credenciais no
repositório — use um gerenciador de segredos.

Formato do identificador: prefixo de 4 letras seguido de 16 caracteres.
""",
    "dados.json": """{
  "versao": "1.2.3",
  "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "itens": [{"id": 1, "nome": "alfa"}, {"id": 2, "nome": "beta"}]
}
""",
}


def build_clean_corpus(root: Path) -> int:
    """Escreve o corpus em `root` e devolve o número de arquivos.

    Espalha em subdiretórios para exercer a travessia recursiva, e não só a leitura de
    um diretório plano.
    """
    root = Path(root)
    for indice, (nome, conteudo) in enumerate(NEAR_MISS_SHAPES.items()):
        sub = root / f"pacote_{indice % 3}"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / nome).write_text(conteudo, encoding="utf-8")
    return len(NEAR_MISS_SHAPES)

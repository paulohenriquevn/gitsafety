"""Catálogo de padrões de credencial (ADRs D4 e D5).

Módulo de **dados**. Toda regra é registrada na tupla literal `BUILTIN_RULES` no fim do
arquivo — precedente `gitleaks/cmd/generate/config/main.go:30`. Uma regra que não está na
tupla não existe, e a tupla é onde o revisor vê o catálogo inteiro de uma vez.

Cada regra carrega seus próprios exemplos, nos **dois lados**:

- `true_positives` — em contexto de código, não valor nu (ADR D5). Um padrão que casa o
  valor solto mas falha entre aspas passaria no teste e falharia no uso real.
- `false_positives` — o quase-acerto que a regra **não** pode casar. É a metade que a
  maioria das suítes esquece, e é a que protege contra o Risco nº 1 do M2.

`tests/unit/test_catalog.py` percorre a tupla e falha se qualquer regra descumprir
qualquer um dos lados — adaptação de `gitleaks/.../validate.go:16-39`, que mata o
processo na construção.

Os valores usados como exemplo são **chaves de documentação oficial ou sintéticas**;
nenhuma é credencial real.
"""

from __future__ import annotations

from gitsafety.patterns import Rule, keyword_assignment, literal_marker, unique_token


def _r(
    rule_id: str,
    description: str,
    secret_regex: str,
    tps: tuple[str, ...],
    fps: tuple[str, ...],
    *,
    case_insensitive: bool = False,
    self_anchored: bool = False,
) -> Rule:
    """Atalho de construção — mantém o catálogo legível como dado.

    `self_anchored=True` usa `literal_marker`, para padrões cujo próprio texto é a
    âncora (blocos PEM, cabeçalhos de arquivo de chave). São a exceção declarada, não
    a regra.
    """
    pattern = (
        literal_marker(secret_regex)
        if self_anchored
        else unique_token(secret_regex, case_insensitive=case_insensitive)
    )
    return Rule(
        id=rule_id,
        description=description,
        pattern=pattern,
        true_positives=tps,
        false_positives=fps,
    )


# --- Cloud ---------------------------------------------------------------------

CLOUD_RULES: tuple[Rule, ...] = (
    _r(
        "aws-access-key-id",
        "Identificador de chave de acesso da AWS",
        # `A` fatorado para fora da alternância: alternância no topo derrota a otimização
        # de prefixo literal do `re`. Medido: 0,0473 s -> 0,0299 s sobre 1.000 arquivos.
        r"A(?:KIA|SIA|BIA|CCA)[0-9A-Z]{16}",
        ('AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"', "export AWS_KEY=ASIAY34FZKBOKMUTVV7A"),
        ("AKIA", "AKIAIOSFODNN7EXAMPL", "akiaiosfodnn7example"),
    ),
    _r(
        "aws-session-token",
        "Token de sessão temporária da AWS",
        r"FwoGZXIvYXdzE[A-Za-z0-9/+=]{50,300}",
        ('token = "FwoGZXIvYXdzE' + "A" * 60 + '"',),
        ("FwoGZXIvYXdzE", "FwoGZXIvYXdz"),
    ),
    _r(
        "gcp-api-key",
        "Chave de API do Google Cloud",
        r"AIza[0-9A-Za-z_-]{35}",
        ('GOOGLE_API_KEY = "AIza' + "S" * 35 + '"', "key: AIza" + "b" * 35),
        ("AIza", "AIza" + "S" * 10),
    ),
    _r(
        "gcp-service-account",
        "Identificador de conta de serviço do Google Cloud",
        r"[a-z][a-z0-9-]{5,29}@[a-z][a-z0-9-]{5,29}\.iam\.gserviceaccount\.com",
        ('sa = "deploy-bot@meu-projeto.iam.gserviceaccount.com"',),
        ("alguem@exemplo.com", "sa@gserviceaccount.com"),
    ),
    _r(
        "azure-storage-key",
        "Chave de conta de armazenamento do Azure",
        r"DefaultEndpointsProtocol=https;AccountName=[a-z0-9]{3,24};AccountKey=[A-Za-z0-9+/=]{60,100}",
        (
            'CONN = "DefaultEndpointsProtocol=https;AccountName=minhaconta;AccountKey='
            + "A" * 64
            + '=="',
        ),
        ("DefaultEndpointsProtocol=https;AccountName=minhaconta",),
    ),
    _r(
        "digitalocean-token",
        "Token de acesso pessoal da DigitalOcean",
        r"dop_v1_[a-f0-9]{64}",
        ('DO_TOKEN = "dop_v1_' + "a" * 64 + '"',),
        ("dop_v1_", "dop_v1_" + "a" * 10),
    ),
    _r(
        "heroku-api-key",
        "Chave de API do Heroku",
        r"[Hh]eroku[A-Za-z0-9_-]{0,10}[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        ('heroku_key = "heroku0123abcd-89ab-cdef-0123-456789abcdef"',),
        ("0123abcd-89ab-cdef-0123-456789abcdef",),
    ),
    _r(
        "cloudflare-api-token",
        "Token de API da Cloudflare",
        r"v1\.0-[A-Za-z0-9_-]{20,60}-[A-Za-z0-9_-]{100,200}",
        ('CF = "v1.0-' + "a" * 30 + "-" + "b" * 120 + '"',),
        ("v1.0-abc",),
    ),
)


# --- Controle de versão e pacotes ----------------------------------------------

VCS_RULES: tuple[Rule, ...] = (
    _r(
        "github-personal-access-token",
        "Token de acesso pessoal do GitHub (clássico)",
        r"ghp_[A-Za-z0-9]{36}",
        ('GH_TOKEN = "ghp_' + "a" * 36 + '"', "export GITHUB_TOKEN=ghp_" + "B" * 36),
        ("ghp_", "ghp_" + "a" * 10),
    ),
    _r(
        "github-fine-grained-token",
        "Token de acesso do GitHub de escopo fino",
        r"github_pat_[A-Za-z0-9_]{60,90}",
        ('token = "github_pat_' + "a" * 70 + '"',),
        ("github_pat_", "github_pat_abc"),
    ),
    _r(
        "github-oauth-token",
        "Token OAuth do GitHub",
        r"gho_[A-Za-z0-9]{36}",
        ('oauth = "gho_' + "c" * 36 + '"',),
        ("gho_", "gho_abc"),
    ),
    _r(
        "github-app-token",
        "Token de GitHub App",
        # Classe de caracteres em vez de alternância, pelo mesmo motivo da regra da AWS.
        r"gh[us]_[A-Za-z0-9]{36}",
        ('app = "ghs_' + "d" * 36 + '"', 'user = "ghu_' + "e" * 36 + '"'),
        ("ghs_", "ghu_abc"),
    ),
    _r(
        "github-refresh-token",
        "Token de renovação do GitHub",
        r"ghr_[A-Za-z0-9]{36,255}",
        ('refresh = "ghr_' + "f" * 40 + '"',),
        ("ghr_", "ghr_abc"),
    ),
    _r(
        "gitlab-personal-access-token",
        "Token de acesso pessoal do GitLab",
        r"glpat-[A-Za-z0-9_-]{20}",
        ('GITLAB_TOKEN = "glpat-' + "a" * 20 + '"',),
        ("glpat-", "glpat-abc"),
    ),
    _r(
        "gitlab-pipeline-trigger-token",
        "Token de disparo de pipeline do GitLab",
        r"glptt-[0-9a-f]{40}",
        ('trigger = "glptt-' + "a" * 40 + '"',),
        ("glptt-", "glptt-abc"),
    ),
    _r(
        "npm-access-token",
        "Token de acesso do npm",
        r"npm_[A-Za-z0-9]{36}",
        (
            'NPM_TOKEN = "npm_' + "a" * 36 + '"',
            "//registry.npmjs.org/:_authToken=npm_" + "Z" * 36,
        ),
        ("npm_", "npm_abc"),
    ),
    _r(
        "pypi-upload-token",
        "Token de upload do PyPI",
        r"pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,1000}",
        ('TWINE_PASSWORD = "pypi-AgEIcHlwaS5vcmc' + "a" * 60 + '"',),
        ("pypi-AgEIcHlwaS5vcmc",),
    ),
    _r(
        "rubygems-api-key",
        "Chave de API do RubyGems",
        r"rubygems_[a-f0-9]{48}",
        ('key = "rubygems_' + "a" * 48 + '"',),
        ("rubygems_", "rubygems_abc"),
    ),
    _r(
        "crates-io-token",
        "Token do crates.io",
        r"cio[A-Za-z0-9]{32}",
        ('CARGO_TOKEN = "cio' + "a" * 32 + '"',),
        ("cio", "cioabc"),
    ),
)


# --- IA e dados ----------------------------------------------------------------

AI_RULES: tuple[Rule, ...] = (
    _r(
        "openai-api-key",
        "Chave de API da OpenAI",
        r"sk-(?:proj-)?[A-Za-z0-9_-]{20,120}",
        ('OPENAI_API_KEY = "sk-' + "a" * 48 + '"', 'k = "sk-proj-' + "b" * 40 + '"'),
        ("sk-", "sk-abc"),
    ),
    _r(
        "anthropic-api-key",
        "Chave de API da Anthropic",
        r"sk-ant-(?:api|admin)[0-9]{2}-[A-Za-z0-9_-]{80,120}",
        ('ANTHROPIC_API_KEY = "sk-ant-api03-' + "a" * 95 + '"',),
        ("sk-ant-", "sk-ant-api03-abc"),
    ),
    _r(
        "huggingface-token",
        "Token de acesso do Hugging Face",
        r"hf_[A-Za-z0-9]{34,40}",
        ('HF_TOKEN = "hf_' + "a" * 37 + '"',),
        ("hf_", "hf_abc"),
    ),
    _r(
        "cohere-api-key",
        "Chave de API da Cohere",
        r"[Cc]ohere[A-Za-z0-9_-]{0,10}[A-Za-z0-9]{40}",
        ('cohere_key = "cohere' + "a" * 40 + '"',),
        ("cohere", "cohereabc"),
    ),
    _r(
        "replicate-api-token",
        "Token de API da Replicate",
        r"r8_[A-Za-z0-9]{37,40}",
        ('REPLICATE_API_TOKEN = "r8_' + "a" * 38 + '"',),
        ("r8_", "r8_abc"),
    ),
    _r(
        "wandb-api-key",
        "Chave de API do Weights & Biases",
        r"[Ww]andb[A-Za-z0-9_-]{0,10}[a-f0-9]{40}",
        ('wandb_key = "wandb' + "a" * 40 + '"',),
        ("wandb", "wandbabc"),
    ),
)


# --- Pagamentos e SaaS ---------------------------------------------------------

SAAS_RULES: tuple[Rule, ...] = (
    _r(
        "stripe-secret-key",
        "Chave secreta da Stripe",
        r"sk_live_[A-Za-z0-9]{24,247}",
        ('STRIPE_SECRET = "sk_live_' + "a" * 30 + '"',),
        # `sk_test_` é de ambiente de teste e o README já sugere o `allow:` para ele.
        ("sk_test_" + "a" * 30, "sk_live_", "sk_live_abc"),
    ),
    _r(
        "stripe-restricted-key",
        "Chave restrita da Stripe",
        r"rk_live_[A-Za-z0-9]{24,247}",
        ('rk = "rk_live_' + "b" * 30 + '"',),
        ("rk_test_" + "b" * 30, "rk_live_"),
    ),
    _r(
        "twilio-api-key",
        "Chave de API da Twilio",
        r"SK[0-9a-fA-F]{32}",
        ('TWILIO_API_KEY = "SK' + "a" * 32 + '"',),
        ("SK", "SKabc"),
    ),
    _r(
        "twilio-account-sid",
        "SID de conta da Twilio",
        r"AC[0-9a-fA-F]{32}",
        ('TWILIO_ACCOUNT_SID = "AC' + "b" * 32 + '"',),
        ("AC", "ACabc"),
    ),
    _r(
        "sendgrid-api-key",
        "Chave de API do SendGrid",
        r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}",
        ('SENDGRID_API_KEY = "SG.' + "a" * 22 + "." + "b" * 43 + '"',),
        ("SG.", "SG.abc.def"),
    ),
    _r(
        "slack-bot-token",
        "Token de bot do Slack",
        r"xoxb-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24,32}",
        ('SLACK_BOT_TOKEN = "xoxb-1234567890-1234567890-' + "a" * 24 + '"',),
        ("xoxb-", "xoxb-123"),
    ),
    _r(
        "slack-user-token",
        "Token de usuário do Slack",
        r"xoxp-[0-9]{10,13}-[0-9]{10,13}-[0-9]{10,13}-[a-f0-9]{32}",
        ('t = "xoxp-1234567890-1234567890-1234567890-' + "a" * 32 + '"',),
        ("xoxp-", "xoxp-123"),
    ),
    _r(
        "slack-webhook-url",
        "URL de webhook do Slack",
        r"https://hooks\.slack\.com/services/T[A-Za-z0-9_]{8,12}/B[A-Za-z0-9_]{8,12}/[A-Za-z0-9_]{24}",
        ('WEBHOOK = "https://hooks.slack.com/services/T01234567/B01234567/' + "a" * 24 + '"',),
        ("https://hooks.slack.com/services/",),
    ),
    _r(
        "mailgun-api-key",
        "Chave de API do Mailgun",
        r"key-[0-9a-f]{32}",
        ('MAILGUN_KEY = "key-' + "a" * 32 + '"',),
        ("key-", "key-abc"),
    ),
    _r(
        "datadog-api-key",
        "Chave de API do Datadog",
        r"[Dd]atadog[A-Za-z0-9_-]{0,10}[a-f0-9]{32}",
        ('datadog_key = "datadog' + "a" * 32 + '"',),
        ("datadog", "datadogabc"),
    ),
    _r(
        "sentry-auth-token",
        "Token de autenticação do Sentry",
        r"sntrys_[A-Za-z0-9+/=]{50,200}",
        ('SENTRY_AUTH_TOKEN = "sntrys_' + "a" * 60 + '"',),
        ("sntrys_", "sntrys_abc"),
    ),
    _r(
        "shopify-access-token",
        "Token de acesso da Shopify",
        r"shp(?:at|ca|pa|ss)_[a-fA-F0-9]{32}",
        ('SHOPIFY = "shpat_' + "a" * 32 + '"',),
        ("shpat_", "shpat_abc"),
    ),
    _r(
        "square-access-token",
        "Token de acesso da Square",
        r"sq0atp-[A-Za-z0-9_-]{22}",
        ('SQUARE = "sq0atp-' + "a" * 22 + '"',),
        ("sq0atp-", "sq0atp-abc"),
    ),
    _r(
        "atlassian-api-token",
        "Token de API da Atlassian",
        r"ATATT3[A-Za-z0-9_=-]{180,250}",
        ('JIRA_TOKEN = "ATATT3' + "a" * 200 + '"',),
        ("ATATT3", "ATATT3abc"),
    ),
    _r(
        "linear-api-key",
        "Chave de API do Linear",
        r"lin_api_[A-Za-z0-9]{40}",
        ('LINEAR_API_KEY = "lin_api_' + "a" * 40 + '"',),
        ("lin_api_", "lin_api_abc"),
    ),
    _r(
        "vercel-token",
        "Token de acesso da Vercel",
        r"[Vv]ercel[A-Za-z0-9_-]{0,10}[A-Za-z0-9]{24}",
        ('vercel_token = "vercel' + "a" * 24 + '"',),
        ("vercel", "vercelabc"),
    ),
    _r(
        "netlify-token",
        "Token de acesso da Netlify",
        r"[Nn]etlify[A-Za-z0-9_-]{0,10}[A-Za-z0-9_-]{40,45}",
        ('netlify_token = "netlify' + "a" * 43 + '"',),
        ("netlify", "netlifyabc"),
    ),
    _r(
        "algolia-admin-key",
        "Chave de administração da Algolia",
        r"[Aa]lgolia[A-Za-z0-9_-]{0,12}[a-f0-9]{32}",
        ('algolia_admin_key = "algolia' + "a" * 32 + '"',),
        ("algolia", "algoliaabc"),
    ),
    _r(
        "jwt-token",
        "JSON Web Token",
        r"eyJ[A-Za-z0-9_-]{10,500}\.eyJ[A-Za-z0-9_-]{10,500}\.[A-Za-z0-9_-]{10,500}",
        ('AUTH = "eyJ' + "a" * 20 + ".eyJ" + "b" * 20 + "." + "c" * 30 + '"',),
        ("eyJhbGciOiJIUzI1NiJ9", "eyJ.eyJ."),
    ),
)


# --- Chaves privadas -----------------------------------------------------------

KEY_RULES: tuple[Rule, ...] = (
    _r(
        "private-key-pem",
        "Bloco de chave privada em formato PEM",
        r"-----BEGIN[ A-Z]{0,20}PRIVATE KEY(?: BLOCK)?-----",
        (
            "-----BEGIN RSA PRIVATE KEY-----",
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "-----BEGIN EC PRIVATE KEY-----",
            "-----BEGIN PGP PRIVATE KEY BLOCK-----",
        ),
        ("-----BEGIN PUBLIC KEY-----", "-----BEGIN CERTIFICATE-----"),
        self_anchored=True,
    ),
    _r(
        "putty-private-key",
        "Chave privada no formato PuTTY",
        r"PuTTY-User-Key-File-[0-9]{1,2}:",
        ("PuTTY-User-Key-File-3: ssh-rsa",),
        ("PuTTY-User-Key-File",),
        self_anchored=True,
    ),
    _r(
        "pkcs8-encrypted-key",
        "Chave privada PKCS#8 cifrada",
        r"-----BEGIN ENCRYPTED PRIVATE KEY-----",
        ("-----BEGIN ENCRYPTED PRIVATE KEY-----",),
        ("-----BEGIN PUBLIC KEY-----",),
        self_anchored=True,
    ),
    _r(
        "age-secret-key",
        "Chave secreta do age",
        r"AGE-SECRET-KEY-1[0-9A-Z]{58}",
        ('KEY = "AGE-SECRET-KEY-1' + "A" * 58 + '"',),
        ("AGE-SECRET-KEY-1", "age1" + "a" * 58),
    ),
)


# --- Banco de dados ------------------------------------------------------------

DB_RULES: tuple[Rule, ...] = (
    _r(
        "postgres-connection-string",
        "String de conexão do PostgreSQL com senha",
        r"postgres(?:ql)?://[A-Za-z0-9_.-]{1,60}:[^@\s/'\"]{3,120}@[A-Za-z0-9_.-]{1,80}",
        ('DATABASE_URL = "postgresql://app:s3nh4Sup3r@db.exemplo.com:5432/prod"',),
        ("postgresql://app@db.exemplo.com/prod", "postgres://localhost/dev"),
        self_anchored=True,
    ),
    _r(
        "mysql-connection-string",
        "String de conexão do MySQL com senha",
        r"mysql://[A-Za-z0-9_.-]{1,60}:[^@\s/'\"]{3,120}@[A-Za-z0-9_.-]{1,80}",
        ('DB = "mysql://root:s3nh4Sup3r@127.0.0.1:3306/app"',),
        ("mysql://root@127.0.0.1/app",),
        self_anchored=True,
    ),
    _r(
        "mongodb-connection-string",
        "String de conexão do MongoDB com senha",
        r"mongodb(?:\+srv)?://[A-Za-z0-9_.-]{1,60}:[^@\s/'\"]{3,120}@[A-Za-z0-9_.-]{1,80}",
        ('MONGO_URL = "mongodb+srv://app:s3nh4Sup3r@cluster0.exemplo.mongodb.net"',),
        ("mongodb://localhost:27017/app",),
        self_anchored=True,
    ),
    _r(
        "redis-connection-string",
        "String de conexão do Redis com senha",
        r"redis(?:s)?://[A-Za-z0-9_.-]{0,60}:[^@\s/'\"]{3,120}@[A-Za-z0-9_.-]{1,80}",
        ('REDIS_URL = "redis://:s3nh4Sup3r@cache.exemplo.com:6379"',),
        ("redis://localhost:6379",),
        self_anchored=True,
    ),
    _r(
        "amqp-connection-string",
        "String de conexão AMQP com senha",
        r"amqps?://[A-Za-z0-9_.-]{1,60}:[^@\s/'\"]{3,120}@[A-Za-z0-9_.-]{1,80}",
        ('BROKER = "amqps://user:s3nh4Sup3r@rabbit.exemplo.com:5671"',),
        ("amqp://localhost:5672",),
        self_anchored=True,
    ),
)


#: Registro único do catálogo. Uma regra que não está aqui **não existe** — precedente
#: `gitleaks/cmd/generate/config/main.go:30`. É também onde o revisor vê o catálogo
# --- Genéricas: ancoradas por palavra-chave ------------------------------------

#: Palavras que precedem uma credencial em código real.
#:
#: A lista é curta de propósito. Cada palavra acrescentada aumenta a superfície de falso
#: positivo, e o M2 mediu **zero falsos positivos** justamente por não ter nenhuma regra
#: desta família — o que também significava que `aws_secret_access_key = "..."` passava
#: sem ser vista. O identificador da chave AWS (`AKIA...`) nós detectávamos; a credencial
#: de fato, não.
_PALAVRAS_DE_SEGREDO = (
    "aws_secret_access_key",
    "secret_access_key",
    "client_secret",
    "private_key",
    "secret_key",
    "access_token",
    "auth_token",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "senha",
    "secret",
    "token",
)

#: O valor precisa ter ao menos 20 caracteres **e conter dígito e letra**.
#:
#: A exigência de dígito E letra é o que separa uma credencial de um identificador de
#: código: `secret_key = settings.SECRET_KEY` e `token = os.environ["X"]` não têm dígito;
#: `api_key = 12345678901234567890` não tem letra e parece número de série. Medido sobre
#: **72.570 linhas** de código real dos peers (excluídas as definições de regra, que contêm
#: segredo de exemplo por natureza): **zero falsos positivos**, contra 26 sem a exigência.
#:
#: As lookaheads têm teto (`{0,79}`, não `*`) porque o guard do M2 proíbe quantificador
#: livre no catálogo — nenhuma regex pode pendurar o commit de alguém. Medido: 0,025 s no
#: pior caso adversarial de 4.000 caracteres.
_VALOR_DE_SEGREDO = (
    r"(?=[A-Za-z0-9/+=_.\-]{0,79}[0-9])"
    r"(?=[A-Za-z0-9/+=_.\-]{0,79}[A-Za-z])"
    r"[A-Za-z0-9/+=_.\-]{20,80}"
)

GENERIC_RULES: tuple[Rule, ...] = (
    Rule(
        id="generic-secret-assignment",
        description="Credencial atribuída a uma variável de nome revelador",
        pattern=keyword_assignment(_PALAVRAS_DE_SEGREDO, _VALOR_DE_SEGREDO),
        true_positives=(
            'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
            'password: "S3nh4Sup3rL0ngaDoBanco2026"',
            "api_key = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'",
            "CLIENT_SECRET=Xk8fJ2mNp4qRt6vYw9zAb1cDe3fGh5jK",
        ),
        false_positives=(
            'password = "changeme"',
            'token = os.environ["GITHUB_TOKEN"]',
            "api_key = get_api_key()",
            "secret_key = settings.SECRET_KEY",
            'password = "${VAULT_SECRET}"',
            "auth_token = None",
            'senha = "aaaaaaaaaaaaaaaaaaaaaaaaa"',
            "api_key = 12345678901234567890",
        ),
    ),
)


#: inteiro num lugar só, que é justamente o valor de manter a lista literal.
BUILTIN_RULES: tuple[Rule, ...] = (
    *CLOUD_RULES,
    *VCS_RULES,
    *AI_RULES,
    *SAAS_RULES,
    *KEY_RULES,
    *DB_RULES,
    *GENERIC_RULES,
)

#: Categorias do `README.md § O que ele detecta`, para o teste de cobertura.
CATEGORIES: dict[str, tuple[Rule, ...]] = {
    "cloud": CLOUD_RULES,
    "vcs": VCS_RULES,
    "ai": AI_RULES,
    "saas": SAAS_RULES,
    "keys": KEY_RULES,
    "db": DB_RULES,
    "generic": GENERIC_RULES,
}

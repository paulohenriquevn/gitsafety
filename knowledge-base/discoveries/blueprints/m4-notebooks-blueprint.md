# Blueprint: Notebooks Jupyter (M4)

**Slug:** `m4-notebooks`
**Plano de origem:** `knowledge-base/discoveries/plans/m4-notebooks-plan.md` (v1.0)
**Data:** 2026-07-27
**Questões:** 6 respondidas, 0 BLOCKED

> **Natureza da evidência (ADR D2 do plano).** Nenhum peer parseia notebook, então a fonte
> primária aqui é **execução reproduzível** — notebooks sintéticos gerados, varridos e com
> a saída transcrita — no mesmo nível de rigor de uma citação `arquivo:linha`.

## Context

O `docs/PRD.md § 2` identifica a saída salva de célula como o vetor mal coberto que motiva
o público de cientistas de dados. O `ROADMAP.md § M4` nomeia dois riscos: variação entre
`nbformat` v3 e v4, e notebook grande pulado em silêncio.

O que a descoberta acrescentou ao enunciado: **a varredura atual já acha a maior parte**, e
o valor do M4 é mais estreito e mais preciso do que "passar a suportar notebooks".

## Coverage Corner 1 — Integration Tests

### Q4 — O que a varredura atual perde, medido

Notebook sintético com **5 segredos** em posições distintas, varrido com o gitsafety
`v0.4.0`:

| # | Posição | Encontrado? |
|---|---|---|
| 1 | Código da célula 1 | ✅ linha 6 |
| 2 | Saída `stream` da célula 2 | ✅ linha 24 |
| 3 | Código da célula 3, **partido entre elementos de `source`** | ❌ |
| 4 | Saída `execute_result` da célula 4 | ✅ linha 53 |
| 5 | Célula `markdown` | ✅ linha 62 |

**4 de 5 encontrados. Um falso negativo, 20%.**

A causa do único que escapa, do JSON cru (`medida.ipynb:32`):

```json
   "c = 'postgresql://app:s3nh4",
```

O valor continua no elemento seguinte da lista `source`, e entre os dois o JSON insere
`",\n   "`. Nenhuma regex de linha atravessa isso.

**Duas conclusões que mudam o enunciado do milestone:**

1. **Detectar não é o problema.** Varrer o JSON como texto acha 4 de 5, incluindo as duas
   saídas salvas — que é o vetor que o PRD nomeia. Dizer que "notebooks não são
   suportados" seria falso.
2. **Localizar é o problema.** As linhas reportadas — 6, 24, 53, 62 — são do **JSON**. Um
   notebook aberto no Jupyter não tem linha 53; o usuário recebe um número que não
   consegue usar. É a lacuna real, e ela é de usabilidade, não de cobertura.

> **Ressalva honesta sobre a medição.** A primeira execução deste teste reportou 3 de 5, e
> o número estava errado: o heredoc do shell não estava aspado e comeu a variável da
> célula markdown, de modo que o quinto segredo nunca foi plantado. Corrigido com heredoc
> aspado. Registrado porque um número errado num blueprint vira requisito errado no plano.

## Coverage Corner 2 — Dependencies

### Q6 — O parsing acrescenta dependência?

`.ipynb` **é** um documento JSON, e a estrutura necessária — `cells[].source`,
`cells[].outputs[]` — é alcançável com `json.loads` e indexação de dicionário. Verificado
por execução: o percurso das saídas na Q3 abaixo usou apenas `json` da stdlib.

**Veredito: nenhuma dependência nova.** `nbformat` traria validação de esquema e migração
entre versões — e a validação é justamente o que **não** queremos: um notebook que o
`nbformat` rejeita ainda pode conter segredo que devemos achar. O `docs/PRD.md § NFR-1` já
está esgotado desde o M3, então a alternativa nem estava disponível.

## Coverage Corner 3 — Tools

### Q5 — Notebook grande é pulado em silêncio?

Não. O limite de 1 MB do M0 age em `walker._classify`, e o arquivo pulado entra em
`skipped`, que a saída resume — comportamento decidido no ADR D3 do M0 exatamente para
que descarte nosso nunca seja invisível.

O **Risco nº 2 do M4** ("notebook grande pulado em silêncio") está, portanto, **já
mitigado** pela decisão do M0. O que resta é confirmar por teste, não construir.

A ressalva que permanece: notebook com saída de imagem embutida passa de 1 MB com
facilidade, então o caso é **frequente** — e o resumo dizer "1 arquivo pulado" é pouco
informativo quando o arquivo é justamente o notebook que o usuário queria verificar.

## Coverage Corner 4 — Techniques

### Q1 — O que o gitleaks faz com `.ipynb`

`knowledge-base/references/gitleaks/detect/utils.go:41-43` e `:84-86`:

```go
ext := strings.ToLower(filepath.Ext(filePath))
if ext == ".ipynb" || ext == ".md" {
    link += "?plain=1"        // GitHub
    // e, no outro trecho:
    link += "?display=source" // Bitbucket
}
```

É **formatação de link**, não parsing. O gitleaks varre o JSON como texto e, ao montar a
URL do achado, acrescenta um parâmetro para que a plataforma mostre o arquivo como código
— porque de outro modo o número de linha do JSON não corresponderia a nada na vista
renderizada.

**Confirmado: nenhum peer parseia notebook.** E a solução deles é reveladora: eles têm
exatamente o mesmo problema de localização que a Q4 mediu, e o resolvem **na apresentação**
em vez de na varredura, porque escrevem links e nós escrevemos caminhos locais.

### Q2 — Estrutura mínima a percorrer

Verificado por execução sobre notebook `nbformat` 4.5:

```
cells[]
  ├─ cell_type   : "code" | "markdown" | "raw"
  ├─ source      : lista de strings (uma por linha) — em v3, `input`
  └─ outputs[]   : só em células de código
```

`source` ser **lista de linhas** é o detalhe que explica a Q4: uma linha do notebook é um
elemento; um valor partido no meio de uma linha ocupa dois elementos e vira duas linhas do
JSON. Juntar os elementos antes de varrer é o que fecha a lacuna.

### Q3 — Onde o texto mora em cada tipo de saída

Verificado por execução, gerando um notebook com os quatro tipos e percorrendo o JSON:

| `output_type` | Onde está o texto |
|---|---|
| `stream` | `text` (lista de linhas) |
| `execute_result` | `data["text/plain"]` |
| `display_data` | `data["text/plain"]` |
| `error` | `traceback` (lista) e `evalue` |

Quatro caminhos distintos. Cobrir só `stream` — o mais óbvio, porque é o do `print` —
deixaria escapar o `execute_result`, que é o que aparece quando a **última expressão da
célula** é o valor: `os.environ` sozinho numa célula produz `execute_result`, não `stream`.

E o `error` importa mais do que parece: um traceback carrega a linha de código que falhou,
com os valores. Uma exceção durante uma chamada autenticada deixa a credencial no
traceback salvo.

**Sobre o Risco nº 1 (v3 × v4):** em `nbformat` v3 as células de código usam `input` em vez
de `source`, e as saídas têm o texto em `text` mesmo para resultados. Tratar apenas `source`
produziria falso negativo silencioso em notebook antigo — que é exatamente o risco
declarado. A mitigação é aceitar ambas as chaves, não migrar o documento.

## Cross-cutting Comparison

| Dimensão | gitleaks | gitsafety hoje (v0.4.0) | Decisão para o M4 |
|---|---|---|---|
| Parseia notebook | **Não** | Não | **Sim** — é o diferencial |
| Acha segredo em saída salva | Incidental (texto) | Incidental — 4/5 medido | Explícito |
| Localização do achado | Linha do JSON + `?plain=1` no link | Linha do JSON | **Célula + linha na célula** |
| Valor partido em `source` | Perde | Perde (medido) | Junta os elementos antes de varrer |
| `execute_result` / `error` | Incidental | Incidental | Explícito |
| v3 vs v4 | n/a | n/a | Aceitar `source` **e** `input` |
| Notebook > 1 MB | n/a | Pulado, reportado em `skipped` | Já mitigado no M0 |
| Dependência | — | — | Nenhuma; `json` da stdlib |

## ADRs

### D1 — Parsear o notebook, e reportar célula + linha dentro da célula

**Decisão:** `.ipynb` é lido como JSON; o achado reporta a **célula** e a **linha dentro
dela**, não a linha do arquivo.

**Rationale:** a Q4 mediu que detectar já funciona em 4 de 5 casos — o que **não** funciona
é localizar: as linhas 6, 24, 53 e 62 são do JSON, e um notebook aberto no Jupyter não tem
linha 53. O gitleaks tem o mesmo problema e o resolve na apresentação
(`detect/utils.go:41-43`), o que só serve a quem escreve links.

**Alternativas consideradas:** (a) manter a varredura como texto e documentar que a linha é
do JSON — deixa o usuário sem como agir, e ele abre o notebook renderizado, não o JSON; (b)
reportar linha do JSON **e** célula — dois números para o usuário reconciliar, contra o
`docs/PRD.md § 4`; (c) reportar só o número da célula — insuficiente numa célula de 80
linhas.

**Consequências:** o `Finding` precisa carregar a localização em notebook, ou a `path`
precisa codificá-la. Codificar no caminho (`nb.ipynb:célula 3:linha 2`) evita mudar a
dataclass que quatro milestones consomem.

### D2 — Juntar os elementos de `source` antes de varrer

**Decisão:** `"".join(source)` antes de aplicar as regras, e a numeração de linha derivada
do texto reconstituído.

**Rationale:** é a causa medida do único falso negativo da Q4. O `source` é uma lista de
**linhas**, mas o Jupyter pode quebrar no meio de uma linha, e o JSON insere `",\n   "`
entre os elementos. Nenhuma regex de linha atravessa isso; juntar antes, sim.

**Alternativas consideradas:** (a) varrer elemento a elemento — é o comportamento atual, e
foi ele que produziu o falso negativo; (b) juntar com `\n` — inseriria quebra onde não há,
deslocando a numeração e criando falso negativo novo em valores multilinha.

**Consequências:** a numeração de linha dentro da célula passa a vir do texto reconstituído,
que é o que o usuário vê no Jupyter. É o comportamento correto e exige `splitlines()` sobre
o texto unido, não sobre a lista.

### D3 — Cobrir os quatro tipos de saída, e as duas chaves de código

**Decisão:** varrer `stream.text`, `execute_result.data["text/plain"]`,
`display_data.data["text/plain"]`, `error.traceback` e `error.evalue`. Aceitar `source` e
`input` como origem do código.

**Rationale:** a Q3 mediu quatro caminhos distintos. Cobrir só `stream` — o mais óbvio,
porque é o do `print` — perderia `execute_result`, que é o que aparece quando a última
expressão da célula é o valor: `os.environ` sozinho produz `execute_result`. O `error`
importa porque traceback salvo carrega valores da chamada que falhou. E `input` fecha o
Risco nº 1 do roadmap sem migrar o documento.

**Alternativas consideradas:** (a) só `stream` — o caso do `print`, que é o mais citado e
não é o único; (b) varrer o `data` inteiro, todos os mime-types — `image/png` é base64 de
imagem e produziria ruído sem ganho; (c) usar `nbformat` para normalizar v3→v4 — segunda
dependência, vedada.

**Consequências:** mais caminhos para manter quando o formato evoluir. Mitigado por serem
dados, não lógica: uma tabela de caminhos, não uma cadeia de `if`.

### D4 — Notebook malformado degrada para varredura de texto, não falha

**Decisão:** se o `json.loads` falhar, o arquivo é varrido **como texto**, com um aviso na
saída — não é erro, e não é pulado.

**Rationale:** um `.ipynb` corrompido ou truncado ainda pode conter a credencial, e ela
ainda importa. Falhar recusaria a varredura de um arquivo que o usuário quer verificar;
pular em silêncio é o falso negativo que o ADR D3 do M0 proíbe. Varrer como texto é
exatamente o comportamento de hoje, que a Q4 mediu como 4/5 — degradação para um estado
conhecido, não para o desconhecido.

**Alternativas consideradas:** (a) erro tipado e exit 2 — recusa o arquivo em vez de fazer
o possível, e um notebook quebrado no meio de uma varredura de mil arquivos derrubaria
tudo; (b) pular em silêncio — contraria o M0 D3; (c) pular e reportar em `skipped` —
melhor que (b), mas ainda deixa de achar o que a varredura de texto acharia.

**Consequências:** um notebook malformado produz achados com linha do JSON, não com
célula. A saída precisa dizer isso, senão o usuário procura uma célula que o relatório não
conseguiu identificar.

## Recommendations

1. **Parsear `.ipynb` como JSON** e reportar **célula + linha na célula** (D1) — a lacuna
   medida é de localização, não de detecção.
2. **Juntar os elementos de `source`** antes de varrer (D2) — fecha o único falso negativo
   medido.
3. **Cobrir os quatro tipos de saída** e aceitar `source`/`input` (D3) — `execute_result` e
   `error` são os esquecidos, e `input` fecha o Risco nº 1.
4. **Degradar para texto** quando o JSON não parsear (D4), com aviso.
5. **Confirmar por teste** que notebook acima de 1 MB aparece em `skipped` — o Risco nº 2
   já está mitigado pelo M0; falta a evidência.
6. **Não adotar `nbformat`** — `json` da stdlib basta, e o orçamento de dependências
   acabou no M3.
7. **Medir o custo do parsing** contra a varredura de texto: parsear JSON é mais caro que
   ler linhas, e notebooks são grandes.

## Blocked questions

Nenhuma. Todas as seis respondidas — quatro por execução reproduzível (ADR D2 do plano) e
duas por citação a `knowledge-base/references/gitleaks/detect/utils.go`.

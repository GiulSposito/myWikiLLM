# Plano: Otimização de Agentes e Skills da Wiki

## Contexto

A wiki possui 300+ páginas (106 no knowledge graph principal + ~200 no data-dictionary), 35+ fontes ingeridas e um pipeline de ingestão maduro. O pipeline usa 5 subagentes especializados orquestrados pelo skill `wiki-ingest`, que atualmente opera de forma sequencial e delega cada entidade/conceito em chamadas separadas. O objetivo é reduzir tokens consumidos e tempo de execução sem degradar a qualidade do conhecimento compilado.

### Avaliação de Impacto de Qualidade por Otimização

| # | Otimização | Risco de Qualidade | Risco de UX | Mitigação necessária |
|---|-----------|-------------------|-------------|---------------------|
| 1 | Batch entity+concept curator | BAIXO | Nenhum | Limitar a 5 itens por batch; instrução anti-cross-contamination |
| 2 | Paralelismo entity ↔ concept | ZERO | Nenhum | — |
| 3 | source-reader saída condicional | BAIXO | Nenhum | Garantir metadata + claims sempre presentes |
| 4 | Threshold inline vs. subagente | MÉDIO | Nenhum | Threshold conservador + excluir transcripts/schemas |
| 5 | Contradiction-reviewer pré-filtrado | BAIXO | Nenhum | Usar páginas já linkadas no source (não heurística de tags) |
| 6 | wiki-linter single-pass | ZERO | Nenhum | — |
| 7 | wiki-query lazy overview.md | ZERO | Levemente melhor | overview.md está desatualizada (confirmado na exploração) |
| 8 | Step 12b reuso de dados coletados | ZERO | Nenhum | — |
| 9 | Curators modo update cirúrgico | BAIXO | Nenhum | Instrução explícita: append to section, não reescrever página |

**Conclusão**: Nenhuma das otimizações reduz qualidade se implementadas com as mitigações acima. Três têm risco zero. As demais têm risco baixo com mitigação simples.

---

## Mudanças por Arquivo

### 1. `.claude/agents/source-reader.md`

**Otimização 3: Saída condicional**

Adicionar regra explícita no bloco `## Rules`:
```
- Omitir seções sem conteúdo — não escrever placeholders ("None", "N/A", "—")
- Seções obrigatórias (sempre presentes): Metadados bibliográficos, Claims principais
- Seções condicionais (incluir apenas se houver conteúdo): Citações importantes, Contradições internas, Limitações declaradas, Referências citadas
```

Adicionar modo tiered no início do `## Output esperado`:
```
## Modo de extração
- Documento < 800 palavras, tipo artigo/web-clipping: extração compacta (apenas seções com conteúdo)
- Demais documentos: extração completa (incluir todas as seções que têm conteúdo)
```

---

### 2. `.claude/agents/concept-curator.md`

**Otimizações 1 + 9: Batch mode + Update cirúrgico**

Adicionar bloco `## Modos de operação` após `## Role`:

```markdown
## Modos de operação

### CREATE (página nova)
Escrever página completa usando o template. Criar o arquivo em wiki/concepts/<slug>.md.

### UPDATE (página existente)
- Ler o arquivo existente primeiro
- Usar Edit para fazer mudanças cirúrgicas: adicionar claims à seção "Source-Backed Claims", adicionar alias, atualizar sources[] e updated:
- NUNCA reescrever a página inteira — apenas as seções que mudam
- Registrar source anterior se sobrescrevendo um claim

### BATCH (lista de conceitos)
- Aceitar uma lista de até 5 conceitos para processar em uma única resposta
- Processar cada item de forma COMPLETAMENTE INDEPENDENTE — não cruzar fatos entre itens
- Para cada item: aplicar o fluxo de decisão (buscar existente → CREATE ou UPDATE)
- Retornar confirmação de cada item processado
```

---

### 3. `.claude/agents/entity-curator.md`

**Otimizações 1 + 9: Batch mode + Update cirúrgico**

Mesma estrutura que concept-curator. Adicionar bloco `## Modos de operação`:

```markdown
## Modos de operação

### CREATE (entidade nova)
Escrever página completa usando o template. Criar o arquivo em wiki/entities/<slug>.md.

### UPDATE (entidade existente)
- Ler o arquivo existente primeiro
- Usar Edit para adicionar fatos à seção "Key facts" e atualizar sources[] e updated:
- NUNCA reescrever a página inteira
- Se um fato novo conflitar com um existente: registrar ambos com suas fontes

### BATCH (lista de entidades)
- Aceitar lista de até 5 entidades para processar em uma única resposta
- Processar cada item INDEPENDENTEMENTE — não cruzar fatos entre itens
- Para cada item: aplicar o fluxo de decisão (buscar existente → CREATE ou UPDATE)
- Retornar confirmação de cada item processado
```

---

### 4. `.claude/agents/contradiction-reviewer.md`

**Otimização 5: Input pré-filtrado**

Alterar o bloco `## Rules` — primeira linha (input specification):

```markdown
# ANTES:
- Recebe como input:
  - (a) Lista de claims extraídos da nova fonte (output do source-reader)
  - (b) Páginas wiki relevantes existentes a serem comparadas

# DEPOIS:
- Recebe como input:
  - (a) Lista de claims extraídos da nova fonte (output do source-reader)
  - (b) Páginas wiki explicitamente linkadas no source page sob "Relevant Entities" e "Relevant Concepts" — essas são as páginas com maior probabilidade de conflito
  - Nota: páginas NÃO linkadas no source também podem ter conflitos, mas são de baixa prioridade e não fazem parte desta varredura inicial
```

---

### 5. `.claude/agents/wiki-linter.md`

**Otimização 6: Single-pass scanning**

Substituir o bloco `## Fluxo de execução` (10 passos) por versão single-pass:

```markdown
## Fluxo de execução (single-pass)

1. Mapear todos os arquivos .md no escopo
2. Inicializar estruturas: `files_data = {}`, `all_links = {}`, `inbound_counts = {}`
3. Para CADA arquivo (uma única leitura por arquivo):
   a. Parsear frontmatter YAML → registrar em files_data[path]
   b. Extrair todos [[wikilinks]] → registrar em all_links[path]
   c. Verificar campos obrigatórios → acumular missing_fields
   d. Coletar aliases → acumular alias_registry
4. Após leitura completa (processamento cruzado):
   a. Para cada link em all_links: verificar se destino existe em files_data → broken_links
   b. Para cada arquivo: contar inbound links → orphans (count == 0)
   c. Varrer alias_registry por duplicatas → duplicate_aliases
   d. Checar sources[] em cada arquivo → empty_sources
   e. Comparar files_data keys com wiki/index.md → not_in_index
5. Gerar JSON estruturado e salvar relatório
```

---

### 6. `.claude/skills/wiki-ingest/SKILL.md`

**Otimizações 1, 2, 4, 5, 8 — o maior arquivo a modificar**

#### Step 2: Threshold para delegação

```markdown
### Step 2: Read the source
Classify the source before reading:
- Se documento < 800 palavras E tipo = article/web-clipping (NÃO transcript, schema, slide-deck, data-catalog):
  → Extrair inline, sem delegar ao source-reader subagent
- Caso contrário:
  → Delegate to source-reader subagent (comportamento atual)
```

#### Steps 4+5: Batch + Paralelismo

```markdown
### Steps 4+5: Process entities AND concepts (parallel + batch)

Execute Steps 4 e 5 SIMULTANEAMENTE (em paralelo):

**Entidades (Step 4):**
- Coletar TODAS as entidades identificadas
- Dividir em batches de máximo 5 itens
- Para cada batch: delegate to entity-curator subagent (BATCH mode)
- Registrar durante processamento: {slug, source_count_after_update} para Step 12b

**Conceitos (Step 5):**
- Coletar TODOS os conceitos identificados
- Dividir em batches de máximo 5 itens
- Para cada batch: delegate to concept-curator subagent (BATCH mode)
- Registrar durante processamento: {slug, source_count_after_update} para Step 12b

Aguardar conclusão de ambos antes de prosseguir para Step 6.
```

#### Step 7: Contradiction reviewer com input pré-filtrado

```markdown
### Step 7: Contradiction review
Fornecer ao contradiction-reviewer APENAS as páginas explicitamente linkadas no source page criado no Step 3 (seções "Relevant Entities" e "Relevant Concepts"). Não passar todas as páginas tocadas — apenas as linkadas diretamente.
```

#### Step 12b: Reuso de dados coletados

```markdown
### Step 12b: Post-ingest query ritual
Usar os dados já coletados nos Steps 4+5 para responder as três perguntas de encerramento:
- **source_count_registry** (coletado em Steps 4+5): lista de {slug, source_count} para todos os conceitos/entidades tocados → use para identificar promoção de status e concept-synthesis readiness sem releitura
- Para gap check em wiki/questions/: buscar apenas questões cujos `tags` interseccionem com as tags da nova fonte (filtro por relevância antes de ler arquivos)
```

---

### 7. `.claude/skills/wiki-query/SKILL.md`

**Otimização 7: Lazy overview.md**

Substituir Step 1:

```markdown
### Step 1: Orient
- Sempre: ler wiki/index.md para localizar páginas relevantes
- Ler wiki/overview.md APENAS SE a query é sobre estrutura do vault, convenções, domínios cobertos, ou uma questão ampla sem entidade/conceito específico
- Para queries pontuais (entidade específica, conceito específico, fato específico): pular overview.md e ir diretamente para a página relevante
```

---

## Ordem de Implementação

Implementar nesta ordem para evitar referências quebradas entre arquivos:

1. **Agentes** (independentes entre si — implementar em paralelo):
   - `source-reader.md` (mudança simples — adicionar regras)
   - `concept-curator.md` (adicionar modos de operação)
   - `entity-curator.md` (adicionar modos de operação)
   - `contradiction-reviewer.md` (alterar input spec)
   - `wiki-linter.md` (reescrever fluxo de execução)

2. **Skills** (dependem dos agentes atualizados):
   - `wiki-ingest/SKILL.md` (referencia os 4 agentes acima — implementar após eles)
   - `wiki-query/SKILL.md` (independente — pode ir junto)
   - `wiki-lint/SKILL.md` (referenciar o novo fluxo do linter)

## Verificação

Após implementação:
1. Rodar `/wiki-ingest` em um documento de teste (< 800 palavras) → confirmar que extrai inline sem subagente
2. Rodar `/wiki-ingest` em um documento maior → confirmar que curators recebem batch e rodam em paralelo com entity+concept simultâneos
3. Rodar `/wiki-lint` → confirmar relatório gerado sem erros
4. Rodar `/wiki-query` com pergunta pontual → confirmar que overview.md não é lido
5. Confirmar que a qualidade das páginas criadas é equivalente às criadas antes da otimização

# preco-teto v2 — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refatorar o CLI `radar` para `preco-teto` com interface simplificada, correção de bugs de índices, remoção de dependências instáveis e melhoria da fórmula `teto_por_dy`.

**Date:** 2026-03-24

---

## 1. Nome e Interface

### Antes
```bash
uv run radar acao VALE3
uv run radar fii HGLG11
uv run radar indices
```

### Depois
```bash
uv run preco-teto VALE3      # ação BR ou US, detectado automaticamente
uv run preco-teto HGLG11     # FII, detectado automaticamente
uv run preco-teto indices    # índices BR (CDI e IPCA)
```

- `pyproject.toml`: `name = "preco-teto"`, entry point `preco-teto = "preco_teto.cli:app"`
- Diretório: `src/preco_teto/` (renomear de `src/radar/`)
- Subcomando `acao` removido — o ticker é passado direto
- O CLI detecta automaticamente se é ação BR, ação US, FII ou ETF

---

## 2. Detecção de tipo de ativo

Ordem de detecção no CLI:

1. Se arg for `indices` → comando especial
2. Se ticker termina em `11` → tenta como FII via scraping fiiscom.br; se scraping falhar (ex: unit como `SANB11`, `TAEE11`), cai como ação BR
3. Se ticker termina em número → ação BR (ex: `VALE3`, `PETR4`)
4. Caso contrário → ação US (ex: `AAPL`, `MSFT`)

**Ativos sem dados suficientes (ETFs, units, ativos sem cobertura):** o CLI tenta calcular normalmente. Se todos os tetos retornarem `None`, exibir:
```
<TICKER> — cálculo de preço teto não disponível para este ativo.
```
Isso cobre ETFs BR e US, units, e qualquer ativo que o yfinance não consiga fornecer dados suficientes.

---

## 3. Índices BR — correções

### Remover
- `tesouro.py` inteiro — endpoint do Tesouro Direto está fora do ar
- Campo `juro_futuro` de `IndicesBR`
- Exibição de índices US no comando `indices`

### Renomear
- `fetch_selic()` → `fetch_cdi()` — série 11 BCB é taxa DI, não SELIC
- Campo `selic` → `cdi` em `IndicesBR` e em todos os outputs
- Labels no output: "CDI" em vez de "SELIC" ou "CDI (SELIC)"

### IndicesBR após mudança
```python
@dataclass
class IndicesBR:
    cdi: float | None
    ipca: float | None
    melhor_indice: float | None  # max(cdi * 0.85, ipca + 2.0)
```

---

## 4. Índices US — hardcoded

Remover `fetch_indices_us()` e dependência de yfinance para índices.

```python
FED_FUNDS_US = 5.25  # atualizar manualmente quando Fed mudar
CPI_US = 3.1         # atualizar manualmente quando necessário
```

`IndicesUS` mantido como dataclass simples com esses valores, usado internamente nas fórmulas de ações US. **Não exibido** no comando `indices`.

---

## 5. Fórmulas — mudanças

### `teto_por_dy` para ações — nova implementação

**Antes:** `cotacao × dy_estimado / taxa` — redundante com Bazin.

**Depois:** dividendo anual médio dos últimos anos completos disponíveis via `t.dividends`:

```
# t.dividends = pd.Series com índice de datas e valores em R$/$ por pagamento
dividendos_por_ano = t.dividends.groupby(t.dividends.index.year).sum()
anos_completos = dividendos_por_ano[anos < ano_atual]  # exclui ano em curso
dividendo_medio = media(anos_completos[-3:])  # até 3 anos, usa o que tiver
teto_por_dy = dividendo_medio / (melhor_indice / 100)
```

- `taxa` = `melhor_indice` (`max(cdi * 0.85, ipca + 2.0)`) para BR; `FED_FUNDS_US` para US
- `CPI_US` não entra no `melhor_indice` US — é usado apenas como parâmetro `inflacao` no `teto_dcf`
- Usa até 3 anos completos; se tiver 1 ou 2 anos, usa o que tiver
- Pseudocode usa `pd.Series.mean()` para calcular a média
- Fallback: se zero anos completos disponíveis (sem histórico), usar `info['dividendRate']` do yfinance como `dividendo_medio`. Se `dividendRate` também for `None` ou `0`, retornar `None`. `teto_por_dy` pode coincidir com `teto_bazin` nesse caso — aceitável.

### `teto_por_dy` para FIIs
Manter comportamento atual: usa DY% do scraping fiiscom.br dividido por 100, sem média histórica.

### `teto_por_lucro`
Manter exatamente como está — heurística validada empiricamente.

### `teto_graham`, `teto_bazin`, `teto_dcf`
Sem mudanças.

---

## 6. Estrutura de arquivos

### Renomear
```
src/radar/          → src/preco_teto/
tests/              → sem mudança de estrutura
```

### Remover
```
src/preco_teto/services/tesouro.py   (deletar)
```

### Modificar
```
pyproject.toml                                  (nome, entry point)
src/preco_teto/cli.py                           (nova interface, detecção de tipo)
src/preco_teto/services/banco_central.py        (rename fetch_selic→fetch_cdi, campo selic→cdi)
src/preco_teto/services/referencia.py           (remover tesouro, hardcodar US, rename campos)
src/preco_teto/services/acao.py                 (adicionar dy_medio_3a, detecção ETF)
src/preco_teto/output/tabela.py                 (rename CDI, remover juro_futuro e índices US)
src/preco_teto/output/plain.py                  (idem)
src/preco_teto/output/json_out.py               (idem)
tests/conftest.py                               (atualizar fixtures)
tests/test_formulas.py                          (adicionar testes teto_por_dy novo comportamento)
tests/test_acao.py                              (adicionar teste ETF, dy_medio_3a)
tests/test_referencia.py                        (remover juro_futuro, atualizar CDI)
```

---

## 7. Testes

- 100% mock — zero chamadas externas
- Novos casos obrigatórios:
  - Todos os tetos `None` → mensagem "cálculo não disponível" (cobre ETFs, units, ativos sem dados)
  - `teto_por_dy` com histórico 3 anos → usa média
  - `teto_por_dy` sem histórico → fallback para dividendo atual
  - `IndicesBR` sem `juro_futuro`
  - Labels CDI corretos nos outputs
- Manter todos os 35 testes existentes passando (adaptados para nova nomenclatura)

---

## 8. Notas de implementação

- `FED_FUNDS_US = 5.25` e `CPI_US = 3.1` ficam em `referencia.py` com comentário `# atualizar manualmente`. Não há mecanismo automático de atualização — é responsabilidade do mantenedor.
- O comando `indices` exibe apenas CDI e IPCA. Nenhum índice US é exibido.
- Exemplo de output do comando `indices` após mudança:
  ```
  CDI:   14.65%
  IPCA:   5.85%
  ```

---

## 9. O que NÃO muda

- Lógica de scraping FII (`fiiscom.br`)
- Fórmulas `teto_graham`, `teto_bazin`, `teto_dcf`, `teto_por_lucro`
- `melhor_indice_br` — lógica interna igual, só renomeia campo
- Flags `--json`, `--plain` (sem flag = tabela rich)
- Estrutura src-layout com `uv`

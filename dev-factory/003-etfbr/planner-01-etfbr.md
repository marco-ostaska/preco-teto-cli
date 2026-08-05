# Planner: `--etfbr` — ETFs brasileiros via ETFs Brasil

## Problem

Confirmado (intake + conversa): flag **`--etfbr`** para ETFs listados na B3 que:

1. Busca **apenas** `https://www.etfsbrasil.com.br/etfs/{ticker}` (ticker minúsculo na URL)
2. Extrai cotação, VP/cota (via spread), min/max 52w (série de cotação no mesmo payload), metadados
3. Calcula `teto_nav = pl_cota`, `teto_margem`, prêmio/desconto vs VP, termômetro
4. **Sem fallback** — falha de rede, HTTP ≠ 200, ticker inexistente, ou campo obrigatório ausente → uma mensagem de erro e `return`
5. **Não altera** `--etf` / `_render_etf` / `fetch_etf`

**Branch:** `feat/etfbr` (criar na implementação). **Mode:** solo. **Rebase:** pendente na implementação (`main` limpo local).

## Chunk

`single chunk`

## ADRs

### ADR-1 — Serviço dedicado `fetch_etf_br` + dataclass `EtfBrData`

- **Decision:** novo módulo `src/preco_teto/services/etf_br.py` com `fetch_etf_br(ticker) -> EtfBrData`; levanta exceção tipada (`EtfBrFetchError`) em qualquer falha.
- **Context:** `etf.py` acoplado a StatusInvest/CVM (`etf.py:176-203`); BR path quebrado; US path não deve regredir.
- **Alternatives:** estender `fetch_etf` com flag — rejeitado (mistura fontes e lógica US).
- **Consequences:** testes isolados com HTML fixture; `--etf` intacto.

### ADR-2 — Parse híbrido SSR + RSC no mesmo GET

- **Decision:** um `requests.get` na página; BeautifulSoup para hero/facts; parser dedicado para chunks `self.__next_f.push` contendo (a) série spread/preço e (b) série cotação 365d.
- **Context:** VP só aparece na seção spread (RSC chunk ~`6e`); cotação hero está no SSR (`quoteValue`); 52w não tem label — min/max da série histórica.
- **Alternatives:** (2) headless browser — pesado; (3) chamar APIs internas do site — 404/inexistentes sem garantia.
- **Consequences:** fragilidade a mudança de layout → mitigar com fixture congelado + testes de regressão.

### ADR-3 — VP a partir do spread

- **Decision:** usar último ponto da série spread (%). Fórmula documentada no site: spread entre preço de fechamento e VP. Implementar como:

  ```text
  pl_cota = cotacao / (1 + spread_pct / 100)
  ```

  quando `spread_pct` é `(P - VP) / VP * 100` (padrão mercado BR). Validar sinal com fixture DIVO11 (spread pequeno, VP ligeiramente abaixo ou acima do preço). Se parse retornar VP explícito no futuro, preferir valor direto.

- **Consequences:** teste unitário fixa números do fixture; revisar se site mudar tooltip/definição.

### ADR-4 — Renderer dedicado `render_etfbr`

- **Decision:** três funções `render_etfbr` em `tabela.py`, `plain.py`, `json_out.py`; labels sem "-6%".
- **Context:** `render_etf` (`tabela.py:90-92`) hardcoded "Teto PL (-6%)"; kwargs P/FCF US não aplicam.
- **Consequences:** duplicação leve de layout; evita quebrar output `--etf`.

### ADR-5 — Erro único, sem output parcial

- **Decision:** `_render_etfbr` captura `EtfBrFetchError` e qualquer falha de validação; imprime:

  ```text
  {TICKER} — não foi possível obter dados do ETF (etfsbrasil.com.br).
  ```

  exit code 0 (consistente com mensagens existentes `cli.py:44`, `cli.py:85`).

- **Alternatives:** TyperException / exit 1 — rejeitado para manter padrão CLI atual.

## Hard constraints

| Constraint | Source | Check | Status |
|------------|--------|-------|--------|
| Fonte única etfsbrasil.com.br | intake + usuário | só uma URL no serviço | PASS |
| Sem fallback | usuário | nenhum import/call StatusInvest/yfinance/CVM/brapi/i10 | PASS |
| Erro se falhar | usuário | mensagem única; sem tetos parciais | PASS |
| Campos obrigatórios | intake | cotacao, pl_cota, low_52, high_52 ou raise | PASS |
| Sem DY / P/FCF / PEG | intake | não calcular nem renderizar | PASS |
| Sem -6% arbitrário | intake | `teto_nav = pl_cota` | PASS |
| Não alterar `--etf` | intake | `_render_etf`, `fetch_etf`, `render_etf` intactos | PASS |
| Flags mutuamente exclusivas | `cli.py:120-121` | `--etfbr` no mesmo guard | PASS |
| TDD pytest | `CLAUDE.md`, `tests/test_etf.py` | novos testes em `tests/test_etf_br.py` | PASS |
| Sem rede nos unit tests | `test_etf.py:54-69` | mock `requests.get` + fixture HTML | PASS |

## Approaches considered

### 1. SSR + parse RSC inline (recomendada)

- **Pros:** um GET; VP + histórico na mesma resposta; sem browser.
- **Cons:** parser RSC frágil; precisa fixture real congelado.
- **Risks:** deploy Next.js muda formato → testes pegam.

### 2. Headless (Playwright) na página

- **Pros:** lê gráfico como usuário.
- **Cons:** dependência pesada; lento; overkill para CLI.
- **Risks:** CI sem browser.

### 3. Só SSR (cotação + PL total, sem VP)

- **Pros:** parse simples.
- **Cons:** **não** entrega ancora patrimonial — inviabiliza objetivo.
- **Risks:** rejeitado.

## Recommended approach

**Approach 1** — SSR + RSC parser no mesmo fetch.

## Side effects

| Pergunta | Evidência | Resposta |
|----------|-----------|----------|
| Callers de `fetch_etf`? | `cli.py:36`, `tests/test_etf.py` | Nenhum; novo módulo isolado |
| `--etf` regressão? | `test_cli_main.py:85-171` | Intocado se `_render_etf` não mudar |
| Auto-FII `*11`? | `cli.py:131-137` | `--etfbr` deve ser checado **antes** do auto-FII |
| Renderers | três arquivos output | adicionar `render_etfbr`, não alterar `render_etf` |
| Config nova? | — | nenhuma |
| Rollback? | revert commit | seguro |

## Pre-execution simulation

| Path | Current | Planned | Risks | Result |
|------|---------|---------|-------|--------|
| `DIVO11 --etfbr` ok | N/A (flag não existe) | VP + margem + metadados | parse RSC | PASS com fixture |
| `DIVO11 --etfbr` site down | N/A | mensagem erro | timeout | PASS |
| `DIVO11 --etfbr` HTML sem spread | N/A | mensagem erro | layout change | PASS |
| `DIVO11 --etf` | PL vazio + margem SI | **igual** | — | PASS (intocado) |
| `SPY --etf` | US yfinance | **igual** | — | PASS |
| `DIVO11` sem flag | tenta FII → falha | **igual** | — | PASS |
| `--etf --etfbr` | N/A | `BadParameter` | — | PASS |
| `--json --etfbr` | N/A | `render_etfbr` json | — | PASS |

## Premortem

| Falha | Prevenção |
|-------|-----------|
| Site muda HTML hero | Fixture + seletor por classe estável (`quoteValue`, highlight fields) |
| RSC muda formato | Parser isolado + teste com snapshot real; falha explícita |
| Spread formula invertida | Teste com números conhecidos do fixture; documentar no código |
| VP e cotação de datas diferentes | Usar último par spread+preço da mesma série |
| Implementador adiciona fallback yfinance | Code review / constraint no intake |
| `--etfbr` após auto-FII | Ordem no `main`: checar `--etfbr` antes de `_is_fii` |
| Duplicar lógica de margem | Reusar `teto_margem` / `termometro_margem` (`formulas.py:123-145`) |

## Changes explained

1. **`etf_br.py`:** GET página, parse SSR, parse RSC, validar campos, montar `EtfBrData`.
2. **`cli.py`:** flag `--etfbr`, guard flags, `_render_etfbr`, ordem antes de auto-FII.
3. **Output:** `render_etfbr` (tabela/plain/json) com labels BR.
4. **Testes:** serviço (mock HTML), CLI (mock fetch), parser spread/52w unitário.

## Files to change

### `src/preco_teto/services/etf_br.py` (novo)

**Why:** isolamento da fonte ETFs Brasil.

**What:**

```python
@dataclass
class EtfBrData:
    ticker: str
    nome: str | None
    cotacao: float
    pl_cota: float
    premio_desconto_pct: float
    low_52: float
    high_52: float
    pl_total_mm: float | None
    taxa_adm_pct: float | None
    cotistas: int | None
    cnpj: str | None
    indice: str | None

class EtfBrFetchError(Exception): ...

def fetch_etf_br(ticker: str) -> EtfBrData: ...
```

**Protected:** nenhum (arquivo novo).

**Risk:** baixo.

---

### `src/preco_teto/cli.py:103-129` (+ `_render_etfbr` novo)

**Why:** expor flag e orquestração.

**What:**

```diff
+    etfbr: Annotated[bool, typer.Option("--etfbr")] = False,
...
+    if sum([etf, fii, etfbr]) > 1:
+        raise typer.BadParameter("Use apenas uma flag entre --etf, --fii e --etfbr.")
+
+    if etfbr:
+        _render_etfbr(ticker, renderer)
+        return
```

**`_render_etfbr`:**

```python
def _render_etfbr(ticker: str, renderer) -> None:
    try:
        data = fetch_etf_br(ticker)
    except EtfBrFetchError:
        typer.echo(f"{ticker} — não foi possível obter dados do ETF (etfsbrasil.com.br).")
        return
    idx = fetch_indices_br()
    tetos = {
        "teto_nav": round(data.pl_cota, 2),
        "pl_cota": round(data.pl_cota, 2),
        "teto_margem": teto_margem(data.cotacao, data.low_52, data.high_52),
        "premio_desconto_pct": round(data.premio_desconto_pct, 2),
    }
    if _todos_none({"teto_nav": tetos["teto_nav"], "teto_margem": tetos["teto_margem"]}):
        typer.echo(f"{ticker} — não foi possível obter dados do ETF (etfsbrasil.com.br).")
        return
    termometro = termometro_margem(...)
    renderer.render_etfbr(data, tetos, idx, termometro=termometro)
```

**Protected:** `_render_etf` (`cli.py:35-70`), fluxo `--etf`, auto-FII, ações.

**Risk:** médio (ordem das flags).

---

### `src/preco_teto/output/tabela.py` (+ `plain.py`, `json_out.py`)

**Why:** labels e metadados BR.

**What (tabela):**

| Teto | Valor | Potencial |
|------|-------|-----------|
| VP/cota | pl_cota | vs cotação |
| Teto NAV | pl_cota | idem |
| Prêmio/desconto | X,XX % | — |
| Teto Margem (52w) | teto_margem | ✓/✗ |

Footer: CDI, IPCA, termômetro, taxa adm, índice, cotistas, CNPJ.

**Protected:** `render_etf` existente (`tabela.py:81-98`).

**Risk:** baixo.

---

### `tests/conftest.py` — fixture `mock_etfsbrasil_divo11_html`

**Why:** HTML real congelado (truncado se necessário) com hero + chunk RSC mínimo para spread e histórico.

**Protected:** fixtures existentes.

---

### `tests/test_etf_br.py` (novo)

**Why:** TDD do serviço e parser.

**Cases:**

- `test_fetch_etf_br_extrai_cotacao_vp_e_52w` — mock GET, assert campos
- `test_fetch_etf_br_http_erro_levanta` — status 500
- `test_fetch_etf_br_html_sem_spread_levanta` — HTML incompleto
- `test_parse_spread_deriva_pl_cota` — unitário spread + preço → VP
- `test_parse_historico_52w` — min/max da série

---

### `tests/test_cli_main.py` — adicionar

- `test_cli_etfbr_chama_fetch_e_render`
- `test_cli_etfbr_erro_mensagem_unica`
- `test_cli_etfbr_exclusivo_com_etf`

**Protected:** testes `--etf` existentes.

## Existing code referenced

- Ordem/guards de flags: `cli.py:120-125`
- Mensagem indisponível: `cli.py:44`, `cli.py:85`
- Fórmulas margem/termômetro: `formulas.py:123-145`
- Padrão mock HTTP ETF: `tests/test_etf.py:10-41` (`requests.get` side_effect)
- Padrão CLI mock: `tests/test_cli_main.py:85-104`
- Parse BRL (reutilizar ou extrair helper corrigido de `etf.py:38-49` **só** em `etf_br.py` — não alterar `etf.py` nesta história)

## Tests

| Teste | Bug que pega |
|-------|----------------|
| parse spread → VP | regressão fórmula invertida |
| 52w min/max | margem errada se série truncada |
| fetch ok | integração parser + dataclass |
| fetch fail | fallback acidental |
| CLI erro | output parcial enganoso |
| CLI ok | wire renderer/tetos |
| flags exclusivas | combinação inválida |

**Framework:** pytest (`tests/test_etf.py:1-6`).

## Gates

### Architect gate

| Interface | Definição | Status |
|-----------|-----------|--------|
| `fetch_etf_br` | novo `etf_br.py` | PASS |
| `render_etfbr` | novo nos 3 outputs | PASS |
| `render_etf` / `fetch_etf` | `tabela.py:81`, `etf.py:176` | PASS (intocados) |
| `teto_margem` | `formulas.py:123` | PASS (reuso) |

### QA gate

- Framework: pytest, padrão `tests/test_etf.py`
- Cobertura: `etf_br.py`, `_render_etfbr`, guards CLI, 3 renderers
- Sem rede: mocks only
- **PASS** se todos os casos acima implementados

## Assumptions

| Assunção | Status |
|----------|--------|
| URL `https://www.etfsbrasil.com.br/etfs/{ticker.lower()}` | confirmado probe DIVO11/BOVA11 |
| Spread % = (P-VP)/VP×100 | inferred — validar com fixture; marcar no teste |
| Série cotação 365d no RSC permite min/max 52w | confirmado JS `cotacoes/chart/{id}/365/`; parser no mesmo HTML |
| Erro = exit 0 + echo | confirmado `cli.py:44-45` |
| Typer mutual exclusion estendida a 3 flags | inferred — padrão 2 flags em `cli.py:120-121` |

## Next steps

1. Aprovar plano.
2. `git checkout -b feat/etfbr`
3. TDD: fixture HTML → parser → `fetch_etf_br` → CLI → renderers.
4. `uv run pytest tests/test_etf_br.py tests/test_cli_main.py -v`
5. Smoke manual: `uv run preco-teto DIVO11 --etfbr` (rede real).

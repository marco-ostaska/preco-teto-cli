# Implementer: `--etfbr` — ETFs Brasil

## Planner reference

`dev-factory/003-etfbr/planner-01-etfbr.md`

## Steps completed

1. Criado `src/preco_teto/services/etf_br.py` com `fetch_etf_br`, parse SSR (BeautifulSoup) + chunks RSC Flight (`65`/`6e` dinâmicos via série Performance/Spread).
2. Adicionada flag `--etfbr` e `_render_etfbr` em `cli.py`, antes de `--etf` e auto-FII.
3. Adicionado `render_etfbr` em `tabela.py`, `plain.py`, `json_out.py`.
4. Fixture `tests/fixtures/etfsbrasil_divo11.html` + fixture pytest `mock_etfsbrasil_divo11_html`.
5. Testes `tests/test_etf_br.py` e casos CLI em `tests/test_cli_main.py`.

## Files changed

| File | Descrição |
|------|-----------|
| `src/preco_teto/services/etf_br.py` | Serviço ETFs Brasil |
| `src/preco_teto/cli.py` | Flag `--etfbr`, orquestração |
| `src/preco_teto/output/tabela.py` | Renderer Rich |
| `src/preco_teto/output/plain.py` | Renderer plain |
| `src/preco_teto/output/json_out.py` | Renderer JSON |
| `tests/fixtures/etfsbrasil_divo11.html` | HTML congelado DIVO11 |
| `tests/conftest.py` | Fixture mock |
| `tests/test_etf_br.py` | Testes serviço/parser |
| `tests/test_cli_main.py` | Testes CLI |

## Changes explained

- **`etf_br.py`:** GET único em `etfsbrasil.com.br/etfs/{ticker}`; cotação/metadados via SSR; VP via último spread do chunk Spread (`pl_cota = cotacao / (1 + spread/100)`); 52w via min/max de floats no chunk Performance (janela `cot*0.77..cot*1.11`).
- **`cli.py:74-98`:** `_render_etfbr` captura `EtfBrFetchError`, mensagem única, tetos `teto_nav`, `teto_margem`, `premio_desconto_pct`.
- **`cli.py:133-141`:** guard `sum([etf, fii, etfbr]) > 1`; `--etfbr` checado antes de `--etf`.

## Diff self-review

Todos os hunks planejados. `_render_etf` / `fetch_etf` intocados. Protected contracts preservados.

## Tests executed

```text
uv run pytest tests/test_etf_br.py tests/test_cli_main.py -v
16 passed

uv run preco-teto DIVO11 --etfbr
(smoke ok — VP 128.16, margem 108.81, termômetro Neutro)
```

## E2E test instructions

1. `uv run preco-teto DIVO11 --etfbr` — deve exibir VP/cota, Teto NAV, prêmio/desconto, margem 52w, metadados.
2. `uv run preco-teto DIVO11 --etf --etfbr` — deve falhar com mensagem de flags exclusivas.
3. `uv run preco-teto DIVO11 --etf` — comportamento anterior inalterado.

## Issues found

- Chunks RSC são binários (Flight `T` rows); parser usa heurística de floats em vez de decoder Flight completo — validado contra fixture e smoke live.

## Deviations

Nenhuma.

## Time spent

~1 sessão (investigação RSC + implementação TDD).

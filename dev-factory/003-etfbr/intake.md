# Intake: `--etfbr` — preço teto para ETFs brasileiros

## Slug & branch

- **Slug:** `003-etfbr` (nova; sequência após `001-etf-us-pfcf-peg`, `002-recomendacao-heuristica`; legacy `etfs-br-intake/` é histórico anterior e **não** será reutilizada)
- **Branch sugerida:** `feat/etfbr` (a criar na implementação)
- **Mode:** solo
- **Motivo pasta nova:** história distinta do `--etf` US/BR quebrado e do intake legacy de PL/DY; regra nova de fonte única sem fallback

## Problem

O fluxo atual `preco-teto TICKER --etf` trata ETFs BR via StatusInvest + CVM INF_DIARIO, mas em produção **não entrega PL/cota** (INF_DIARIO não contém FIIM/ETF listado) e aplica **-6% arbitrário** no PL. ETFs BR **não pagam dividendos** — teto por DY não se aplica.

Precisamos de uma flag **`--etfbr`** dedicada que:

1. Busca dados **somente** em [etfsbrasil.com.br](https://www.etfsbrasil.com.br/etfs/{ticker})
2. Calcula tetos ancorados em **VP/cota** (spread preço vs valor patrimonial) e **margem 52w** (derivada do histórico de cotação na mesma página)
3. **Sem fallback** (StatusInvest, Investidor10, yfinance, CVM, brapi): se fetch ou parse falhar → mensagem de erro e encerra
4. **Não altera** o comportamento de `--etf` (US continua yfinance + P/FCF/PEG; BR em `--etf` permanece como está até eventual depreciação futura)

## Codebase explored

- `src/preco_teto/cli.py:35-70` — `_render_etf`: `teto_pl = pl_cota * 0.94`, `fetch_etf`, índices BR sempre; P/FCF/PEG só se `cnpj == ""`
- `src/preco_teto/cli.py:103-129` — flags `--etf` / `--fii`; ETFs terminados em `11` caem em auto-FII sem flag (`cli.py:131-137`)
- `src/preco_teto/services/etf.py:176-203` — path BR: StatusInvest + `_load_latest_inf_diario_row`; CNPJ ok mas CVM retorna vazio para FIIM em produção (probe ao vivo ago/2026)
- `src/preco_teto/services/etf.py:38-49` — `_parse_brl_number` quebra inteiros BR (`1.989.174.468` → `None`)
- `src/preco_teto/output/tabela.py:81-98` — `render_etf` labels "Teto PL (-6%)", "PL por Cota", "Teto Margem"; kwargs P/FCF US
- `src/preco_teto/output/plain.py:63-76` — mesma estrutura
- `src/preco_teto/output/json_out.py:38-51` — JSON tetos + métricas US
- `src/preco_teto/formulas.py:123-145` — `teto_margem`, `termometro_margem` (reutilizáveis)
- `tests/test_etf.py:10-51` — mock CVM fictício faz BR passar nos testes; não reflete produção
- `tests/test_cli_main.py:85-140` — asserts `--etf` BR/US; sem `--etfbr`
- `dev-factory/etfs-br-intake/intake.md` — histórico: -6% PL, opções A/B/C; **supersedido** por esta história (fonte ETFs Brasil, sem DY)

### Fonte ETFs Brasil (probe ao vivo, ago/2026)

URL: `https://www.etfsbrasil.com.br/etfs/divo11`

**SSR (HTML parseável):**

| Campo | Exemplo DIVO11 |
|-------|------------------|
| Cotação | R$ 128,24 |
| Patrimônio líquido (R$ MM) | 2.250,16 |
| Taxa adm total | 0,50% |
| Cotistas | 48.778 |
| CNPJ | 13.416.245/0001-46 |
| Índice | IDIV |
| Gestor / Admin | Itaú Asset / Itaú Unibanco |
| DY | 0,00% |
| Carteira | top holdings % PL |
| Retorno vs IBOV | tabela mensal |

**Seção crítica:** "Spread entre o Preço de Fechamento e o Valor Patrimonial da Cota" — gráfico com série spread (%) + preço. Dados em payload Next.js RSC (chunk `6e:…`), não REST público.

**Não tem** min/máx 52 semanas explícitos no SSR; histórico de cotação (~365d) está no mesmo payload RSC (`/api/etfs/cotacoes/chart/{id}/365/` referenciado no JS interno, mas **sem fallback** — min/max 52w deve vir do parse do **mesmo** HTML/RSC da página.

**APIs públicas testadas:** `/api/etfs/...`, `/api/assets/...` → 404. Sem token, sem endpoint JSON estável além do HTML.

### CVM (contexto, não fonte v1)

- `registro_fundo_classe.zip`: DIVO11/BOVA11 existem como **FIIM** com CNPJ correto
- `INF_DIARIO`: 0 linhas para CNPJs FIIM — confirma por que `etf.py` BR falha hoje

## Project norms & constraints

- **Testes:** pytest + pytest-mock; fixtures em `tests/conftest.py`; TDD esperado (`CLAUDE.md`)
- **Tooling:** Python ≥3.11, `uv`, `requests`, `BeautifulSoup` já no projeto (`etf.py`, `fii.py`)
- **Padrão serviço:** dataclass + `fetch_*` em `src/preco_teto/services/`; CLI orquestra fórmulas + renderer
- **Renderers:** três implementações paralelas (`tabela`, `plain`, `json_out`) — mudança de output exige as três
- **CONSTRAINT:** `--etfbr` **sem fallback** — erro único, sem output parcial enganoso quando campos obrigatórios faltam
- **CONSTRAINT:** sem teto por DY/Bazin (ETF BR não paga proventos ao cotista)
- **CONSTRAINT:** sem P/FCF/PEG (métricas US)
- **CONSTRAINT:** não alterar `_render_etf` / `--etf` nesta história
- **CONSTRAINT:** flag `--etfbr` mutuamente exclusiva com `--etf` e `--fii` (mesmo padrão `cli.py:120-121`)
- **Red flag:** parse de Next.js RSC pode quebrar com deploy do site — testes usam HTML fixture congelado
- **Red flag:** scraping depende de `User-Agent` e disponibilidade do site — sem retry multi-fonte

## Decisions made

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| Flag | `--etfbr` separada | ETFs BR terminam em `11`; evita conflito auto-FII; não mistura com `--etf` US |
| Fonte de dados | **Somente** etfsbrasil.com.br | Especializada; tem spread VP; confirmado pelo usuário |
| Fallback | **Nenhum** | Pedido explícito: "se der erro só falar que deu erro" |
| VP/cota | Derivar do spread + preço de fechamento na mesma página | Métrica central; site define spread vs VP |
| Teto NAV | `pl_cota` puro (sem -6%) | Remove arbitrário; ancora no VP |
| Prêmio/desconto | `(cotacao / pl_cota - 1) * 100` | Informativo no output |
| 52 semanas | min/max do histórico de cotação parseado do **mesmo** fetch | Site não expõe label 52w; série existe no RSC |
| Campos obrigatórios | `cotacao`, `pl_cota`, `low_52`, `high_52` | Sem fallback parcial; falta qualquer um → erro |
| DY / dividendos | Fora de escopo | ETF BR não distribui (DY 0% no site) |
| `--etf` BR | Intocado | Escopo isolado |
| Output | `render_etfbr` dedicado (ou `render_etf` com flag interna) | Labels diferentes ("VP/cota", "Teto NAV", sem -6%) |
| Metadados extras | taxa adm, índice, PL total, cotistas, CNPJ | Footer ou bloco info; não entram em `tetos` |

## What was rejected

- **StatusInvest / CVM INF_DIARIO** — PL/cota inexistente para FIIM em produção
- **Investidor10** — cotação ok, sem VP/spread
- **brapi** — exige token; usuário quer fonte única gratuita
- **yfinance `.SA`** — sem `navPrice`; violaria regra sem fallback
- **Teto por DY** — ETF BR não paga
- **Manter -6% no PL** — sem base financeira
- **Fallback parcial** (mostrar só margem se VP falhar) — rejeitado com "sem fallback"
- **Reusar pasta `etfs-br-intake/`** — história e decisões diferentes

## Work chunks identified

**single chunk** — fetch + parse + CLI + renderers + testes formam um entregável indivisível.

## Next steps

1. Confirmar este intake.
2. Ler `planner-01-etfbr.md`.
3. Implementar com TDD após aprovação do plano (`dev-factory-implementer`).

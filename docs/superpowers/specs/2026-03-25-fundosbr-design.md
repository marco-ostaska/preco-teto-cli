# Design: fundos-br CLI

Data: 2026-03-25

---

## Contexto

Novo comando `fundos-br` no mesmo repositório `preco-teto` para avaliar fundos de investimento brasileiros por CNPJ. CLI separado do `preco-teto` (entry point próprio), compartilhando apenas `services/banco_central.py`. O `preco-teto` existente **não** é alterado — detecção por CNPJ não faz parte do escopo deste design.

---

## Estrutura de Arquivos

```
src/preco_teto/fundos/
├── __init__.py
├── cli.py                  # entry point: fundos-br CNPJ
├── services/
│   ├── __init__.py
│   ├── cadastro.py         # baixa/parseia cad_fi.csv da CVM
│   ├── cotas.py            # baixa ZIPs INF_DIARIO, extrai série de cotas
│   └── benchmark.py        # CDI histórico (BCB), DIVO11 (yfinance), BTC (yfinance)
├── formulas.py             # rentabilidade, volatilidade, drawdown, % CDI, consistência
├── termometro.py           # lógica dos termômetros de performance e consistência
└── output/
    ├── __init__.py
    └── tabela.py           # Rich table com cores e termômetros
```

`pyproject.toml` — segundo script:
```toml
[project.scripts]
preco-teto = "preco_teto.cli:main"
fundos-br  = "preco_teto.fundos.cli:main"
```

---

## Fluxo de Execução

```
fundos-br 26.199.519/0001-34
    │
    ├─ 1. Valida formato CNPJ (XX.XXX.XXX/XXXX-XX)
    ├─ 2. cadastro.py → baixa cad_fi.csv (cache 1d)
    │       extrai: nome, CLASSE_ANBIMA, taxa_adm, taxa_perf, gestor, PL, cotistas
    │       se SIT ≠ "EM FUNCIONAMENTO NORMAL" → erro claro
    ├─ 3. Detecta benchmark por CLASSE_ANBIMA:
    │       Renda Fixa* / Multimercado* → CDI (BCB série 12)
    │       Ações*                      → DIVO11.SA (yfinance)
    │       Cambial*                    → USDBRL=X (yfinance)
    │       Crypto*                     → BTC-USD (yfinance)
    │       não mapeado                 → prompt interativo: "Classe X não mapeada. Benchmark? [CDI/DIVO11/BTC/USD]: "
    │                                     se stdin não for TTY → fallback silencioso para CDI + aviso no output
    ├─ 4. cotas.py → baixa ZIPs dos últimos 36 meses
    │       progress bar: "Baixando dados CVM: 12/36 meses..."
    │       cache: mês atual TTL 1 dia, meses passados permanente
    │       filtra pelo campo CNPJ_FUNDO_CLASSE (nome exato da coluna no CSV dentro do ZIP)
    │       usando o CNPJ extraído do cadastro (campo CNPJ_FUNDO em cad_fi.csv)
    │       se CNPJ não encontrado em nenhum ZIP → erro: "Fundo sem dados de cotas na CVM"
    │       série resultado: DataFrame com colunas [DT_COMPTC, VL_QUOTA]
    ├─ 5. benchmark.py → histórico do benchmark no mesmo período
    ├─ 6. formulas.py → calcula todas as métricas
    ├─ 7. termometro.py → performance por período + consistência
    └─ 8. tabela.py → exibe output com cores
```

**Cache:** `~/.cache/preco-teto/cvm/`
- `cad_fi.csv` — TTL 1 dia
- `inf_diario_fi_AAAAMM.zip` — TTL 1 dia (mês atual), permanente (meses anteriores)

---

## Métricas

Calculadas para os períodos: 1m, 3m, 6m, 12m, 24m, 36m.

**Definição de período:** último dia útil com cota disponível como `cota_atual`; data de início = mesmo dia do mês N meses antes (ou dia útil anterior se não existir). Se o fundo não tiver dados suficientes para um período, a linha é exibida como `—` (não omitida).

**yfinance (Ações/Cambial/Crypto):** se yfinance retornar série mais curta que as cotas do fundo, calcula apenas os períodos cobertos; períodos sem dados do benchmark exibem `—`.

| Métrica | Fórmula |
|---------|---------|
| Rentabilidade | `(cota_atual / cota_inicio) - 1` |
| Benchmark acumulado | `prod(1 + r_i/100) - 1` onde `r_i` são as taxas diárias em % (BCB série 12 para CDI) |
| % Benchmark | `rentabilidade_fundo / benchmark_acumulado` — só interpretável quando benchmark > 0; se benchmark ≤ 0, exibir `N/A` |
| Volatilidade anual | `std(retornos_diários) × √252` |
| Drawdown máximo | maior queda pico→vale nos últimos 36m |
| Meses acima benchmark | contagem de meses onde fundo > benchmark do mês |
| Meses consecutivos abaixo | sequência atual de meses abaixo do benchmark |

**Nota:** taxa de adm e taxa de perf já estão implícitas no VL_QUOTA histórico — o retorno calculado é sempre após todas as taxas.

---

## Termômetros

### Performance por período (% benchmark)

| % Benchmark | Status |
|-------------|--------|
| ≥ 100% | Excelente |
| 95–99% | Bom |
| 90–94% | Neutro |
| 80–89% | Fraco |
| < 80% | Ruim |

### Consistência (36m — janela fixa de 36 meses)

Contagem sobre os últimos 36 meses completos. Se houver menos de 36 meses de dados, usa o máximo disponível e indica `(Nm disponíveis)` no output.

| % meses acima benchmark | Status |
|-------------------------|--------|
| ≥ 60% | Consistente |
| 50–59% | Irregular |
| < 50% | Inconsistente |

### Alertas (meses consecutivos abaixo do benchmark)

| Sequência atual | Alerta |
|-----------------|--------|
| < 6 meses | Nenhum |
| 6–11 meses | Atenção |
| ≥ 12 meses | Crítico |

### Cores na tabela de rentabilidade (coluna % Benchmark)

Neutro, Fraco e Ruim mapeiam para Vermelho. N/A e `—` não recebem cor.

| Valor | Cor |
|-------|-----|
| ≥ 100% | Verde |
| 95–99% | Amarelo |
| < 95% | Vermelho |

---

## Output Esperado

```
$ fundos-br 26.199.519/0001-34

ITAÚ PRIVILÈGE RENDA FIXA DI
CNPJ: 26.199.519/0001-34 | Classe: Renda Fixa Referenciado DI
Gestor: Itaú | Taxa Adm: 0,20% a.a. | Taxa Perf: —
PL: R$ 87,0 bi | Cotistas: 480.549

Rentabilidade vs CDI (bruto)
──────────────────────────────────────────────────────
Período   Fundo     CDI      % CDI   Performance
──────────────────────────────────────────────────────
1m        0,87%    0,88%    [amarelo]98,9%[/]   Bom
3m        2,63%    2,65%    [amarelo]99,2%[/]   Bom
6m        5,31%    5,35%    [amarelo]99,3%[/]   Bom
12m      10,65%   10,75%    [amarelo]99,1%[/]   Bom
24m      21,40%   21,60%    [amarelo]99,1%[/]   Bom
36m      32,10%   32,50%    [amarelo]98,8%[/]   Bom
──────────────────────────────────────────────────────

Risco
──────────────────────────────────────
Volatilidade 12m:   0,12% a.a.
Drawdown máximo:   -0,03%
Consistência 36m:   Consistente  (22/36 meses acima CDI)
Alerta:            Nenhum
──────────────────────────────────────
```

---

## Benchmarks por Tipo

| CLASSE_ANBIMA | Benchmark | Fonte |
|---------------|-----------|-------|
| Renda Fixa* | CDI bruto | BCB série 12 |
| Multimercado* | CDI bruto | BCB série 12 |
| Ações* | DIVO11.SA | yfinance |
| Cambial* | USDBRL=X | yfinance |
| Crypto* | BTC-USD | yfinance |
| não mapeado | pergunta ao usuário | — |

---

## Decisões Tomadas

- CLI separado `fundos-br`, módulo `src/preco_teto/fundos/`
- Compartilha apenas `banco_central.py` com `preco-teto`
- Comparação bruto vs bruto (taxas já embutidas no VL_QUOTA)
- Cache em `~/.cache/preco-teto/cvm/` com TTL diferenciado
- Progress bar durante download dos ZIPs
- Termômetros de performance (5 níveis) e consistência (3 níveis) em vez de veredicto binário
- Cores na coluna % benchmark: verde ≥ 100%, amarelo 95–99%, vermelho < 95%
- Benchmark para crypto: BTC-USD
- Benchmark para ações: DIVO11.SA (não IBOV)

---

## CNPJs de Teste

| CNPJ | Nome | Tipo | Observação |
|------|------|------|------------|
| `26.199.519/0001-34` | ITAÚ PRIVILÈGE RF DI | Renda Fixa DI | Ativo, R$87bi — caso base |
| `03.618.256/0001-55` | ITAÚ GLOBAL DINÂMICO | Multimercado | CANCELADO — testa SIT ≠ EM FUNCIONAMENTO NORMAL |

CNPJs para Ações, Cambial e Crypto devem ser adicionados antes da implementação desses tipos. **v1 implementa apenas Renda Fixa e Multimercado (benchmark CDI).** Ações/Cambial/Crypto são out-of-scope para v1.

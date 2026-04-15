# FII: Último Dividendo com Data e DY Mensal

**Data:** 2026-04-15
**Autor:** Marco Ostaska
**Status:** Draft

## Contexto

O CLI `preco-teto` mostra tetos para FIIs mas não exibe informações sobre o último rendimento pago. O usuário quer ver, na saída do FII, o valor do último dividendo, o mês/ano (ex: `Mar/2026`), e o DY mensal daquele dividendo sobre a cotação atual.

## Decisões de Design

### Campos novos no FiiData

| Campo | Tipo | Descrição |
|---|---|---|
| `ultimo_dividendo` | `float \| None` | Valor em R$ do último rendimento |
| `mes_ano_dividendo` | `str \| None` | Mês/ano do dividendo, formato `MMM/YYYY` (ex: `Mar/2026`) |
| `dy_mensal` | `float \| None` | DY mensal do último dividendo sobre a cotação atual (%) |

### Fonte primária: fiis.com.br

O scraper já acessa `fiis.com.br/<ticker>/`. Os blocos `.yieldChart__table__bloco--rendimento` contêm 6 linhas por rendimento:

1. Tipo ("Rendimento")
2. Data Base (`DD.MM.YYYY`) — **usar esta para mês/ano**
3. Data Pagamento
4. Cotação Base
5. DY mensal (`X,XX%`) — **usar este para DY mensal**
6. Rendimento (`R$ X,XX`) — **usar este para valor**

Expandir `_parse()` para extrair do primeiro bloco (mais recente):
- Data Base → converter `DD.MM.YYYY` para `MMM/YYYY` (ex: `31.03.2026` → `Mar/2026`)
- DY mensal → parsear `0,70%` para `0.70`
- Rendimento → já extraído como `dividendos[0]`

### Fallback: yfinance

Se o scraper não encontrar dados de dividendo (FII menos popular, página indisponível, HTML vazio):
- Usar `yfinance.Ticker(ticker + ".SA").info` para `lastDividendValue` e `lastDividendDate`
- `lastDividendDate` é Unix timestamp → converter para `MMM/YYYY`
- `dy_mensal` calculado como `ultimo_dividendo / cotacao * 100`

### Saída nos renderers

**Tabela Rich (padrão):** Adicionar linha após VPA na tabela do FII:
```
Último Div.  R$ 1,10  Mar/2026  DY: 0,70%
```

Na estrutura `_teto_row`, não faz sentido reusar (não é um teto). Adicionar linha customizada formatada manualmente abaixo da tabela de tetos, ou como linha extra na tabela com colunas adaptadas.

Decisão: adicionar como linha extra na tabela existente, usando as colunas Teto/Valor/Potencial/Status — Teto=`Último Div.`, Valor=`R$ 1,10  Mar/2026`, Potencial=`0,70%`, Status=em branco. Ou melhor: adicionar uma linha separada após a tabela, no rodapé, junto com CDI/IPCA:

```
CDI: X%   IPCA: Y%   Último div: R$ 1,10 (Mar/2026) DY: 0,70%   Termômetro: Neutro
```

Decisão final: linha no rodapé (após CDI/IPCA), é informação complementar, não um teto.

**Plain:** Adicionar ao rodapé:
```
CDI: X%  IPCA: Y%  Último div: R$ 1,10 (Mar/2026) DY: 0,70%  Termômetro: Neutro
```

**JSON:** Adicionar campos ao dict de saída:
```json
{
  "ultimo_dividendo": 1.10,
  "mes_ano_dividendo": "Mar/2026",
  "dy_mensal": 0.70
}
```

## Arquivos a Modificar

1. **`src/preco_teto/services/fii.py`**
   - Expandir `_parse()` para extrair data base, DY mensal do primeiro bloco de rendimento
   - Adicionar propriedades `data_base_dividendo`, `dy_mensal_html` ao `FiisComService`
   - Adicionar campos `ultimo_dividendo`, `mes_ano_dividendo`, `dy_mensal` ao `FiiData`
   - Adicionar fallback via yfinance em `fetch_fii()` quando scraper não retorna dados

2. **`src/preco_teto/cli.py`**
   - Passar novos campos de `FiiData` ao renderer

3. **`src/preco_teto/output/tabela.py`**
   - Adicionar info do último dividendo ao rodapé da tabela FII

4. **`src/preco_teto/output/plain.py`**
   - Adicionar info do último dividendo ao rodapé da saída FII

5. **`src/preco_teto/output/json_out.py`**
   - Adicionar campos ao JSON de saída FII

## Formato do mês/ano

Usar abreviação em português: `Jan`, `Fev`, `Mar`, `Abr`, `Mai`, `Jun`, `Jul`, `Ago`, `Set`, `Out`, `Nov`, `Dez`.

Mapping: `01→Jan, 02→Fev, 03→Mar, 04→Abr, 05→Mai, 06→Jun, 07→Jul, 08→Ago, 09→Set, 10→Out, 11→Nov, 12→Dez`

## Edge Cases

- **FII sem dividendos:** campos `None`, não mostra linha do último dividendo
- **Scraper sem acesso:** fallback yfinance
- **yfinance sem dados:** campos `None`, saída limpa sem erro
- **DY mensal zero ou negativo:** não exibir (campo `None`)

## Testes

- Testar parse do HTML com data `31.03.2026` → `Mar/2026`
- Testar conversão de `0,70%` → `0.70`
- Testar fallback yfinance com mock
- Testar renderer com e sem dados de dividendo
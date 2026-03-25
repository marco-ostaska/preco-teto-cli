# Design: benchmark explicito e benchmarks reais no fundos-br

Data: 2026-03-25

---

## Contexto

O comando `fundos-br` hoje assume `CDI` como benchmark real e, em alguns casos, apenas troca o rotulo do comparativo. Isso produz comparacoes enganosas para fundos que nao deveriam ser lidos contra `CDI`, como multimercados, ouro, exterior ou estrategias dolarizadas.

O objetivo e tornar a escolha do benchmark explicita e garantir que cada benchmark suportado tenha calculo real.

---

## Escopo

Adicionar ao `fundos-br`:
- flag `--benchmark`
- prompt interativo quando a flag nao for informada
- suporte real para benchmarks:
  - `CDI`
  - `DIVO11`
  - `IVV`
  - `BTC`
  - `USD`

Fora de escopo:
- detectar benchmark automaticamente por classe do fundo
- criar recomendacao automatica de benchmark
- modelar versao liquida para benchmarks diferentes de `CDI`

---

## Regras

### Escolha do benchmark

- Novo argumento opcional: `--benchmark`
- Valores aceitos: `CDI`, `DIVO11`, `IVV`, `BTC`, `USD`
- Se `--benchmark` for informado:
  - usar o benchmark escolhido
  - nao perguntar nada no terminal
- Se `--benchmark` nao for informado:
  - em TTY: perguntar `Benchmark? [CDI/DIVO11/IVV/BTC/USD]`
  - fora de TTY: usar `CDI` como fallback e marcar aviso no output

### Benchmarks reais

Cada benchmark deve ter sua propria serie historica para o mesmo intervalo das cotas do fundo:
- `CDI`: continuar usando serie do BCB
- `DIVO11`: usar historico de mercado
- `IVV`: usar historico de mercado
- `BTC`: usar historico de mercado
- `USD`: usar historico cambial

O comparativo por periodo deve usar o retorno acumulado real da serie escolhida. Nao basta trocar o nome da coluna.

### Output para `CDI`

Quando o benchmark escolhido for `CDI`:
- manter tabela atual com:
  - `CDI`
  - `% CDI`
  - `CDI Liq.`
  - `% CDI Liq.`
- manter simulacao de `R$ 100` com:
  - `CDB 100% CDI bruto`
  - `CDB 100% CDI liquido`
  - `Diferenca vs CDB liquido`

### Output para benchmarks nao-CDI

Quando o benchmark escolhido for `DIVO11`, `IVV`, `BTC` ou `USD`:
- a tabela deve mostrar apenas:
  - `Fundo`
  - `<benchmark>`
  - `% <benchmark>`
  - `Performance`
- nao mostrar colunas liquidas
- a simulacao de `R$ 100` deve mostrar:
  - `Fundo`
  - `<benchmark>`
  - `Diferenca vs <benchmark>`

### Termometros e consistencia

- `Performance` continua sendo derivada de `% benchmark`
- `Consistencia` e `Alerta` devem passar a usar o benchmark escolhido, nao `CDI` fixo
- a string de consistencia continua no formato ja adotado:
  - `13/28 (46,4%) meses acima <benchmark>`

---

## Arquivos Afetados

- Modificar: `src/preco_teto/fundos/cli.py`
  - adicionar flag `--benchmark`
  - resolver benchmark via flag ou prompt
  - carregar a serie correta do benchmark
  - calcular periodos, consistencia e alerta com o benchmark escolhido

- Modificar: `src/preco_teto/fundos/services/benchmark.py`
  - centralizar benchmarks suportados
  - adicionar fetch historico para benchmarks de mercado
  - adicionar fetch historico para `USD`

- Modificar: `src/preco_teto/fundos/formulas.py`
  - reutilizar ou adaptar helpers para benchmarks nao-CDI em periodos e consistencia

- Modificar: `src/preco_teto/fundos/output/tabela.py`
  - esconder colunas liquidas fora de `CDI`
  - ajustar simulacao de `R$ 100` para benchmark generico
  - manter aviso de fallback para execucao nao interativa sem `--benchmark`

- Modificar: `tests/fundos/test_benchmark.py`
  - cobrir benchmarks suportados e carregamento das series

- Modificar: `tests/fundos/test_cli.py`
  - cobrir uso da flag
  - cobrir prompt quando a flag nao vier
  - cobrir output `CDI` vs output nao-`CDI`

- Modificar: `tests/fundos/test_tabela.py`
  - cobrir ocultacao de colunas liquidas fora de `CDI`
  - cobrir texto da simulacao para benchmark generico

---

## Output Esperado

Exemplo com `IVV`:

```text
Rentabilidade vs IVV
Período | Fundo | IVV | % IVV | Performance

Se tivesse investido R$ 100 ha 12 meses:
Fundo: R$ 118,40
IVV: R$ 121,10
Diferenca vs IVV: -R$ 2,70 (-2,2%)
```

Exemplo com `CDI`:

```text
Rentabilidade vs CDI (bruto)
Período | Fundo | CDI | % CDI | CDI Liq. | % CDI Liq. | Performance

Se tivesse investido R$ 100 ha 12 meses:
Fundo: R$ 114,69
CDB 100% CDI bruto: R$ 114,78
CDB 100% CDI liquido: R$ 112,56
Diferenca vs CDB liquido: +R$ 2,13 (+1,9%)
```

---

## Tradeoffs Aceitos

- Sem `--benchmark`, o fluxo interativo fica mais verboso, mas evita comparacoes erradas.
- `CDI` continua como fallback apenas para execucao nao interativa sem escolha explicita.
- A primeira iteracao pode usar providers diferentes para `CDI`, mercado e `USD`, desde que o comportamento fique consistente no CLI.

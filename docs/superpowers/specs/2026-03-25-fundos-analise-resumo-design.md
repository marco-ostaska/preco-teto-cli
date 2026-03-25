# Design: resumo analitico para fundos-br

Data: 2026-03-25

---

## Contexto

O comando `fundos-br` ja mostra rentabilidade por periodo, consistencia e alerta, mas a leitura ainda exige interpretacao manual. A ideia aqui e adicionar um resumo mais direto sem esconder as metricas existentes.

O objetivo nao e substituir as metricas por opiniao. O objetivo e:
- sintetizar o estado atual do fundo com uma regra mecanica
- traduzir a comparacao com CDI para uma simulacao concreta de R$ 100
- deixar a consistencia mais explicita com percentual

---

## Escopo

Adicionar ao output de `fundos-br`:
- `Analise do Fundo: Excelente/Bom/Fraco/Ruim`
- bloco `Se tivesse investido R$ 100 ha 12 meses`
- percentual explicito em `Consistencia 36m`

Fora de escopo:
- mudar as formulas de retorno
- mudar a regra de consistencia
- mudar a regra de alerta
- adicionar novas janelas para a simulacao alem de 12 meses

---

## Regras

### Analise do Fundo

Resumo mecanico derivado de sinais que ja existem no CLI.

Entradas:
- `% CDI` de 12 meses
- consistencia 36m
- alerta atual

Classificacao:
- `Excelente`: `% CDI 12m >= 100%`, consistencia `Consistente`, alerta `Nenhum`
- `Bom`: `% CDI 12m >= 95%` e alerta diferente de `Critico`
- `Fraco`: `% CDI 12m >= 90%` mas fora de `Bom`, ou consistencia `Inconsistente`
- `Ruim`: `% CDI 12m < 90%` ou alerta `Critico`

Observacao:
- `Critico` domina e puxa o resumo para `Ruim`
- a regra e propositalmente conservadora

### Simulacao de R$ 100 em 12m

Usar a linha de 12 meses ja calculada no CLI.

Valores exibidos:
- Fundo: `100 * (1 + ret_fundo_12m)`
- CDB 100% CDI bruto: `100 * (1 + ret_bench_12m)`
- CDB 100% CDI liquido: `100 * (1 + ret_bench_liq_12m)`
- Diferenca vs CDB liquido:
  - valor absoluto em reais
  - variacao percentual relativa ao CDB liquido

Se 12m nao estiver disponivel:
- exibir `—` nas linhas de simulacao

### Consistencia 36m

Formato atual:
- `(13/28 meses acima CDI)`

Novo formato:
- `(13/28 (46,4%) meses acima CDI)`

O percentual e `acima / total`.

---

## Arquivos Afetados

- Modificar: `src/preco_teto/fundos/cli.py`
  - derivar `analise_fundo`
  - localizar a linha `12m`
  - montar dados da simulacao

- Modificar: `src/preco_teto/fundos/termometro.py`
  - adicionar helper para `analise_fundo`

- Modificar: `src/preco_teto/fundos/output/tabela.py`
  - renderizar bloco de analise
  - renderizar bloco de simulacao
  - atualizar texto de consistencia com percentual

- Modificar: `tests/fundos/test_termometro.py`
  - cobrir a regra da analise

- Modificar: `tests/fundos/test_cli.py`
  - cobrir presenca do novo resumo e simulacao

---

## Output Esperado

```text
Analise do Fundo: Ruim

Se tivesse investido R$ 100 ha 12 meses:
Fundo: R$ 114,69
CDB 100% CDI bruto: R$ 114,78
CDB 100% CDI liquido: R$ 112,56
Diferenca vs CDB liquido: +R$ 2,13 (+1,9%)

Risco
Consistencia 36m: Inconsistente  (13/28 (46,4%) meses acima CDI)
Alerta: Critico
```

---

## Tradeoff Aceito

Esse resumo pode simplificar casos ambigueos, mas ele continua ancorado nas metricas ja visiveis no output. O usuario ainda consegue ver a tabela completa, a consistencia e o alerta logo abaixo.

# Design: Indicador Buffett para Ações US

## Objetivo

Adicionar um segundo indicador textual ao lado do `Termômetro` atual para consultas de ações dos EUA. Esse novo indicador deve representar contexto macro do mercado americano, não avaliação específica do ativo consultado.

## Escopo

Incluído:
- Exibir `Indicador Buffett US` em consultas de ações US.
- Calcular a razão `market cap proxy / GDP nominal` dos EUA.
- Classificar o resultado com a régua definida pelo usuário.
- Exibir o percentual calculado e a data/período de referência usados na conta.

Excluído:
- Ações BR.
- FIIs.
- ETFs.
- Qualquer tentativa de aplicar o indicador a um ativo individual.

## Definição do Indicador

### Fórmula

`indicador_buffett_us = market_cap_total_proxy_us / pib_nominal_us * 100`

### Fontes

- `market_cap_total_proxy_us`: série `NCBEILQ027S` no FRED, originada do `Board of Governors of the Federal Reserve System (US)`, descrita como `Nonfinancial Corporate Business; Corporate Equities; Liability, Level`.
- `pib_nominal_us`: série `GDP` no FRED, originada do `U.S. Bureau of Economic Analysis (BEA)`.

### Motivo da escolha

Não foi encontrada, nesta etapa, uma fonte pública atual e simples de integrar para `total listed market cap` dos EUA com cobertura adequada para o indicador. A série `NCBEILQ027S` é uma proxy institucional forte, trimestral e facilmente consumível. O design deve deixar explícito que se trata de uma proxy, não da versão canônica perfeita do indicador.

## Classificação

Aplicar a régua abaixo sobre o percentual calculado:

- `< 75%`: `Mercado barato`
- `>= 75% e < 100%`: `Preço justo`
- `>= 100% e < 120%`: `Ficando caro`
- `>= 120%`: `Caro/Bolha`

## Alinhamento temporal

As duas séries devem ser comparadas no mesmo trimestre mais recente disponível em comum.

Regra:
- buscar a observação trimestral mais recente de `market_cap_total_proxy_us`;
- buscar a observação trimestral de `GDP` para o mesmo período;
- se o mesmo período não existir, retroceder para o trimestre comum mais recente.

Isso evita misturar um market cap de um trimestre com um PIB de outro.

## Formato de saída

O indicador deve aparecer junto do bloco de contexto já existente para ações US.

Exemplo:

`Fed Funds: 4.75%   CPI: 2.9%   Termômetro: Neutro   Buffett US: Caro/Bolha (230.3%, ref. Q3 2025)`

## Arquitetura

### Serviço de referência macro US

Adicionar ao fluxo de referências um ponto de obtenção das duas séries trimestrais usadas no indicador:
- market cap proxy US
- GDP nominal US

Esse serviço deve encapsular:
- leitura das séries;
- seleção do trimestre comum;
- retorno do valor percentual calculado;
- retorno do rótulo qualitativo;
- retorno da referência temporal usada.

### Função de domínio

Adicionar uma função de domínio dedicada ao indicador, separando:
- cálculo do percentual;
- classificação qualitativa.

Isso evita acoplar a regra à CLI ou à camada de renderização.

### Renderização

Somente a saída de ações US deve receber o novo texto.

Nenhum renderer de FII, ETF ou ações BR deve exibir esse indicador nesta etapa.

## Tratamento de erro

Se qualquer série estiver indisponível:
- não quebrar a consulta do ativo;
- omitir o `Buffett US`;
- manter o restante da saída intacto.

Se houver dados mas não existir trimestre comum:
- omitir o indicador.

## Testes

Cobrir pelo menos:
- cálculo correto do percentual;
- classificação em cada faixa;
- alinhamento por trimestre comum mais recente;
- omissão do indicador quando faltar dado;
- exibição apenas para ações US.

## Exemplo validado nesta fase de design

Simulação validada durante a pesquisa:

- `NCBEILQ027S`, `Q3 2025`: `71,631,310` milhões USD
- `GDP`, `Q3 2025`: `31,098,027` milhões USD
- razão: `230.3%`
- classificação: `Caro/Bolha`

## Riscos e limites

- A série de market cap é uma proxy, não a definição clássica exata do Buffett Indicator.
- A atualização é trimestral, então o indicador não será sensível a movimentos diários de mercado.
- O rótulo deve ser apresentado como contexto macro, não como sinal de compra/venda do ativo consultado.

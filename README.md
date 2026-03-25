# preco-teto

CLI para consultar cotacao, referencias e comparativos de acoes, FIIs e fundos brasileiros.

## Instalacao

```bash
git clone <repo>
cd preco-teto
uv sync
```

## Uso

```bash
# Acoes e FIIs
uv run preco-teto VALE3
uv run preco-teto AAPL
uv run preco-teto HGLG11
uv run preco-teto indices

# Saida alternativa
uv run preco-teto VALE3 --json
uv run preco-teto VALE3 --plain

# Fundos por CNPJ
uv run fundos-br 26.199.519/0001-34
uv run fundos-br 37.306.536/0001-40 --benchmark IVV
```

## Testes

```bash
uv run pytest tests/ -q
```

## Aviso

Este projeto foi feito para uso pessoal. Ele consome dados de terceiros e pode conter erros, atrasos, indisponibilidades ou mudancas nas fontes. Nenhuma informacao aqui constitui recomendacao financeira, e nao ha qualquer responsabilizacao por decisoes, perdas ou danos decorrentes do uso da ferramenta.

## Licenca

MIT. Veja [LICENSE](LICENSE).

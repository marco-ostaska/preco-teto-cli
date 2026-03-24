# preco-teto

CLI para cotação e preços teto de ações (BR/US) e FIIs.

## Instalação

```bash
git clone <repo>
cd radar-cli
uv sync
```

## Uso

```bash
uv run preco-teto VALE3      # ação BR
uv run preco-teto AAPL       # ação US
uv run preco-teto HGLG11     # FII (detectado automaticamente)
uv run preco-teto indices    # CDI e IPCA atuais

# Flags de output
uv run preco-teto VALE3 --json
uv run preco-teto VALE3 --plain
```

## Testes

```bash
uv run pytest tests/ -v
```

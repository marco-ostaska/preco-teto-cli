# radar-cli

CLI para cotação e preços teto de ações (BR/US) e FIIs.

## Instalação

```bash
git clone <repo>
cd radar-cli
uv sync
```

## Uso

```bash
uv run radar acao VALE3
uv run radar acao AAPL
uv run radar fii HGLG11
uv run radar indices

# Flags de output
uv run radar acao VALE3 --json
uv run radar acao VALE3 --plain
```

## Testes

```bash
uv run pytest tests/ -v
```

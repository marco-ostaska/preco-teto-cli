# preco-teto v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar o CLI `radar` para `preco-teto`: renomear pacote, simplificar interface, corrigir nomenclatura CDI, remover juro futuro, hardcodar índices US, e melhorar `teto_por_dy` com média histórica de dividendos.

**Architecture:** Renomear `src/radar/` → `src/preco_teto/`, atualizar entry point, remover `tesouro.py`, simplificar CLI para aceitar ticker direto sem subcomando `acao`, e adicionar lógica de média histórica de dividendos em `acao.py`.

**Tech Stack:** Python ≥3.11, uv, typer, rich, yfinance, pandas, scipy, beautifulsoup4, pytest, pytest-mock

**Spec:** `docs/superpowers/specs/2026-03-24-preco-teto-v2-design.md`

---

## Arquivo map

| Ação | Arquivo |
|------|---------|
| Renomear dir | `src/radar/` → `src/preco_teto/` |
| Modificar | `pyproject.toml` |
| Modificar | `src/preco_teto/services/banco_central.py` |
| Deletar | `src/preco_teto/services/tesouro.py` |
| Modificar | `src/preco_teto/services/referencia.py` |
| Modificar | `src/preco_teto/services/acao.py` |
| Modificar | `src/preco_teto/cli.py` |
| Modificar | `src/preco_teto/output/tabela.py` |
| Modificar | `src/preco_teto/output/plain.py` |
| Modificar | `src/preco_teto/output/json_out.py` |
| Modificar | `tests/conftest.py` |
| Modificar | `tests/test_referencia.py` |
| Modificar | `tests/test_acao.py` |
| Modificar | `tests/test_formulas.py` |

---

## Task 1: Renomear pacote e atualizar pyproject.toml

**Files:**
- Rename: `src/radar/` → `src/preco_teto/`
- Modify: `pyproject.toml`

- [ ] **Step 1: Renomear o diretório do pacote**

```bash
cd ~/git-personal/marco-ostaska/radar-cli
mv src/radar src/preco_teto
```

- [ ] **Step 2: Atualizar pyproject.toml**

Substituir conteúdo completo:

```toml
[project]
name = "preco-teto"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = [
    "typer",
    "rich",
    "yfinance",
    "pandas",
    "scipy",
    "requests",
    "beautifulsoup4",
]

[project.scripts]
preco-teto = "preco_teto.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/preco_teto"]

[dependency-groups]
dev = ["pytest", "pytest-mock"]

[tool.pytest.ini_options]
pythonpath = ["src"]
```

- [ ] **Step 3: Atualizar todos os imports internos de `radar` para `preco_teto`**

```bash
cd ~/git-personal/marco-ostaska/radar-cli
grep -rl "from radar" src/ tests/ | xargs sed -i 's/from radar/from preco_teto/g'
grep -rl "import radar" src/ tests/ | xargs sed -i 's/import radar/import preco_teto/g'
```

- [ ] **Step 4: Reinstalar o pacote**

```bash
uv sync
```

- [ ] **Step 5: Verificar que os testes ainda passam (vão falhar alguns por tesouro — ok por ora)**

```bash
uv run pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: rename package radar -> preco_teto, update entry point"
```

---

## Task 2: Remover juro futuro e renomear selic → cdi

**Files:**
- Delete: `src/preco_teto/services/tesouro.py`
- Modify: `src/preco_teto/services/banco_central.py`
- Modify: `src/preco_teto/services/referencia.py`
- Modify: `tests/test_referencia.py`

- [ ] **Step 1: Escrever testes novos para CDI e IndicesBR sem juro_futuro**

Substituir `tests/test_referencia.py` completo:

```python
import pytest
from unittest.mock import patch, MagicMock
import requests

BCB_CDI_RESPONSE = [
    {"data": "01/01/2024", "valor": "0.0452"},
    {"data": "02/01/2024", "valor": "0.0452"},
]

BCB_IPCA_RESPONSE = [
    {"data": "01/01/2024", "valor": "0.38"},
    {"data": "01/02/2024", "valor": "0.41"},
]


def mock_get(url, *args, **kwargs):
    m = MagicMock()
    if "bcb.gov.br" in url and "11" in url:
        m.json.return_value = BCB_CDI_RESPONSE
        m.raise_for_status = MagicMock()
    elif "bcb.gov.br" in url and "10844" in url:
        m.json.return_value = BCB_IPCA_RESPONSE
        m.raise_for_status = MagicMock()
    return m


@patch("requests.get", side_effect=mock_get)
def test_fetch_cdi_returns_float(mock):
    from preco_teto.services.banco_central import fetch_cdi
    result = fetch_cdi()
    assert isinstance(result, float)
    assert result > 0


@patch("requests.get", side_effect=mock_get)
def test_fetch_ipca_returns_float(mock):
    from preco_teto.services.banco_central import fetch_ipca
    result = fetch_ipca()
    assert isinstance(result, float)
    assert result > 0


@patch("requests.get", side_effect=lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError()))
def test_fetch_cdi_returns_none_on_error(mock):
    from preco_teto.services.banco_central import fetch_cdi
    result = fetch_cdi()
    assert result is None


@patch("preco_teto.services.banco_central.fetch_cdi", return_value=13.75)
@patch("preco_teto.services.banco_central.fetch_ipca", return_value=4.80)
def test_indices_br(mock_ipca, mock_cdi):
    from preco_teto.services.referencia import IndicesBR, fetch_indices_br
    idx = fetch_indices_br()
    assert isinstance(idx, IndicesBR)
    assert idx.cdi == 13.75
    assert idx.ipca == 4.80
    assert not hasattr(idx, "juro_futuro")
    assert idx.melhor_indice == pytest.approx(max(13.75 * 0.85, 4.80 + 2.0), rel=1e-3)


def test_indices_us_hardcoded():
    from preco_teto.services.referencia import IndicesUS, fetch_indices_us
    idx = fetch_indices_us()
    assert isinstance(idx, IndicesUS)
    assert idx.fed_funds > 0
    assert idx.cpi > 0
```

- [ ] **Step 2: Rodar testes novos — devem falhar**

```bash
uv run pytest tests/test_referencia.py -v
```

Expected: FAIL — `fetch_cdi` não existe ainda.

- [ ] **Step 3: Atualizar banco_central.py — renomear fetch_selic → fetch_cdi**

```python
from datetime import datetime
import requests
import pandas as pd


def _bcb_url(codigo_serie: int, anos: int = 1) -> str:
    ontem = datetime.now() - pd.Timedelta(days=1)
    inicio = f"{ontem.day}/{ontem.month}/{ontem.year - anos}"
    fim = f"{ontem.day}/{ontem.month}/{ontem.year}"
    return (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados"
        f"?formato=json&dataInicial={inicio}&dataFinal={fim}"
    )


def fetch_cdi() -> float | None:
    """Taxa CDI anualizada atual (última observação, série 11 BCB). Retorna % (ex: 14.65)."""
    try:
        resp = requests.get(_bcb_url(11, anos=1), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        taxa_diaria = float(data[-1]["valor"].replace(",", ".")) / 100
        return round(((1 + taxa_diaria) ** 252 - 1) * 100, 2)
    except Exception:
        return None


def fetch_ipca() -> float | None:
    """IPCA acumulado 12 meses (soma das últimas 12 leituras mensais). Retorna %."""
    try:
        resp = requests.get(_bcb_url(10844, anos=2), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ultimas_12 = [float(d["valor"].replace(",", ".")) for d in data[-12:]]
        return round(sum(ultimas_12), 2)
    except Exception:
        return None


def melhor_indice_br(cdi: float | None, ipca: float | None) -> float | None:
    """Retorna max(cdi_liquido, ipca_ganho_real). Usado em teto_por_dy e teto_bazin BR."""
    try:
        cdi_liq = cdi * 0.85 if cdi else None
        ipca_real = (ipca + 2.0) if ipca else None
        candidates = [x for x in [cdi_liq, ipca_real] if x is not None]
        return max(candidates) if candidates else None
    except Exception:
        return None
```

- [ ] **Step 4: Deletar tesouro.py**

```bash
rm src/preco_teto/services/tesouro.py
```

- [ ] **Step 5: Atualizar referencia.py — remover juro_futuro, hardcodar US, renomear campos**

```python
from dataclasses import dataclass
from preco_teto.services.banco_central import fetch_cdi, fetch_ipca, melhor_indice_br

FED_FUNDS_US = 5.25  # atualizar manualmente quando Fed mudar
CPI_US = 3.1         # atualizar manualmente quando necessário


@dataclass
class IndicesBR:
    cdi: float | None
    ipca: float | None
    melhor_indice: float | None  # max(cdi * 0.85, ipca + 2.0)


@dataclass
class IndicesUS:
    fed_funds: float
    cpi: float


def fetch_indices_br() -> IndicesBR:
    cdi = fetch_cdi()
    ipca = fetch_ipca()
    melhor = melhor_indice_br(cdi, ipca)
    return IndicesBR(cdi=cdi, ipca=ipca, melhor_indice=melhor)


def fetch_indices_us() -> IndicesUS:
    return IndicesUS(fed_funds=FED_FUNDS_US, cpi=CPI_US)
```

- [ ] **Step 6: Rodar testes de referencia — devem passar**

```bash
uv run pytest tests/test_referencia.py -v
```

Expected: 5 testes PASS.

- [ ] **Step 7: Commit**

```bash
git add src/preco_teto/services/banco_central.py \
        src/preco_teto/services/referencia.py \
        tests/test_referencia.py
git rm src/preco_teto/services/tesouro.py
git commit -m "refactor: rename selic->cdi, remove juro_futuro and tesouro.py, hardcode US rates"
```

---

## Task 3: Atualizar acao.py — dy_medio histórico e detecção de sem-dados

**Files:**
- Modify: `src/preco_teto/services/acao.py`
- Modify: `tests/test_acao.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Adicionar fixture de dividendos históricos com 3 anos em conftest.py**

Adicionar ao final de `tests/conftest.py`:

```python
@pytest.fixture
def mock_dividends_3y():
    """Dividendos mensais cobrindo 3 anos completos (2021, 2022, 2023)."""
    import numpy as np
    dates = pd.date_range("2021-01-15", periods=36, freq="MS")
    # 2021: ~1.00/mês, 2022: ~1.20/mês, 2023: ~1.40/mês
    vals = (
        [1.00] * 12 +  # 2021: total 12.00
        [1.20] * 12 +  # 2022: total 14.40
        [1.40] * 12    # 2023: total 16.80
    )
    return pd.Series(vals, index=dates)


@pytest.fixture
def mock_dividends_1y():
    """Dividendos cobrindo apenas 1 ano completo (2023)."""
    dates = pd.date_range("2023-01-15", periods=12, freq="MS")
    vals = [1.40] * 12  # 2023: total 16.80
    return pd.Series(vals, index=dates)


@pytest.fixture
def mock_dividends_empty():
    """Sem histórico de dividendos."""
    import pandas as pd
    return pd.Series([], dtype=float)
```

- [ ] **Step 2: Escrever testes novos para acao.py**

Adicionar ao final de `tests/test_acao.py`:

```python
def test_dy_medio_3y(mock_dividends_3y, mock_yf_info_br, mock_adj_close, mocker):
    """dy_medio deve usar média dos 3 anos completos mais recentes."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = None
    mock_ticker.dividends = mock_dividends_3y
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    # média de 12.00, 14.40, 16.80 = 14.40
    assert data.dividendo_medio == pytest.approx(14.40, rel=1e-2)


def test_dy_medio_fallback_sem_historico(mock_dividends_empty, mock_yf_info_br, mock_adj_close, mocker):
    """Sem histórico, dy_medio usa dividendRate do info."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br  # dividendRate = 3.60
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = None
    mock_ticker.dividends = mock_dividends_empty
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    assert data.dividendo_medio == pytest.approx(3.60, rel=1e-2)


def test_todos_tetos_none_sem_dados(mocker):
    """Ativo sem dados suficientes retorna dividendo_medio None."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {}
    mock_ticker.history.return_value = __import__("pandas").DataFrame()
    mock_ticker.income_stmt = None
    mock_ticker.dividends = __import__("pandas").Series([], dtype=float)
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("IAU")
    assert data.dividendo_medio is None
    assert data.cotacao is None
```

- [ ] **Step 3: Rodar testes novos — devem falhar**

```bash
uv run pytest tests/test_acao.py::test_dy_medio_3y tests/test_acao.py::test_dy_medio_fallback_sem_historico tests/test_acao.py::test_todos_tetos_none_sem_dados -v
```

Expected: FAIL — `dividendo_medio` não existe ainda.

- [ ] **Step 4: Atualizar acao.py — adicionar dividendo_medio**

```python
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import yfinance as yf
from scipy.stats import trim_mean


def _is_br(ticker: str) -> bool:
    return ticker[-1].isdigit()


def _get_cotacao(info: dict, history: pd.DataFrame) -> float | None:
    if "currentPrice" in info:
        return info["currentPrice"]
    if "previousClose" in info:
        return info["previousClose"]
    if "regularMarketPrice" in info:
        return info["regularMarketPrice"]
    try:
        return float(history["Close"].iloc[-1])
    except Exception:
        return None


def _year_prices(history: pd.DataFrame) -> dict[int, float]:
    """trim_mean(10%) dos últimos 30 pregões de cada ano no histórico."""
    result = {}
    if history.empty:
        return result
    history = history.copy()
    history.index = pd.to_datetime(history.index)
    for year in history.index.year.unique():
        mask = history.index.year == year
        vals = history.loc[mask, "Close"].tail(30).values
        if len(vals) > 0:
            result[int(year)] = float(trim_mean(vals, proportiontocut=0.1))
    return result


def _dividendo_medio(dividends: pd.Series, dividend_rate: float | None) -> float | None:
    """
    Calcula dividendo anual médio dos últimos 3 anos completos.
    Fallback: dividend_rate do yfinance se sem histórico completo.
    """
    try:
        if dividends is None or dividends.empty:
            return dividend_rate or None
        dividends = dividends.copy()
        dividends.index = pd.to_datetime(dividends.index)
        ano_atual = datetime.now().year
        por_ano = dividends.groupby(dividends.index.year).sum()
        anos_completos = por_ano[por_ano.index < ano_atual]
        if anos_completos.empty:
            return dividend_rate or None
        ultimos = anos_completos.tail(3)
        return round(float(ultimos.mean()), 4)
    except Exception:
        return dividend_rate or None


@dataclass
class AcaoData:
    ticker: str
    is_br: bool
    cotacao: float | None
    dividend_rate: float | None
    dividendo_medio: float | None   # média anual 3 anos (ou fallback dividend_rate)
    lpa: float | None
    vpa: float | None
    free_cashflow: float | None
    shares_outstanding: float | None
    beta: float | None
    earnings_growth: float | None
    revenue_growth: float | None
    income_net: pd.Series = field(repr=False, default=None)
    year_prices: dict = field(repr=False, default_factory=dict)
    previous_close: float | None = None


def fetch_acao(ticker: str) -> AcaoData:
    ticker = ticker.upper()
    is_br = _is_br(ticker)
    yf_ticker = f"{ticker}.SA" if is_br else ticker

    t = yf.Ticker(yf_ticker)
    info = t.info or {}
    history = t.history(period="5y")

    cotacao = _get_cotacao(info, history)
    year_px = _year_prices(history)

    income_net = None
    try:
        stmt = t.income_stmt
        if stmt is not None and "Net Income" in stmt.index:
            income_net = stmt.loc["Net Income"].dropna()
    except Exception:
        pass

    dividends = None
    try:
        dividends = t.dividends
    except Exception:
        pass

    dividend_rate = info.get("dividendRate")
    div_medio = _dividendo_medio(dividends, dividend_rate)

    return AcaoData(
        ticker=ticker,
        is_br=is_br,
        cotacao=cotacao,
        dividend_rate=dividend_rate,
        dividendo_medio=div_medio,
        lpa=info.get("trailingEps"),
        vpa=info.get("bookValue"),
        free_cashflow=info.get("freeCashflow"),
        shares_outstanding=info.get("sharesOutstanding"),
        beta=info.get("beta"),
        earnings_growth=info.get("earningsGrowth") or info.get("revenueGrowth"),
        revenue_growth=info.get("revenueGrowth"),
        income_net=income_net,
        year_prices=year_px,
        previous_close=info.get("previousClose") or info.get("regularMarketPreviousClose"),
    )
```

- [ ] **Step 5: Rodar todos os testes de acao — devem passar**

```bash
uv run pytest tests/test_acao.py -v
```

Expected: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add src/preco_teto/services/acao.py tests/test_acao.py tests/conftest.py
git commit -m "feat: add dividendo_medio com média histórica 3 anos e fallback"
```

---

## Task 4: Atualizar formulas.py — teto_por_dy usa dividendo_medio

**Files:**
- Modify: `src/preco_teto/formulas.py`
- Modify: `tests/test_formulas.py`

- [ ] **Step 1: Escrever testes para novo teto_por_dy**

Adicionar ao final de `tests/test_formulas.py`:

```python
def test_teto_por_dy_usa_dividendo_medio():
    """teto_por_dy agora recebe dividendo_anual direto (não cotacao * dy)."""
    # dividendo_medio = 14.40, indice_base = 11.69%
    resultado = teto_por_dy(14.40, 11.69)
    assert resultado == pytest.approx(14.40 / 0.1169, rel=1e-2)


def test_teto_por_dy_none_se_dividendo_none():
    assert teto_por_dy(None, 11.69) is None


def test_teto_por_dy_none_se_taxa_zero():
    assert teto_por_dy(14.40, 0) is None
```

- [ ] **Step 2: Rodar testes novos — devem falhar**

```bash
uv run pytest tests/test_formulas.py::test_teto_por_dy_usa_dividendo_medio -v
```

Expected: FAIL — assinatura de `teto_por_dy` ainda usa `cotacao, dy_estimado, indice_base`.

- [ ] **Step 3: Atualizar assinatura de teto_por_dy em formulas.py**

Substituir a função `teto_por_dy`:

```python
def teto_por_dy(dividendo_anual: float | None, indice_base: float) -> float | None:
    """
    teto = dividendo_anual_medio / (indice_base / 100)
    dividendo_anual: média dos últimos 1-3 anos de dividendos pagos (R$ ou $)
    indice_base: melhor_indice BR ou FED_FUNDS_US, em % (ex: 11.69)
    """
    try:
        if not dividendo_anual or not indice_base:
            return None
        return round(dividendo_anual / (indice_base / 100), 2)
    except Exception:
        return None
```

- [ ] **Step 4: Rodar todos os testes de formulas — devem passar**

```bash
uv run pytest tests/test_formulas.py -v
```

Expected: todos PASS (os testes antigos de `teto_por_dy` usavam a assinatura velha — devem ser removidos/atualizados se falharem).

> **Nota:** Se testes antigos de `teto_por_dy` falharem por assinatura, remova-os — foram substituídos pelos novos.

- [ ] **Step 5: Commit**

```bash
git add src/preco_teto/formulas.py tests/test_formulas.py
git commit -m "refactor: teto_por_dy recebe dividendo_anual direto em vez de cotacao*dy"
```

---

## Task 5: Atualizar CLI — ticker direto, detecção de tipo, mensagem sem dados

**Files:**
- Modify: `src/preco_teto/cli.py`

- [ ] **Step 1: Reescrever cli.py**

```python
from typing import Annotated
import typer

from preco_teto.services.acao import fetch_acao
from preco_teto.services.fii import fetch_fii
from preco_teto.services.referencia import fetch_indices_br, fetch_indices_us
from preco_teto.formulas import (
    teto_por_lucro, teto_por_dy, teto_bazin, teto_graham, teto_dcf
)

app = typer.Typer(help="Preço teto de ativos — ações BR/US e FIIs")


def _get_renderer(json_flag: bool, plain_flag: bool):
    if json_flag:
        from preco_teto.output import json_out
        return json_out
    if plain_flag:
        from preco_teto.output import plain
        return plain
    from preco_teto.output import tabela
    return tabela


def _todos_none(tetos: dict) -> bool:
    return all(v is None for v in tetos.values())


def _is_fii(ticker: str) -> bool:
    return ticker.endswith("11")


@app.command()
def main(
    ticker: str,
    json: Annotated[bool, typer.Option("--json")] = False,
    plain: Annotated[bool, typer.Option("--plain")] = False,
):
    """Consulta preço teto de um ativo (ação BR/US ou FII). Use 'indices' para ver CDI e IPCA."""
    ticker = ticker.upper()

    if ticker == "INDICES":
        indices(json=json, plain=plain)
        return

    renderer = _get_renderer(json, plain)

    # Tenta como FII se termina em 11
    if _is_fii(ticker):
        try:
            data = fetch_fii(ticker)
            idx = fetch_indices_br()
            indice_base = idx.melhor_indice
            tetos = {
                "teto_por_dy": teto_por_dy(
                    (data.dividend_yield / 100 * data.cotacao) if data.dividend_yield and data.cotacao else None,
                    indice_base,
                ) if data.cotacao else None,
                "vpa": data.vpa,
            }
            if _todos_none(tetos):
                typer.echo(f"{ticker} — cálculo de preço teto não disponível para este ativo.")
                return
            renderer.render_fii(data.ticker, data.cotacao, tetos, idx)
            return
        except Exception:
            pass  # fallback para ação BR

    # Ação BR ou US
    data = fetch_acao(ticker)
    if data.is_br:
        idx = fetch_indices_br()
        indice_base = idx.melhor_indice
        taxa_livre = idx.cdi
        premio = 5.5
        inflacao = idx.ipca or 4.8
    else:
        idx = fetch_indices_us()
        indice_base = idx.fed_funds
        taxa_livre = idx.fed_funds
        premio = 5.0
        inflacao = idx.cpi

    tetos = {
        "teto_por_lucro": teto_por_lucro(data.income_net, data.year_prices, data.previous_close or data.cotacao or 0),
        "teto_por_dy": teto_por_dy(data.dividendo_medio, indice_base) if data.dividendo_medio else None,
        "teto_bazin": teto_bazin(data.dividend_rate, indice_base),
        "teto_graham": teto_graham(data.lpa, data.vpa),
        "teto_dcf": teto_dcf(
            data.free_cashflow, data.shares_outstanding, data.beta,
            data.earnings_growth, taxa_livre or 0, premio, inflacao
        ),
    }

    if _todos_none(tetos):
        typer.echo(f"{ticker} — cálculo de preço teto não disponível para este ativo.")
        return

    renderer.render_acao(data.ticker, data.cotacao, data.is_br, tetos, idx)


def indices(
    json: Annotated[bool, typer.Option("--json")] = False,
    plain: Annotated[bool, typer.Option("--plain")] = False,
):
    """Exibe índices de referência BR (CDI e IPCA)."""
    br = fetch_indices_br()
    renderer = _get_renderer(json, plain)
    renderer.render_indices(br)


# Expor indices como subcomando também
app.command(name="indices")(indices)
```

- [ ] **Step 2: Verificar que o CLI sobe sem erro**

```bash
uv run preco-teto --help
```

Expected: mostra help com comando `main` e `indices`.

- [ ] **Step 3: Commit**

```bash
git add src/preco_teto/cli.py
git commit -m "feat: new CLI interface — ticker direto, detecção FII, mensagem sem dados"
```

---

## Task 6: Atualizar outputs — renomear CDI, remover juro_futuro e índices US

**Files:**
- Modify: `src/preco_teto/output/tabela.py`
- Modify: `src/preco_teto/output/plain.py`
- Modify: `src/preco_teto/output/json_out.py`

- [ ] **Step 1: Atualizar tabela.py**

```python
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def _teto_row(label: str, valor: float | None, cotacao: float | None) -> tuple:
    if valor is None:
        return label, "—", ""
    fmt = f"R$ {valor:.2f}" if cotacao and cotacao > 1 else f"$ {valor:.2f}"
    if cotacao and valor >= cotacao:
        return label, f"[green]{fmt}[/green]", "[green]✓[/green]"
    return label, f"[red]{fmt}[/red]", "[red]✗[/red]"


def render_acao(ticker, cotacao, is_br, tetos: dict, indices):
    moeda = "R$" if is_br else "$"
    t = Table(title=f"{ticker}  {moeda} {cotacao:.2f}", box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("")

    labels = {
        "teto_por_lucro": "Teto por Lucro  (heurística)",
        "teto_por_dy":    "Teto por DY     (DY médio 3a)",
        "teto_bazin":     f"Teto Bazin      ({'CDI dinâmico' if is_br else 'Fed Funds dinâmico'})",
        "teto_graham":    "Teto Graham     (LPA×VPA)",
        "teto_dcf":       "Teto DCF        (FCL/CAPM)",
    }
    for key, label in labels.items():
        t.add_row(*_teto_row(label, tetos.get(key), cotacao))

    console.print(t)

    if is_br:
        console.print(f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%")
    else:
        console.print(f"Fed Funds: {indices.fed_funds}%   CPI: {indices.cpi}%")


def render_fii(ticker, cotacao, tetos: dict, indices):
    t = Table(title=f"{ticker}  R$ {cotacao:.2f}", box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("")
    t.add_row(*_teto_row("Teto por DY  (heurística)", tetos.get("teto_por_dy"), cotacao))
    t.add_row(*_teto_row("VPA", tetos.get("vpa"), cotacao))
    console.print(t)
    console.print(f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%")


def render_indices(br):
    t = Table(title="Índices de Referência BR", box=box.SIMPLE_HEAVY)
    t.add_column("Índice")
    t.add_column("Valor", justify="right")
    t.add_row("CDI", f"{br.cdi}%" if br.cdi else "—")
    t.add_row("IPCA (12m)", f"{br.ipca}%" if br.ipca else "—")
    console.print(t)
```

- [ ] **Step 2: Atualizar plain.py**

```python
def _fmt(valor, is_br):
    if valor is None:
        return "—"
    m = "R$" if is_br else "$"
    return f"{m} {valor:.2f}"


def render_acao(ticker, cotacao, is_br, tetos, indices):
    moeda = "R$" if is_br else "$"
    print(f"{ticker}  {moeda} {cotacao:.2f}")
    print("-" * 46)
    for key, label in [
        ("teto_por_lucro", "Teto por Lucro"),
        ("teto_por_dy",    "Teto por DY"),
        ("teto_bazin",     "Teto Bazin"),
        ("teto_graham",    "Teto Graham"),
        ("teto_dcf",       "Teto DCF"),
    ]:
        v = tetos.get(key)
        mark = "OK" if (v and cotacao and v >= cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, is_br):>12}  {mark}")
    print("-" * 46)
    if is_br:
        print(f"CDI: {indices.cdi}%  IPCA: {indices.ipca}%")
    else:
        print(f"Fed Funds: {indices.fed_funds}%  CPI: {indices.cpi}%")


def render_fii(ticker, cotacao, tetos, indices):
    print(f"{ticker}  R$ {cotacao:.2f}")
    print("-" * 46)
    for key, label in [("teto_por_dy", "Teto por DY"), ("vpa", "VPA")]:
        v = tetos.get(key)
        mark = "OK" if (v and cotacao and v >= cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, True):>12}  {mark}")


def render_indices(br):
    print(f"CDI:   {br.cdi}%")
    print(f"IPCA:  {br.ipca}%")
```

- [ ] **Step 3: Atualizar json_out.py**

```python
import json


def render_acao(ticker, cotacao, is_br, tetos, indices):
    print(json.dumps({
        "ticker": ticker,
        "cotacao": cotacao,
        "is_br": is_br,
        "tetos": tetos,
        "indices": {
            "cdi": getattr(indices, "cdi", None),
            "ipca": getattr(indices, "ipca", None),
        },
    }, indent=2, ensure_ascii=False))


def render_fii(ticker, cotacao, tetos, indices):
    print(json.dumps({
        "ticker": ticker,
        "cotacao": cotacao,
        "tetos": tetos,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
    }, indent=2, ensure_ascii=False))


def render_indices(br):
    print(json.dumps({
        "br": {"cdi": br.cdi, "ipca": br.ipca},
    }, indent=2))
```

- [ ] **Step 4: Rodar todos os testes**

```bash
uv run pytest tests/ -v
```

Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add src/preco_teto/output/
git commit -m "refactor: update outputs — CDI label, remove juro_futuro, remove US indices display"
```

---

## Task 7: Smoke test e verificação final

**Files:** nenhum

- [ ] **Step 1: Rodar suite completa de testes**

```bash
cd ~/git-personal/marco-ostaska/radar-cli
uv run pytest tests/ -v
```

Expected: todos PASS, zero falhas.

- [ ] **Step 2: Verificar help do CLI**

```bash
uv run preco-teto --help
uv run preco-teto indices --help
```

- [ ] **Step 3: Smoke test com ativo real (opcional — requer internet)**

```bash
uv run preco-teto indices --plain
uv run preco-teto VALE3 --plain
uv run preco-teto HGLG11 --plain
uv run preco-teto IAU --plain   # deve mostrar "cálculo não disponível"
```

- [ ] **Step 4: Commit final se ajustes necessários**

```bash
git add -A
git commit -m "chore: final adjustments after smoke test"
```

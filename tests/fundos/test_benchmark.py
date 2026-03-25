import pytest
import pandas as pd
from unittest.mock import patch
from preco_teto.fundos.services.benchmark import (
    fetch_cdi_historico,
    fetch_benchmark_historico,
    normalize_benchmark,
)

BCB_RESPONSE = [
    {"data": "02/01/2024", "valor": "0,052319"},
    {"data": "03/01/2024", "valor": "0,052319"},
]


def test_fetch_cdi_historico_retorna_dataframe():
    with patch("preco_teto.fundos.services.benchmark.requests.get") as mock_get:
        mock_get.return_value.json.return_value = BCB_RESPONSE
        mock_get.return_value.raise_for_status = lambda: None
        from datetime import date
        df = fetch_cdi_historico(date(2024, 1, 1), date(2024, 1, 3))
    assert list(df.columns) == ["data", "taxa"]
    assert len(df) == 2
    assert df["taxa"].iloc[0] == pytest.approx(0.052319)


def test_normalize_benchmark_aceita_suportados():
    assert normalize_benchmark("cdi") == "CDI"
    assert normalize_benchmark("IVV") == "IVV"
    assert normalize_benchmark("btc") == "BTC"


def test_normalize_benchmark_rejeita_nao_suportado():
    assert normalize_benchmark("ouro") is None


def test_fetch_benchmark_historico_ivv_usa_serie_de_mercado():
    hist = pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )
    with patch("preco_teto.fundos.services.benchmark.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = hist
        from datetime import date
        df = fetch_benchmark_historico("IVV", date(2024, 1, 1), date(2024, 1, 3))
    assert list(df.columns) == ["data", "valor"]
    assert df["valor"].tolist() == [100.0, 101.0]


def test_fetch_benchmark_historico_usd_usa_serie_do_bcb():
    with patch("preco_teto.fundos.services.benchmark.requests.get") as mock_get:
        mock_get.return_value.json.return_value = BCB_RESPONSE
        mock_get.return_value.raise_for_status = lambda: None
        from datetime import date
        df = fetch_benchmark_historico("USD", date(2024, 1, 1), date(2024, 1, 3))
    assert list(df.columns) == ["data", "valor"]
    assert df["valor"].iloc[0] == pytest.approx(0.052319)

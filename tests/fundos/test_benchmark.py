import pytest
import pandas as pd
from unittest.mock import patch
from preco_teto.fundos.services.benchmark import (
    fetch_cdi_historico,
    detectar_benchmark,
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


def test_detectar_benchmark_renda_fixa():
    assert detectar_benchmark("Renda Fixa Referenciado DI") == "CDI"
    assert detectar_benchmark("Renda Fixa Crédito Privado") == "CDI"


def test_detectar_benchmark_multimercado():
    assert detectar_benchmark("Multimercado Macro") == "CDI"
    assert detectar_benchmark("Multimercado Long and Short") == "CDI"


def test_detectar_benchmark_nao_mapeado():
    assert detectar_benchmark("Classe Desconhecida") is None

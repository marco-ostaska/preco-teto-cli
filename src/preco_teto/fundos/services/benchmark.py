from __future__ import annotations
from datetime import date
import requests
import pandas as pd

_BCB_SERIE_12 = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"

# Benchmarks supported in v1: CDI only.
# Ações/Cambial/Crypto are out-of-scope for v1.
_BENCHMARK_MAP = {
    "Renda Fixa": "CDI",
    "Multimercado": "CDI",
}


def detectar_benchmark(classe_anbima: str) -> str | None:
    """Returns benchmark key ('CDI') or None if unmapped."""
    for prefix, benchmark in _BENCHMARK_MAP.items():
        if classe_anbima.startswith(prefix):
            return benchmark
    return None


def fetch_cdi_historico(inicio: date, fim: date) -> pd.DataFrame:
    """
    Returns DataFrame [data (datetime), taxa (float %)] from BCB série 12.
    taxa is the daily DI rate in %, e.g. 0.052319.
    """
    fmt = "%d/%m/%Y"
    url = (
        f"{_BCB_SERIE_12}?formato=json"
        f"&dataInicial={inicio.strftime(fmt)}"
        f"&dataFinal={fim.strftime(fmt)}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["taxa"] = df["valor"].str.replace(",", ".").astype(float)
    return df[["data", "taxa"]].reset_index(drop=True)

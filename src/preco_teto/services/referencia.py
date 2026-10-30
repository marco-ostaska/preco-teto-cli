from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path

import yfinance as yf

from preco_teto.services import banco_central

FED_FUNDS_US = 5.25  # fallback manual quando o T-bill não responde
CPI_US = 3.1         # atualizar manualmente quando necessário
_TBILL_13_SEMANAS = "^IRX"


@dataclass
class IndicesBR:
    cdi: float | None
    ipca: float | None
    melhor_indice: float | None  # max(cdi * 0.85, ipca + 2.0)


@dataclass
class IndicesUS:
    fed_funds: float
    cpi: float


_indices_br_cache_date: date | None = None
_indices_br_cache: IndicesBR | None = None
_INDICES_BR_CACHE_PATH = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "preco-teto"
    / "indices-br.json"
)


def fetch_indices_br() -> IndicesBR:
    global _indices_br_cache_date, _indices_br_cache

    today = date.today()
    if _indices_br_cache_date == today and _indices_br_cache is not None:
        return _indices_br_cache

    try:
        cached = json.loads(_INDICES_BR_CACHE_PATH.read_text())
        # Cache só vale quando os dois índices foram obtidos; valor nulo é retentado.
        if (
            cached.get("date") == today.isoformat()
            and cached.get("cdi") is not None
            and cached.get("ipca") is not None
        ):
            _indices_br_cache_date = today
            _indices_br_cache = IndicesBR(
                cdi=cached.get("cdi"),
                ipca=cached.get("ipca"),
                melhor_indice=cached.get("melhor_indice"),
            )
            return _indices_br_cache
    except (OSError, ValueError, TypeError):
        pass

    cdi = banco_central.fetch_cdi()
    ipca = banco_central.fetch_ipca()
    melhor = banco_central.melhor_indice_br(cdi, ipca)
    if cdi is None or ipca is None:
        # Falha transitória do BCB: não memoriza, para tentar de novo na próxima chamada.
        return IndicesBR(cdi=cdi, ipca=ipca, melhor_indice=melhor)
    _indices_br_cache_date = today
    _indices_br_cache = IndicesBR(cdi=cdi, ipca=ipca, melhor_indice=melhor)
    try:
        _INDICES_BR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _INDICES_BR_CACHE_PATH.write_text(json.dumps({
            "date": today.isoformat(),
            "cdi": cdi,
            "ipca": ipca,
            "melhor_indice": melhor,
        }))
    except OSError:
        pass
    return _indices_br_cache


def fetch_fed_funds() -> float:
    """
    Alvo do Fed via T-bill de 13 semanas (^IRX), que acompanha o front end.
    A constante manual só vale quando o Yahoo não responde.
    """
    try:
        fechamentos = yf.Ticker(_TBILL_13_SEMANAS).history(period="5d")["Close"].dropna()
        if fechamentos.empty:
            return FED_FUNDS_US
        return round(float(fechamentos.iloc[-1]), 2)
    except Exception:
        return FED_FUNDS_US


def fetch_indices_us() -> IndicesUS:
    return IndicesUS(fed_funds=fetch_fed_funds(), cpi=CPI_US)

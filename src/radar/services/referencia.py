from dataclasses import dataclass
import yfinance as yf
from radar.services.banco_central import fetch_selic, fetch_ipca, melhor_indice_br
from radar.services.tesouro import fetch_juro_futuro

CPI_US = 3.1  # hardcoded — FRED API requer chave, fora do escopo


@dataclass
class IndicesBR:
    selic: float | None
    ipca: float | None
    juro_futuro: float | None
    melhor_indice: float | None  # max(selic_liq, ipca_ganho_real)


@dataclass
class IndicesUS:
    taxa_curto: float | None   # TFLO ou BIL
    taxa_longo: float | None   # TLT (informativo)
    cpi: float = CPI_US


def fetch_indices_br() -> IndicesBR:
    selic = fetch_selic()
    ipca = fetch_ipca()
    juro_futuro = fetch_juro_futuro()
    melhor = melhor_indice_br(selic, ipca)
    return IndicesBR(selic=selic, ipca=ipca, juro_futuro=juro_futuro, melhor_indice=melhor)


def _yf_dividend_yield(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).info
        dy = info.get("dividendYield")
        return round(dy * 100, 4) if dy else None
    except Exception:
        return None


def fetch_indices_us() -> IndicesUS:
    taxa_curto = _yf_dividend_yield("TFLO")
    if taxa_curto is None:
        taxa_curto = _yf_dividend_yield("BIL")
    taxa_longo = _yf_dividend_yield("TLT")
    return IndicesUS(taxa_curto=taxa_curto, taxa_longo=taxa_longo)

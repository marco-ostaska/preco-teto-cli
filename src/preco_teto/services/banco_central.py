from datetime import datetime
import time
import requests
import pandas as pd

_TIMEOUT = 15
_TENTATIVAS = 3
_BACKOFF = 0.5


def _bcb_url(codigo_serie: int, anos: int = 1) -> str:
    ontem = datetime.now() - pd.Timedelta(days=1)
    inicio = f"{ontem.day}/{ontem.month}/{ontem.year - anos}"
    fim = f"{ontem.day}/{ontem.month}/{ontem.year}"
    return (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados"
        f"?formato=json&dataInicial={inicio}&dataFinal={fim}"
    )


def _bcb_ultimos_url(codigo_serie: int, ultimos: int) -> str:
    return (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}"
        f"/dados/ultimos/{ultimos}?formato=json"
    )


def _bcb_get(url: str, timeout: int = _TIMEOUT) -> list | None:
    """GET no BCB com retentativas — a API responde com timeouts intermitentes."""
    for tentativa in range(_TENTATIVAS):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            dados = resp.json()
            if dados:
                return dados
        except Exception:
            pass
        if tentativa < _TENTATIVAS - 1:
            time.sleep(_BACKOFF * (2 ** tentativa))
    return None


def fetch_cdi() -> float | None:
    """Taxa CDI anualizada atual (última observação, série 11 BCB). Retorna % (ex: 14.65)."""
    dados = _bcb_get(_bcb_ultimos_url(11, 1))
    if not dados:
        return None
    try:
        taxa_diaria = float(dados[-1]["valor"].replace(",", ".")) / 100
        return round(((1 + taxa_diaria) ** 252 - 1) * 100, 2)
    except Exception:
        return None


def fetch_cdi_daily_series(anos: int = 20) -> pd.Series:
    """Série diária CDI (taxa diária em decimal) indexada por data — para as-of no backtest."""
    dados = _bcb_get(_bcb_url(11, anos=anos), timeout=30)
    if not dados:
        return pd.Series(dtype=float)
    try:
        idx = []
        vals = []
        for row in dados:
            # DD/MM/AAAA
            d, m, y = row["data"].split("/")
            idx.append(pd.Timestamp(year=int(y), month=int(m), day=int(d)))
            vals.append(float(row["valor"].replace(",", ".")) / 100)
        return pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index()
    except Exception:
        return pd.Series(dtype=float)


def cdi_anualizado_asof(cdi_daily: pd.Series, as_of: pd.Timestamp) -> float | None:
    """Última taxa diária ≤ as_of, anualizada 252d → %."""
    if cdi_daily is None or cdi_daily.empty:
        return None
    as_of = pd.Timestamp(as_of).normalize()
    hist = cdi_daily.loc[cdi_daily.index <= as_of]
    if hist.empty:
        return None
    taxa_diaria = float(hist.iloc[-1])
    return round(((1 + taxa_diaria) ** 252 - 1) * 100, 2)


def fetch_ipca() -> float | None:
    """IPCA acumulado 12 meses (soma das últimas 12 leituras mensais). Retorna %."""
    dados = _bcb_get(_bcb_ultimos_url(433, 12))
    if not dados:
        return None
    try:
        ultimas_12 = [float(d["valor"].replace(",", ".")) for d in dados[-12:]]
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

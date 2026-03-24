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

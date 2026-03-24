import requests
from bs4 import BeautifulSoup
import pandas as pd
from dataclasses import dataclass
import yfinance as yf


class FiisComService:
    """Scraping de fiis.com.br — sem Redis."""

    def __init__(self, ticker: str):
        self.ticker = ticker.upper()
        self._dados = self._fetch()
        self._dividends = None  # pode ser substituído em testes

    def _fetch(self) -> dict:
        url = f"https://fiis.com.br/{self.ticker.lower()}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = "utf-8"
            return self._parse(resp.text)
        except Exception:
            return {}

    def _parse(self, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        cotacao = None
        q = soup.find("div", class_="item quotation")
        if q:
            v = q.find("span", class_="value")
            try:
                cotacao = float(v.get_text(strip=True).replace(",", ".")) if v else None
            except Exception:
                pass

        vpa = None
        for box in soup.select(".wrapper.indicators .indicators__box"):
            labels = box.find_all("p")
            if len(labels) > 1 and "Val. Patrimonial p/Cota" in labels[1].get_text():
                try:
                    vpa = float(box.find("b").get_text(strip=True).replace(",", "."))
                except Exception:
                    pass

        dy_html = None
        for box in soup.select(".indicators .indicators__box"):
            ps = box.find_all("p")
            if len(ps) == 2 and "Dividend Yield" in ps[1].get_text():
                try:
                    dy_html = float(ps[0].find("b").get_text(strip=True).replace(",", ".").replace("%", ""))
                except Exception:
                    pass

        dividendos = []
        for bloco in soup.select(".yieldChart__table__bloco--rendimento"):
            linhas = bloco.find_all("div", class_="table__linha")
            if len(linhas) >= 5:
                try:
                    rend = float(linhas[-1].get_text(strip=True).replace("R$", "").replace(",", ".").strip())
                    dividendos.append(rend)
                except Exception:
                    pass

        return {"cotacao": cotacao, "vpa": vpa, "dy_html": dy_html, "dividendos": dividendos}

    @property
    def cotacao(self) -> float | None:
        return self._dados.get("cotacao")

    @property
    def vpa(self) -> float | None:
        return self._dados.get("vpa")

    @property
    def dividend_yield(self) -> float | None:
        return self._dados.get("dy_html")

    @property
    def dividendo_estimado(self) -> float | None:
        try:
            divs = self._dividends if self._dividends is not None else pd.Series(self._dados.get("dividendos", []))
            if len(divs) >= 6:
                tres = divs.iloc[:3].mean()
                seis = divs.iloc[:6].mean()
                return round((tres if tres < seis else seis) * 12, 2)
            elif len(divs) >= 3:
                return round(divs.iloc[:3].mean() * 12, 2)
            return None
        except Exception:
            return None


@dataclass
class FiiData:
    ticker: str
    cotacao: float | None
    vpa: float | None
    pvp: float | None
    dividend_yield: float | None   # percentual (ex: 17.01 = 17.01%) — formato direto do HTML
    dividendo_estimado: float | None  # R$/ano estimado (não percentual)
    low_52: float | None = None
    high_52: float | None = None


def fetch_fii(ticker: str) -> FiiData:
    ticker = ticker.upper()
    svc = FiisComService(ticker)
    cotacao = svc.cotacao
    vpa = svc.vpa
    pvp = round(cotacao / vpa, 2) if cotacao and vpa else None

    low_52 = None
    high_52 = None
    try:
        yf_info = yf.Ticker(f"{ticker}.SA").info or {}
        low_52 = yf_info.get("fiftyTwoWeekLow")
        high_52 = yf_info.get("fiftyTwoWeekHigh")
    except Exception:
        pass

    return FiiData(
        ticker=ticker,
        cotacao=cotacao,
        vpa=vpa,
        pvp=pvp,
        dividend_yield=svc.dividend_yield,
        dividendo_estimado=svc.dividendo_estimado,
        low_52=low_52,
        high_52=high_52,
    )

import requests
from bs4 import BeautifulSoup
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
import yfinance as yf

MESES_PT = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}


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
        nome = None
        h1 = soup.find("h1")
        if h1:
            texto = h1.get_text(" ", strip=True)
            if " - " in texto:
                nome = texto.split(" - ", 1)[1].strip()
            else:
                nome = texto.strip()
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
        ultimo_dividendo = None
        data_base_dividendo = None
        dy_mensal_html = None
        for bloco in soup.select(".yieldChart__table__bloco--rendimento"):
            linhas = bloco.find_all("div", class_="table__linha")
            if len(linhas) >= 5:
                try:
                    rend = float(linhas[-1].get_text(strip=True).replace("R$", "").replace(",", ".").strip())
                    dividendos.append(rend)
                except Exception:
                    pass
                # Primeiro bloco = mais recente
                if ultimo_dividendo is None:
                    try:
                        ultimo_dividendo = float(linhas[-1].get_text(strip=True).replace("R$", "").replace(",", ".").strip())
                    except Exception:
                        pass
                    try:
                        data_base_dividendo = linhas[1].get_text(strip=True)  # DD.MM.YYYY
                    except Exception:
                        pass
                    try:
                        dy_mensal_html = float(linhas[-2].get_text(strip=True).replace(",", ".").replace("%", "").strip())
                    except Exception:
                        pass

        return {
            "nome": nome,
            "cotacao": cotacao,
            "vpa": vpa,
            "dy_html": dy_html,
            "dividendos": dividendos,
            "ultimo_dividendo": ultimo_dividendo,
            "data_base_dividendo": data_base_dividendo,
            "dy_mensal_html": dy_mensal_html,
        }

    @property
    def nome(self) -> str | None:
        return self._dados.get("nome")

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

    @property
    def ultimo_dividendo(self) -> float | None:
        return self._dados.get("ultimo_dividendo")

    @property
    def mes_ano_dividendo(self) -> str | None:
        data = self._dados.get("data_base_dividendo")
        if not data:
            return None
        try:
            partes = data.split(".")
            mes = MESES_PT.get(partes[1], partes[1])
            return f"{mes}/{partes[2]}"
        except Exception:
            return None

    @property
    def dy_mensal(self) -> float | None:
        return self._dados.get("dy_mensal_html")


@dataclass
class FiiData:
    ticker: str
    nome: str | None
    cotacao: float | None
    vpa: float | None
    pvp: float | None
    dividend_yield: float | None   # percentual (ex: 17.01 = 17.01%) — formato direto do HTML
    dividendo_estimado: float | None  # R$/ano estimado (não percentual)
    ultimo_dividendo: float | None = None      # R$ do último rendimento
    mes_ano_dividendo: str | None = None       # ex: "Mar/2026"
    dy_mensal: float | None = None             # DY mensal (%) do último dividendo
    low_52: float | None = None
    high_52: float | None = None


def _faixa_52_semanas_por_history(history: pd.DataFrame) -> tuple[float | None, float | None]:
    if history is None or history.empty or "Close" not in history:
        return None, None

    close = history["Close"].dropna()
    if close.empty:
        return None, None

    median = close.median()
    if median and median > 0:
        lower = median * 0.5
        upper = median * 1.5
        filtered = close[(close >= lower) & (close <= upper)]
        if not filtered.empty:
            close = filtered

    return float(close.min()), float(close.max())


def fetch_fii(ticker: str) -> FiiData:
    ticker = ticker.upper()
    svc = FiisComService(ticker)
    cotacao = svc.cotacao
    vpa = svc.vpa
    pvp = round(cotacao / vpa, 2) if cotacao and vpa else None

    # Dados do scraper
    ultimo_dividendo = svc.ultimo_dividendo
    mes_ano_dividendo = svc.mes_ano_dividendo
    dy_mensal = svc.dy_mensal

    low_52 = None
    high_52 = None
    try:
        yf_ticker = yf.Ticker(f"{ticker}.SA")
        yf_info = yf_ticker.info or {}
        low_52 = yf_info.get("fiftyTwoWeekLow")
        high_52 = yf_info.get("fiftyTwoWeekHigh")
        history = yf_ticker.history(period="1y", auto_adjust=False)
        hist_low, hist_high = _faixa_52_semanas_por_history(history)

        low_is_invalid = low_52 is None or (hist_low is not None and low_52 < hist_low * 0.5)
        high_is_invalid = high_52 is None or (hist_high is not None and high_52 > hist_high * 1.5)

        if low_is_invalid:
            low_52 = hist_low
        if high_is_invalid:
            high_52 = hist_high

        # Fallback yfinance para último dividendo
        if ultimo_dividendo is None:
            last_val = yf_info.get("lastDividendValue")
            last_ts = yf_info.get("lastDividendDate")
            if last_val and last_ts:
                ultimo_dividendo = round(last_val, 2)
                try:
                    mes_ano_dividendo = datetime.fromtimestamp(last_ts).strftime("%b/%Y")
                    # Converter abreviação inglesa para portuguesa
                    mes_en = datetime.fromtimestamp(last_ts).strftime("%m")
                    mes_ano_dividendo = f"{MESES_PT.get(mes_en, mes_en)}/{datetime.fromtimestamp(last_ts).year}"
                except Exception:
                    mes_ano_dividendo = None
            if dy_mensal is None and ultimo_dividendo and cotacao and cotacao > 0:
                dy_mensal = round(ultimo_dividendo / cotacao * 100, 2)
    except Exception:
        pass

    return FiiData(
        ticker=ticker,
        nome=svc.nome,
        cotacao=cotacao,
        vpa=vpa,
        pvp=pvp,
        dividend_yield=svc.dividend_yield,
        dividendo_estimado=svc.dividendo_estimado,
        ultimo_dividendo=ultimo_dividendo,
        mes_ano_dividendo=mes_ano_dividendo,
        dy_mensal=dy_mensal,
        low_52=low_52,
        high_52=high_52,
    )

from math import sqrt
import pandas as pd


def teto_por_lucro(
    income: pd.Series,
    year_prices: dict[int, float],
    previous_close: float,
) -> float | None:
    """
    Heurística de interpolação linear lucro↔cotação (mantida da API original).
    income: pd.Series com índice de datas (últimos 5 anos de Net Income).
    year_prices: {ano: trim_mean(10%) dos últimos 30 pregões do ano}.
    """
    try:
        income = income.dropna().tail(5)
        if len(income) < 2:
            return None
        years = list(pd.to_datetime(income.index).year)
        lucros = list(income.values)
        cotacoes = [year_prices.get(y) for y in years]
        if any(c is None for c in cotacoes):
            return None
        # reverse: oldest→newest (mantido da API original — interpolação usa sequência cronológica)
        years, lucros, cotacoes = years[::-1], lucros[::-1], cotacoes[::-1]

        df = pd.DataFrame({"Lucro": lucros, "Cotacao": cotacoes})
        ultimo_lucro = df["Lucro"].iloc[-1]
        min_cot, max_cot = df["Cotacao"].min(), df["Cotacao"].max()
        min_lucro, max_lucro = df["Lucro"].min(), df["Lucro"].max()

        if max_lucro == min_lucro:
            return None

        normalizado = round(
            min_cot + (ultimo_lucro - min_lucro) * (max_cot - min_cot) / (max_lucro - min_lucro), 2
        )

        if ultimo_lucro < 0:
            # Ajuste geométrico mantido idêntico à API original (acoes.py:80-86).
            # O branch `previous_close < 1` trata penny stocks (ex: US stocks < $1).
            # `min(ajuste, normalizado)` evita que o ajuste piore o teto — também da API original.
            if previous_close < 1:
                ajuste = round(sqrt(normalizado * previous_close) / (previous_close * 100), 2)
            else:
                ajuste = round(sqrt(normalizado * previous_close), 2)
            return min(ajuste, normalizado)

        return normalizado
    except Exception:
        return None


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


def teto_bazin(dividendo_anual: float | None, indice_base: float) -> float | None:
    """teto = dividendo_anual / (indice_base / 100) — taxa dinâmica, não 6% fixo."""
    try:
        if not dividendo_anual:
            return None
        return round(dividendo_anual / (indice_base / 100), 2)
    except Exception:
        return None


def teto_graham(lpa: float | None, vpa: float | None) -> float | None:
    """teto = sqrt(22.5 * LPA * VPA). Retorna None se LPA <= 0."""
    try:
        if lpa is None or vpa is None or lpa <= 0 or vpa <= 0:
            return None
        return round(sqrt(22.5 * lpa * vpa), 2)
    except Exception:
        return None


def teto_dcf(
    free_cashflow: float | None,
    shares_outstanding: float | None,
    beta: float | None,
    earnings_growth: float | None,
    taxa_livre_risco: float,   # em % (ex: 13.75)
    premio_risco: float,       # em % (ex: 5.5 para BR, 5.0 para US)
    inflacao: float,           # em % (ex: 4.8)
) -> float | None:
    """
    DCF simplificado com dados yfinance.
    taxa_desconto = taxa_livre_risco + beta * premio_risco  (tudo em %)
    crescimento clampado em [-20%, +30%]
    """
    try:
        if any(v is None for v in [free_cashflow, shares_outstanding, beta, earnings_growth]):
            return None
        fcl_por_acao = free_cashflow / shares_outstanding
        g = min(max(earnings_growth, -0.20), 0.30)
        r = (taxa_livre_risco + beta * premio_risco) / 100
        inflacao_dec = inflacao / 100

        fluxos = sum(
            fcl_por_acao * (1 + g) ** t / (1 + r) ** t
            for t in range(1, 11)
        )
        fcl_ano10 = fcl_por_acao * (1 + g) ** 10
        valor_terminal = fcl_ano10 * (1 + inflacao_dec) / (r - inflacao_dec)
        vt_presente = valor_terminal / (1 + r) ** 10

        return round(fluxos + vt_presente, 2)
    except Exception:
        return None

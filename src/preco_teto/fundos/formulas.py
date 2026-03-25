from __future__ import annotations
from datetime import date
import math
import numpy as np
import pandas as pd


def _nearest_before(df: pd.DataFrame, target: date) -> float | None:
    """Return VL_QUOTA for the last available date <= target."""
    mask = df["DT_COMPTC"].dt.date <= target
    sub = df[mask]
    if sub.empty:
        return None
    return float(sub.iloc[-1]["VL_QUOTA"])


def rentabilidade(cotas: pd.DataFrame, inicio: date, fim: date) -> float | None:
    """(cota_fim / cota_inicio) - 1. Returns None if either cota is missing."""
    cota_ini = _nearest_before(cotas, inicio)
    cota_fim = _nearest_before(cotas, fim)
    if cota_ini is None or cota_fim is None or cota_ini == 0:
        return None
    return (cota_fim / cota_ini) - 1


def acumular_cdi(taxas_diarias: pd.Series) -> float:
    """prod(1 + r_i/100) - 1 where r_i are daily rates in %."""
    if taxas_diarias.empty:
        return 0.0
    return float(np.prod(1 + taxas_diarias.values / 100) - 1)


def pct_benchmark(ret_fundo: float, ret_bench: float) -> float | None:
    """ret_fundo / ret_bench. Returns None if benchmark <= 0."""
    if ret_bench <= 0:
        return None
    return ret_fundo / ret_bench


def volatilidade_anual(cotas: pd.DataFrame) -> float | None:
    """std(daily returns) * sqrt(252). Returns None if fewer than 2 data points."""
    if len(cotas) < 2:
        return None
    returns = cotas["VL_QUOTA"].pct_change().dropna()
    if returns.empty:
        return None
    return float(returns.std() * math.sqrt(252))


def drawdown_maximo(cotas: pd.DataFrame) -> float:
    """Maximum drawdown (peak-to-trough) over the quote series. Returns 0.0 if no drawdown."""
    prices = cotas["VL_QUOTA"].values
    peak = prices[0]
    max_dd = 0.0
    for p in prices[1:]:
        if p > peak:
            peak = p
        dd = (p / peak) - 1
        if dd < max_dd:
            max_dd = dd
    return float(max_dd)


def _monthly_returns(cotas: pd.DataFrame) -> pd.Series:
    """Returns a Series indexed by Period('M') with that month's fund return."""
    df = cotas.copy()
    df["ym"] = df["DT_COMPTC"].dt.to_period("M")
    result = {}
    for ym, group in df.groupby("ym"):
        group = group.sort_values("DT_COMPTC")
        first = float(group.iloc[0]["VL_QUOTA"])
        last = float(group.iloc[-1]["VL_QUOTA"])
        result[ym] = (last / first) - 1 if first != 0 else None
    return pd.Series(result)


def _monthly_cdi(cdi_df: pd.DataFrame) -> pd.Series:
    """Returns a Series indexed by Period('M') with that month's CDI return (accumulated)."""
    df = cdi_df.copy()
    df["ym"] = df["data"].dt.to_period("M")
    result = {}
    for ym, group in df.groupby("ym"):
        result[ym] = acumular_cdi(group["taxa"])
    return pd.Series(result)


def meses_acima_benchmark(
    cotas: pd.DataFrame, cdi_df: pd.DataFrame, n_meses: int = 36
) -> tuple[int, int]:
    """Returns (months_above, total_months) for the last n_meses months."""
    fund_monthly = _monthly_returns(cotas).tail(n_meses)
    cdi_monthly = _monthly_cdi(cdi_df)
    common = fund_monthly.index.intersection(cdi_monthly.index)
    if common.empty:
        return 0, 0
    acima = sum(
        1
        for ym in common
        if fund_monthly[ym] is not None and fund_monthly[ym] > cdi_monthly[ym]
    )
    return acima, len(common)


def meses_consecutivos_abaixo(cotas: pd.DataFrame, cdi_df: pd.DataFrame) -> int:
    """Current streak of consecutive months below benchmark."""
    fund_monthly = _monthly_returns(cotas)
    cdi_monthly = _monthly_cdi(cdi_df)
    common = sorted(fund_monthly.index.intersection(cdi_monthly.index))
    streak = 0
    for ym in reversed(common):
        f = fund_monthly[ym]
        c = cdi_monthly[ym]
        if f is not None and f < c:
            streak += 1
        else:
            break
    return streak

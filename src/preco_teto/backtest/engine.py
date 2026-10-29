"""Backtest runner: predictive power of preço-teto (ratio buckets), not a trading strategy."""
from __future__ import annotations

import numpy as np
import pandas as pd

from preco_teto.backtest.metrics import PredictiveMeta, PredictiveReport
from preco_teto.backtest.pit import (
    BENCHMARK_BR,
    BENCHMARK_US,
    DEFAULT_SEED,
    HORIZONS,
    LAG_DAYS,
    fetch_benchmark_ohlcv,
    fetch_fundamentals_bundle,
    fetch_income_net,
    fetch_ohlcv,
    is_action_ticker,
    load_rate_context,
    ni_sticky_records,
    yf_symbol,
)
from preco_teto.backtest.predictive import build_bucket_stats, collect_weekly_obs
from preco_teto.backtest.progress import backtest_progress, stage

# Re-exports used by legacy tests / helpers
from preco_teto.backtest.predictive import (  # noqa: F401
    exit_on_or_before,
    forward_return,
    mfe_mae,
    ratio_bucket,
)


def run_backtest(
    ticker: str,
    *,
    seed: int = DEFAULT_SEED,
    n_mc: int = 0,  # ignored — kept for CLI compat
    history: pd.DataFrame | None = None,
    income: pd.Series | None = None,
    index_history: pd.DataFrame | None = None,
    show_progress: bool = False,
    cascade: bool = False,
    fundamentals: dict | None = None,
    rate_ctx: dict | None = None,
) -> PredictiveReport:
    """
    Teste de poder preditivo: ratio preço/teto (PIT) × retorno futuro.
    Sem simulação de compra/venda, sem cruzamento, sem episódios-trade.
    """
    del seed, n_mc  # not used in predictive mode
    ticker = ticker.upper()
    if not is_action_ticker(ticker):
        raise ValueError(f"{ticker} — backtest v1 só para ações BR/US (não FII/ETF).")

    _, is_br = yf_symbol(ticker)

    with backtest_progress(enabled=show_progress) as progress:
        if history is None:
            with stage(progress, "Baixando preços"):
                history = fetch_ohlcv(ticker)

        if cascade:
            if fundamentals is None and income is None:
                with stage(progress, "Baixando fundamentos"):
                    fundamentals = fetch_fundamentals_bundle(ticker)
            if fundamentals is None:
                fundamentals = {
                    "is_br": is_br,
                    "income_net": income,
                    "income_stmt": None,
                    "balance_sheet": None,
                    "dividends": None,
                    "shares_outstanding": None,
                }
            if income is None:
                income = fundamentals.get("income_net")
            is_br = bool(fundamentals.get("is_br", is_br))
            if rate_ctx is None:
                with stage(progress, "Baixando taxas (CDI)"):
                    rate_ctx = load_rate_context(is_br)
        else:
            if income is None:
                with stage(progress, "Baixando demonstrações"):
                    income = fetch_income_net(ticker)
            fundamentals = fundamentals or {
                "is_br": is_br,
                "income_net": income,
                "income_stmt": None,
                "balance_sheet": None,
                "dividends": None,
                "shares_outstanding": None,
            }
            rate_ctx = rate_ctx or {}

        if income is None:
            income = pd.Series(dtype=float)
        if index_history is None:
            with stage(progress, "Baixando índice"):
                index_history = fetch_benchmark_ohlcv(is_br)

        if history is None or history.empty:
            raise ValueError(f"{ticker} — histórico de preços indisponível.")

        hist = history.copy()
        hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
        last_day = hist.index.max()
        ni_records = ni_sticky_records(income, last_price_date=last_day, lag_days=LAG_DAYS)

        with stage(progress, "Observações semanais PIT (ratio)"):
            obs = collect_weekly_obs(
                hist,
                income,
                cascade=cascade,
                lag_days=LAG_DAYS,
                dividends=fundamentals.get("dividends"),
                income_stmt=fundamentals.get("income_stmt"),
                balance_sheet=fundamentals.get("balance_sheet"),
                shares_outstanding=fundamentals.get("shares_outstanding"),
                is_br=is_br,
                cdi_daily=rate_ctx.get("cdi_daily") if rate_ctx else None,
                ipca_atual=rate_ctx.get("ipca_atual") if rate_ctx else None,
            )

        with stage(progress, "Faixas × retornos futuros"):
            buckets, spearman, details = build_bucket_stats(
                obs, hist, index_history, horizons=HORIZONS
            )

        ratios = [o.ratio for o in obs]
        income_years = int(income.dropna().shape[0]) if income is not None else 0
        notes = [
            "Modo preditivo: agrupa barras semanais com teto PIT por ratio=preço/teto; "
            "mede retorno futuro Adj Close (sem trade/cruzamento/venda).",
            f"Horizontes={list(HORIZONS)}m; MFE/MAE no caminho diário Adj; "
            f"excesso = retorno ativo − retorno {BENCHMARK_BR if is_br else BENCHMARK_US}.",
            "Episódios = trechos contíguos na mesma faixa (não são trades).",
        ]
        if cascade:
            notes.append("--cascade: teto PL→DY→VPA/ROE quando PL indisponível.")
        else:
            notes.append(f"Teto default=PL (NI sticky YE+{LAG_DAYS}d).")
        notes.append(
            f"NI yfinance: {income_years} ano(s); semanas com teto={len(obs)}."
        )
        for rec in ni_records:
            notes.append(
                f"NI YE={rec['year_end']} available={rec['available_date']} "
                f"NI={rec['net_income']:.0f} usado_como_mais_recente="
                f"{rec['used_from']}→{rec['used_until']}"
            )

        meta = PredictiveMeta(
            ticker=ticker,
            is_br=is_br,
            lag_days=LAG_DAYS,
            cascade=cascade,
            benchmark=BENCHMARK_BR if is_br else BENCHMARK_US,
            date_start=str(hist.index.min().date()) if len(hist) else None,
            date_end=str(hist.index.max().date()) if len(hist) else None,
            n_weeks_with_teto=len(obs),
            income_years=income_years,
            ratio_min=min(ratios) if ratios else None,
            ratio_median=(
                float(np.median(ratios)) if ratios else None
            ),
            notes=notes,
        )
        return PredictiveReport(
            meta=meta,
            buckets=buckets,
            spearman=spearman,
            ni_sticky=ni_records,
            observations=details,
        )

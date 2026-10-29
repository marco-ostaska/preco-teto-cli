"""Weekly signal: teto cascade PL→DY→VPA/ROE; buy on above→≤teto crossing only."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from preco_teto.backtest.pit import (
    THRESHOLD,
    LAG_DAYS,
    previous_adj_close_asof,
    resolve_teto_asof,
)

DecisionStatus = Literal[
    "teto_indisponivel",
    "sem_compra_acima_teto",
    "compra",
    "em_episodio",
]
CADENCE = "semanal"
TetoMethod = Literal["pl", "dy", "vpa_roe"]
# Zona bruta antes do filtro de cruzamento
_RawZone = Literal["nd", "below", "above"]


@dataclass(frozen=True)
class SignalEvent:
    signal_date: pd.Timestamp
    adj_close: float
    teto_pl: float  # valor do teto usado (qualquer método)
    ratio: float
    method: TetoMethod = "pl"
    fallback_notes: tuple[str, ...] = ()
    episode_weeks: int = 1


@dataclass(frozen=True)
class AsOfDecision:
    as_of: pd.Timestamp
    status: DecisionStatus
    adj_close: float | None
    teto_pl: float | None
    ratio: float | None
    method: TetoMethod | None = None
    fallback_notes: tuple[str, ...] = ()
    episode_weeks: int | None = None


MonthDecision = AsOfDecision
MonthStatus = DecisionStatus


@dataclass(frozen=True)
class CheapEpisode:
    """Semanas consecutivas com preço ≤ teto (ignorando gaps N/D no meio)."""
    signal_date: pd.Timestamp | None  # data do cruzamento; None se já começou abaixo
    end_date: pd.Timestamp
    weeks_below: int
    had_signal: bool
    method: TetoMethod | None
    ratio_at_signal: float | None
    adj_close_at_signal: float | None
    teto_at_signal: float | None
    start_date: pd.Timestamp | None = None


@dataclass
class PeriodCoverage:
    period: str
    months_evaluated: int
    months_with_teto: int
    months_teto_indisponivel: int
    buy_signals: int
    sem_compra_acima_teto: int
    coverage_pct: float
    by_method: dict[str, int] = field(default_factory=dict)
    weeks_em_episodio: int = 0
    n_episodes: int = 0


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if index is None or len(index) == 0:
        return pd.DatetimeIndex([])
    s = pd.Series(1, index=pd.DatetimeIndex(index).normalize())
    grouped = s.groupby([s.index.year, s.index.month]).apply(lambda x: x.index.max())
    return pd.DatetimeIndex(sorted(grouped.values))


def week_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if index is None or len(index) == 0:
        return pd.DatetimeIndex([])
    idx = pd.DatetimeIndex(index).normalize()
    s = pd.Series(1, index=idx)
    iso = idx.to_series().dt.isocalendar()
    grouped = s.groupby([iso.year, iso.week]).apply(lambda x: x.index.max())
    return pd.DatetimeIndex(sorted(grouped.values))


def evaluation_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return week_end_dates(index)


def signal_on_date(
    adj_close: float,
    teto_pl: float | None,
    threshold: float = THRESHOLD,
) -> bool:
    if teto_pl is None or teto_pl <= 0:
        return False
    return (adj_close / teto_pl) <= threshold


def _raw_zone(d: AsOfDecision) -> _RawZone:
    if d.status == "teto_indisponivel":
        return "nd"
    if d.status == "sem_compra_acima_teto":
        return "above"
    # raw "compra" = preço ≤ teto (ainda sem cruzamento)
    return "below"


def apply_crossing_episodes(
    raw: list[AsOfDecision],
) -> tuple[list[AsOfDecision], list[CheapEpisode]]:
    """
    Entrada (compra) ao iniciar um episódio ≤ teto:

    - > teto → ≤ teto (cruzamento clássico), ou
    - N/D → ≤ teto (primeiro teto válido já barato, ou retorno após gap N/D)

    Enquanto continuar ≤ teto: em_episodio (sem novo sinal).
    Ao passar > teto: fecha episódio e rearma.
    Gap N/D fecha o episódio (sem armar); o próximo ≤ teto é nova entrada.
    """
    out: list[AsOfDecision] = []
    episodes: list[CheapEpisode] = []

    in_episode = False
    ep_had_signal = False
    ep_signal_date: pd.Timestamp | None = None
    ep_start_date: pd.Timestamp | None = None
    ep_end: pd.Timestamp | None = None
    ep_weeks = 0
    ep_method: TetoMethod | None = None
    ep_ratio: float | None = None
    ep_adj: float | None = None
    ep_teto: float | None = None

    def _close_episode() -> None:
        nonlocal in_episode, ep_had_signal, ep_signal_date, ep_start_date
        nonlocal ep_end, ep_weeks, ep_method, ep_ratio, ep_adj, ep_teto
        if not in_episode or ep_end is None or ep_weeks <= 0:
            in_episode = False
            ep_had_signal = False
            ep_signal_date = None
            ep_start_date = None
            ep_end = None
            ep_weeks = 0
            ep_method = None
            ep_ratio = None
            ep_adj = None
            ep_teto = None
            return
        episodes.append(
            CheapEpisode(
                signal_date=ep_signal_date if ep_had_signal else None,
                start_date=ep_start_date,
                end_date=ep_end,
                weeks_below=ep_weeks,
                had_signal=ep_had_signal,
                method=ep_method,
                ratio_at_signal=ep_ratio if ep_had_signal else None,
                adj_close_at_signal=ep_adj if ep_had_signal else None,
                teto_at_signal=ep_teto if ep_had_signal else None,
            )
        )
        in_episode = False
        ep_had_signal = False
        ep_signal_date = None
        ep_start_date = None
        ep_end = None
        ep_weeks = 0
        ep_method = None
        ep_ratio = None
        ep_adj = None
        ep_teto = None

    def _open_episode(d: AsOfDecision) -> AsOfDecision:
        nonlocal in_episode, ep_had_signal, ep_signal_date, ep_start_date
        nonlocal ep_end, ep_weeks, ep_method, ep_ratio, ep_adj, ep_teto
        in_episode = True
        ep_had_signal = True
        ep_signal_date = d.as_of
        ep_start_date = d.as_of
        ep_end = d.as_of
        ep_weeks = 1
        ep_method = d.method
        ep_ratio = d.ratio
        ep_adj = d.adj_close
        ep_teto = d.teto_pl
        return AsOfDecision(
            as_of=d.as_of,
            status="compra",
            adj_close=d.adj_close,
            teto_pl=d.teto_pl,
            ratio=d.ratio,
            method=d.method,
            fallback_notes=d.fallback_notes,
        )

    def _extend_episode(d: AsOfDecision) -> AsOfDecision:
        nonlocal ep_end, ep_weeks
        ep_weeks += 1
        ep_end = d.as_of
        return AsOfDecision(
            as_of=d.as_of,
            status="em_episodio",
            adj_close=d.adj_close,
            teto_pl=d.teto_pl,
            ratio=d.ratio,
            method=d.method,
            fallback_notes=d.fallback_notes,
        )

    for d in raw:
        zone = _raw_zone(d)

        if zone == "nd":
            # Fecha episódio: próximo ≤ teto = entrada N/D → ≤ teto
            _close_episode()
            out.append(
                AsOfDecision(
                    as_of=d.as_of,
                    status="teto_indisponivel",
                    adj_close=d.adj_close,
                    teto_pl=None,
                    ratio=None,
                    method=None,
                    fallback_notes=d.fallback_notes,
                )
            )
            continue

        if zone == "above":
            _close_episode()
            out.append(
                AsOfDecision(
                    as_of=d.as_of,
                    status="sem_compra_acima_teto",
                    adj_close=d.adj_close,
                    teto_pl=d.teto_pl,
                    ratio=d.ratio,
                    method=d.method,
                    fallback_notes=d.fallback_notes,
                )
            )
            continue

        # zone == below
        if in_episode:
            out.append(_extend_episode(d))
            continue

        # Nova entrada: >teto→≤teto, N/D→≤teto, ou primeiro teto já barato
        out.append(_open_episode(d))

    _close_episode()

    weeks_by_signal = {
        e.signal_date: e.weeks_below
        for e in episodes
        if e.had_signal and e.signal_date is not None
    }
    stamped: list[AsOfDecision] = []
    for d in out:
        if d.status == "compra":
            stamped.append(
                AsOfDecision(
                    as_of=d.as_of,
                    status=d.status,
                    adj_close=d.adj_close,
                    teto_pl=d.teto_pl,
                    ratio=d.ratio,
                    method=d.method,
                    fallback_notes=d.fallback_notes,
                    episode_weeks=weeks_by_signal.get(d.as_of),
                )
            )
        else:
            stamped.append(d)
    return stamped, episodes


def classify_asofs(
    history: pd.DataFrame,
    income: pd.Series,
    *,
    lag_days: int = LAG_DAYS,
    threshold: float = THRESHOLD,
    last_signal_on_or_before: pd.Timestamp | None = None,
    cascade: bool = False,
    dividends: pd.Series | None = None,
    income_stmt=None,
    balance_sheet=None,
    shares_outstanding: float | None = None,
    is_br: bool = True,
    cdi_daily: pd.Series | None = None,
    ipca_atual: float | None = None,
) -> list[AsOfDecision]:
    decisions, _ = classify_asofs_with_episodes(
        history,
        income,
        lag_days=lag_days,
        threshold=threshold,
        last_signal_on_or_before=last_signal_on_or_before,
        cascade=cascade,
        dividends=dividends,
        income_stmt=income_stmt,
        balance_sheet=balance_sheet,
        shares_outstanding=shares_outstanding,
        is_br=is_br,
        cdi_daily=cdi_daily,
        ipca_atual=ipca_atual,
    )
    return decisions


def classify_asofs_with_episodes(
    history: pd.DataFrame,
    income: pd.Series,
    *,
    lag_days: int = LAG_DAYS,
    threshold: float = THRESHOLD,
    last_signal_on_or_before: pd.Timestamp | None = None,
    cascade: bool = False,
    dividends: pd.Series | None = None,
    income_stmt=None,
    balance_sheet=None,
    shares_outstanding: float | None = None,
    is_br: bool = True,
    cdi_daily: pd.Series | None = None,
    ipca_atual: float | None = None,
) -> tuple[list[AsOfDecision], list[CheapEpisode]]:
    if history is None or history.empty:
        return [], []
    hist = history.copy()
    hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
    ends = evaluation_dates(hist.index)
    if last_signal_on_or_before is not None:
        cutoff = pd.Timestamp(last_signal_on_or_before).normalize()
        ends = ends[ends <= cutoff]
    raw: list[AsOfDecision] = []
    for as_of in ends:
        adj = previous_adj_close_asof(hist, as_of)
        teto, method, avisos = resolve_teto_asof(
            history=hist,
            income=income,
            as_of=as_of,
            lag_days=lag_days,
            cascade=cascade,
            dividends=dividends,
            income_stmt=income_stmt,
            balance_sheet=balance_sheet,
            shares_outstanding=shares_outstanding,
            is_br=is_br,
            cdi_daily=cdi_daily,
            ipca_atual=ipca_atual,
        )
        notes = tuple(avisos)
        if adj is None or teto is None or teto <= 0:
            raw.append(
                AsOfDecision(
                    as_of=as_of,
                    status="teto_indisponivel",
                    adj_close=adj,
                    teto_pl=None,
                    ratio=None,
                    method=None,
                    fallback_notes=notes,
                )
            )
            continue
        ratio = adj / float(teto)
        # provisório: "compra" = abaixo do teto (cruzamento aplicado depois)
        status: DecisionStatus = (
            "compra" if ratio <= threshold else "sem_compra_acima_teto"
        )
        raw.append(
            AsOfDecision(
                as_of=as_of,
                status=status,
                adj_close=adj,
                teto_pl=float(teto),
                ratio=ratio,
                method=method,
                fallback_notes=notes,
            )
        )
    return apply_crossing_episodes(raw)


def classify_months(*args, **kwargs) -> list[AsOfDecision]:
    return classify_asofs(*args, **kwargs)


def coverage_by_period(
    decisions: list[AsOfDecision],
    episodes: list[CheapEpisode] | None = None,
) -> list[PeriodCoverage]:
    if not decisions:
        return [
            PeriodCoverage(
                period="TOTAL",
                months_evaluated=0,
                months_with_teto=0,
                months_teto_indisponivel=0,
                buy_signals=0,
                sem_compra_acima_teto=0,
                coverage_pct=0.0,
            )
        ]

    episodes = episodes or []

    def _eps_in_period(period: str, rows: list[AsOfDecision]) -> int:
        if period == "TOTAL":
            return len(episodes)
        years = {d.as_of.year for d in rows}
        n = 0
        for e in episodes:
            start = e.signal_date or e.start_date or e.end_date
            if start.year in years or e.end_date.year in years:
                n += 1
        return n

    def _agg(period: str, rows: list[AsOfDecision]) -> PeriodCoverage:
        n = len(rows)
        with_teto = sum(1 for d in rows if d.status != "teto_indisponivel")
        indisponivel = sum(1 for d in rows if d.status == "teto_indisponivel")
        compra = sum(1 for d in rows if d.status == "compra")
        acima = sum(1 for d in rows if d.status == "sem_compra_acima_teto")
        em_ep = sum(1 for d in rows if d.status == "em_episodio")
        by_m: dict[str, int] = {}
        for d in rows:
            if d.method and d.status != "teto_indisponivel":
                by_m[d.method] = by_m.get(d.method, 0) + 1
        return PeriodCoverage(
            period=period,
            months_evaluated=n,
            months_with_teto=with_teto,
            months_teto_indisponivel=indisponivel,
            buy_signals=compra,
            sem_compra_acima_teto=acima,
            coverage_pct=(100.0 * with_teto / n) if n else 0.0,
            by_method=by_m,
            weeks_em_episodio=em_ep,
            n_episodes=_eps_in_period(period, rows),
        )

    by_year: dict[str, list[AsOfDecision]] = {}
    for d in decisions:
        key = str(d.as_of.year)
        by_year.setdefault(key, []).append(d)
    rows = [_agg(y, by_year[y]) for y in sorted(by_year)]
    rows.append(_agg("TOTAL", decisions))
    return rows


def coverage_rows_for_display(rows: list[PeriodCoverage]) -> tuple[list[PeriodCoverage], str | None]:
    """
    Para exibição: omite anos iniciais 100% teto N/D (pré-NI Yahoo).
    Mantém TOTAL. Retorna (linhas, nota_opcional).
    """
    if not rows:
        return [], None
    year_rows = [r for r in rows if r.period != "TOTAL"]
    total = next((r for r in rows if r.period == "TOTAL"), None)
    first = next((i for i, r in enumerate(year_rows) if r.months_with_teto > 0), None)
    if first is None:
        return ([total] if total else list(rows)), None
    omitted = year_rows[:first]
    kept = list(year_rows[first:])
    if total is not None:
        kept.append(total)
    note = None
    if omitted:
        note = (
            f"Omitidos {omitted[0].period}–{omitted[-1].period} "
            f"({sum(r.months_evaluated for r in omitted)} barras, teto N/D — sem NI PIT suficiente)."
        )
    return kept, note


def iter_weekly_signals(*args, **kwargs) -> list[SignalEvent]:
    decisions, episodes = classify_asofs_with_episodes(*args, **kwargs)
    weeks_by = {
        e.signal_date: e.weeks_below
        for e in episodes
        if e.had_signal and e.signal_date is not None
    }
    events: list[SignalEvent] = []
    for d in decisions:
        if d.status != "compra":
            continue
        assert (
            d.adj_close is not None
            and d.teto_pl is not None
            and d.ratio is not None
            and d.method
        )
        events.append(
            SignalEvent(
                signal_date=d.as_of,
                adj_close=d.adj_close,
                teto_pl=d.teto_pl,
                ratio=d.ratio,
                method=d.method,
                fallback_notes=d.fallback_notes,
                episode_weeks=weeks_by.get(d.as_of, d.episode_weeks or 1),
            )
        )
    return events


iter_monthly_signals = iter_weekly_signals

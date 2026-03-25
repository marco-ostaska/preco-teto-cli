from __future__ import annotations
import re
import sys
from datetime import date
from dateutil.relativedelta import relativedelta

import typer
import pandas as pd

from preco_teto.fundos.services.cadastro import buscar_fundo
from preco_teto.fundos.services.cotas import extrair_cotas
from preco_teto.fundos.services.benchmark import fetch_benchmark_historico, normalize_benchmark
from preco_teto.fundos import formulas
from preco_teto.fundos import termometro
from preco_teto.fundos.output.tabela import exibir

app = typer.Typer()

_CNPJ_RE = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
_PERIODOS = [
    ("1m", 1), ("3m", 3), ("6m", 6), ("12m", 12), ("24m", 24), ("36m", 36)
]


def _simulacao_100_12m(periodos: list[dict]) -> dict[str, float | None] | None:
    periodo_12m = next((p for p in periodos if p["label"] == "12m"), None)
    if periodo_12m is None:
        return None

    ret_fundo = periodo_12m.get("ret_fundo")
    ret_bench = periodo_12m.get("ret_bench")
    ret_bench_liq = periodo_12m.get("ret_bench_liq")
    if ret_fundo is None or ret_bench is None:
        return None

    fundo = 100 * (1 + ret_fundo)
    benchmark = 100 * (1 + ret_bench)
    data = {"fundo": fundo, "benchmark": benchmark}
    if ret_bench_liq is not None:
        benchmark_liquido = 100 * (1 + ret_bench_liq)
        diff_valor = fundo - benchmark_liquido
        diff_pct = (diff_valor / benchmark_liquido) if benchmark_liquido else None
        data["benchmark_liquido"] = benchmark_liquido
    else:
        diff_valor = fundo - benchmark
        diff_pct = (diff_valor / benchmark) if benchmark else None
    data["diff_valor"] = diff_valor
    data["diff_pct"] = diff_pct
    return data


def _validate_cnpj(cnpj: str) -> None:
    if not _CNPJ_RE.match(cnpj):
        typer.echo(f"CNPJ inválido: {cnpj!r}. Formato esperado: XX.XXX.XXX/XXXX-XX")
        raise typer.Exit(code=1)


def _resolve_benchmark(benchmark: str | None) -> tuple[str, bool]:
    """Returns (benchmark_key, is_fallback)."""
    if benchmark is not None:
        normalized = normalize_benchmark(benchmark)
        if normalized is None:
            typer.echo("Benchmark inválido. Use: CDI, DIVO11, IVV, BTC ou USD.")
            raise typer.Exit(code=1)
        return normalized, False

    if sys.stdin.isatty():
        choice = typer.prompt(
            "Benchmark? [CDI/DIVO11/IVV/BTC/USD]",
            default="CDI",
            show_default=True,
        )
        normalized = normalize_benchmark(choice)
        if normalized is None:
            typer.echo("Benchmark inválido. Use: CDI, DIVO11, IVV, BTC ou USD.")
            raise typer.Exit(code=1)
        return normalized, False
    return "CDI", True


@app.command()
def main(cnpj: str, benchmark: str | None = typer.Option(None, "--benchmark")) -> None:
    """Avalia fundo de investimento brasileiro por CNPJ."""
    _validate_cnpj(cnpj)

    # 1. Fund registry
    try:
        info = buscar_fundo(cnpj)
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(code=1)

    # 2. Benchmark selection
    bench_key, fallback = _resolve_benchmark(benchmark)
    bench_label = bench_key

    # 3. Quote series
    try:
        cotas = extrair_cotas(cnpj, meses=36)
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(code=1)

    cota_atual_date = cotas["DT_COMPTC"].max().date()

    # 4. Benchmark historical (same range as quotes)
    cota_inicio_date = cotas["DT_COMPTC"].min().date()
    benchmark_df = fetch_benchmark_historico(bench_key, cota_inicio_date, cota_atual_date)
    benchmark_tipo = "cdi" if bench_key == "CDI" else "serie"

    # 5. Compute per-period metrics
    periodos_out = []
    for label, n in _PERIODOS:
        inicio = cota_atual_date - relativedelta(months=n)
        ret_fundo = formulas.rentabilidade(cotas, inicio, cota_atual_date)
        if bench_key == "CDI":
            mask = (
                (benchmark_df["data"].dt.date >= inicio)
                & (benchmark_df["data"].dt.date <= cota_atual_date)
            )
            cdi_slice = benchmark_df[mask]["taxa"]
            ret_bench = formulas.acumular_cdi(cdi_slice) if not cdi_slice.empty else None
            ret_bench_liq = (
                formulas.acumular_cdi_liquido(cdi_slice) if not cdi_slice.empty else None
            )
        else:
            ret_bench = formulas.rentabilidade_serie(benchmark_df, inicio, cota_atual_date)
            ret_bench_liq = None
        pct_bench = (
            formulas.pct_benchmark(ret_fundo, ret_bench)
            if ret_fundo is not None and ret_bench is not None
            else None
        )
        pct_bench_liq = (
            formulas.pct_benchmark(ret_fundo, ret_bench_liq)
            if ret_fundo is not None and ret_bench_liq is not None
            else None
        )
        perf_label = termometro.performance_relativa(ret_fundo, ret_bench, pct_bench)
        periodos_out.append({
            "label": label,
            "ret_fundo": ret_fundo,
            "ret_bench": ret_bench,
            "ret_bench_liq": ret_bench_liq,
            "pct_bench": pct_bench,
            "pct_bench_liq": pct_bench_liq,
            "perf_label": perf_label,
        })

    # 6. Risk metrics
    vol = formulas.volatilidade_anual(cotas)
    dd = formulas.drawdown_maximo(cotas)
    acima, total = formulas.meses_acima_benchmark(
        cotas, benchmark_df, n_meses=36, benchmark_tipo=benchmark_tipo
    )
    consec = formulas.meses_consecutivos_abaixo(
        cotas, benchmark_df, benchmark_tipo=benchmark_tipo
    )
    consist_label = termometro.consistencia(acima, total)
    alert_label = termometro.alerta(consec)
    periodo_12m = next((p for p in periodos_out if p["label"] == "12m"), None)
    analise_label = termometro.analise_fundo(
        periodo_12m.get("pct_bench") if periodo_12m else None,
        consist_label,
        alert_label,
    )
    simulacao_12m = _simulacao_100_12m(periodos_out)

    # 7. Render
    exibir(
        info=info,
        benchmark_label=bench_label,
        periodos=periodos_out,
        volatilidade=vol,
        drawdown=dd,
        consistencia_acima=acima,
        consistencia_total=total,
        consistencia_label=consist_label,
        alerta_label=alert_label,
        analise_label=analise_label,
        simulacao_12m=simulacao_12m,
        benchmark_fallback=fallback,
    )


if __name__ == "__main__":
    app()

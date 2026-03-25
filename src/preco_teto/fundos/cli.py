from __future__ import annotations
import re
import sys
from datetime import date
from dateutil.relativedelta import relativedelta

import typer
import pandas as pd

from preco_teto.fundos.services.cadastro import buscar_fundo
from preco_teto.fundos.services.cotas import extrair_cotas
from preco_teto.fundos.services.benchmark import detectar_benchmark, fetch_cdi_historico
from preco_teto.fundos import formulas
from preco_teto.fundos import termometro
from preco_teto.fundos.output.tabela import exibir

app = typer.Typer()

_CNPJ_RE = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
_PERIODOS = [
    ("1m", 1), ("3m", 3), ("6m", 6), ("12m", 12), ("24m", 24), ("36m", 36)
]


def _validate_cnpj(cnpj: str) -> None:
    if not _CNPJ_RE.match(cnpj):
        typer.echo(f"CNPJ inválido: {cnpj!r}. Formato esperado: XX.XXX.XXX/XXXX-XX")
        raise typer.Exit(code=1)


def _resolve_benchmark(classe_anbima: str) -> tuple[str, bool]:
    """Returns (benchmark_key, is_fallback). In v1 only CDI is supported."""
    bench = detectar_benchmark(classe_anbima)
    if bench is not None:
        return bench, False
    # Unmapped class
    if sys.stdin.isatty():
        typer.echo(
            f"Classe '{classe_anbima}' não mapeada. "
            "Benchmark? [CDI/DIVO11/BTC/USD] (default: CDI): ",
            nl=False,
        )
        choice = input().strip().upper() or "CDI"
        return choice, False
    return "CDI", True  # non-TTY fallback


@app.command()
def main(cnpj: str) -> None:
    """Avalia fundo de investimento brasileiro por CNPJ."""
    _validate_cnpj(cnpj)

    # 1. Fund registry
    try:
        info = buscar_fundo(cnpj)
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(code=1)

    # 2. Benchmark detection (v1: CDI only)
    bench_key, fallback = _resolve_benchmark(info.classe_anbima)
    bench_label = bench_key  # "CDI"

    # 3. Quote series
    try:
        cotas = extrair_cotas(cnpj, meses=36)
    except ValueError as e:
        typer.echo(f"Erro: {e}")
        raise typer.Exit(code=1)

    cota_atual_date = cotas["DT_COMPTC"].max().date()

    # 4. CDI historical (same range as quotes)
    cota_inicio_date = cotas["DT_COMPTC"].min().date()
    cdi_df = fetch_cdi_historico(cota_inicio_date, cota_atual_date)

    # 5. Compute per-period metrics
    periodos_out = []
    for label, n in _PERIODOS:
        inicio = cota_atual_date - relativedelta(months=n)
        ret_fundo = formulas.rentabilidade(cotas, inicio, cota_atual_date)
        # CDI accumulated for that period
        mask = (cdi_df["data"].dt.date >= inicio) & (cdi_df["data"].dt.date <= cota_atual_date)
        cdi_slice = cdi_df[mask]["taxa"]
        ret_bench = formulas.acumular_cdi(cdi_slice) if not cdi_slice.empty else None
        pct_bench = (
            formulas.pct_benchmark(ret_fundo, ret_bench)
            if ret_fundo is not None and ret_bench is not None
            else None
        )
        perf_label = termometro.performance(pct_bench)
        periodos_out.append({
            "label": label,
            "ret_fundo": ret_fundo,
            "ret_bench": ret_bench,
            "pct_bench": pct_bench,
            "perf_label": perf_label,
        })

    # 6. Risk metrics
    vol = formulas.volatilidade_anual(cotas)
    dd = formulas.drawdown_maximo(cotas)
    acima, total = formulas.meses_acima_benchmark(cotas, cdi_df, n_meses=36)
    consec = formulas.meses_consecutivos_abaixo(cotas, cdi_df)
    consist_label = termometro.consistencia(acima, total)
    alert_label = termometro.alerta(consec)

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
        benchmark_fallback=fallback,
    )


if __name__ == "__main__":
    app()

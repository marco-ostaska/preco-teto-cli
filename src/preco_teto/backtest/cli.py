"""CLI for `preco-teto backtest TICKER` (after argv router strips `backtest`)."""
from __future__ import annotations

import sys
from typing import Annotated

import typer

from preco_teto.backtest.engine import run_backtest
from preco_teto.backtest.pit import DEFAULT_SEED, is_action_ticker

app = typer.Typer(
    help="Poder preditivo do preço-teto (PIT): faixas de ratio × retorno futuro",
    no_args_is_help=True,
)


def _get_renderer(json_flag: bool, plain_flag: bool):
    if json_flag:
        from preco_teto.output import json_out
        return json_out
    if plain_flag:
        from preco_teto.output import plain
        return plain
    from preco_teto.output import tabela
    return tabela


def _want_progress(json_flag: bool) -> bool:
    if json_flag:
        return False
    return sys.stderr.isatty()


@app.command()
def main(
    ticker: str,
    json: Annotated[bool, typer.Option("--json")] = False,
    plain: Annotated[bool, typer.Option("--plain")] = False,
    seed: Annotated[int, typer.Option("--seed")] = DEFAULT_SEED,
    cascade: Annotated[
        bool,
        typer.Option(
            "--cascade",
            help="Se PL der ruim: DY médio 3a; se DY der ruim: VPA/ROE (CDI/Fed). Default: só PL.",
        ),
    ] = False,
) -> None:
    """Teste preditivo: ratio preço/teto PIT vs retorno futuro (sem simular trades)."""
    ticker = ticker.upper()
    if not is_action_ticker(ticker):
        typer.echo(f"{ticker} — backtest v1 só para ações BR/US (não FII/ETF).")
        raise typer.Exit(code=1)
    try:
        report = run_backtest(
            ticker,
            seed=seed,
            show_progress=_want_progress(json),
            cascade=cascade,
        )
    except ValueError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)
    renderer = _get_renderer(json, plain)
    renderer.render_backtest(report)

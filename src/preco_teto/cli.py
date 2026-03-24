from typing import Annotated
import typer

from preco_teto.services.acao import fetch_acao
from preco_teto.services.fii import fetch_fii
from preco_teto.services.referencia import fetch_indices_br, fetch_indices_us
from preco_teto.formulas import (
    teto_por_lucro, teto_por_dy, teto_bazin, teto_graham, teto_dcf
)

app = typer.Typer(help="Radar de ativos — cotação e preços teto")


def _get_renderer(json_flag: bool, plain_flag: bool):
    if json_flag:
        from preco_teto.output import json_out
        return json_out
    if plain_flag:
        from preco_teto.output import plain
        return plain
    from preco_teto.output import tabela
    return tabela


@app.command()
def acao(
    ticker: str,
    json: Annotated[bool, typer.Option("--json")] = False,
    plain: Annotated[bool, typer.Option("--plain")] = False,
):
    """Consulta cotação e preços teto de uma ação (BR ou US)."""
    data = fetch_acao(ticker)

    if data.is_br:
        idx = fetch_indices_br()
        indice_base = idx.melhor_indice
        taxa_livre = idx.cdi
        premio = 5.5
        inflacao = idx.ipca or 4.8
    else:
        idx = fetch_indices_us()
        indice_base = idx.fed_funds
        taxa_livre = idx.fed_funds
        premio = 5.0
        inflacao = idx.cpi

    tetos = {
        "teto_por_lucro": teto_por_lucro(data.income_net, data.year_prices, data.previous_close or data.cotacao or 0),
        "teto_por_dy": teto_por_dy(data.dividendo_medio, indice_base),
        "teto_bazin": teto_bazin(data.dividend_rate, indice_base),
        "teto_graham": teto_graham(data.lpa, data.vpa),
        "teto_dcf": teto_dcf(
            data.free_cashflow, data.shares_outstanding, data.beta,
            data.earnings_growth, taxa_livre or 0, premio, inflacao
        ),
    }

    renderer = _get_renderer(json, plain)
    renderer.render_acao(data.ticker, data.cotacao, data.is_br, tetos, idx)


@app.command()
def fii(
    ticker: str,
    json: Annotated[bool, typer.Option("--json")] = False,
    plain: Annotated[bool, typer.Option("--plain")] = False,
):
    """Consulta cotação e preços teto de um FII."""
    data = fetch_fii(ticker)
    idx = fetch_indices_br()
    indice_base = idx.melhor_indice

    tetos = {
        "teto_por_dy": teto_por_dy(
            (data.cotacao * data.dividend_yield / 100) if (data.cotacao and data.dividend_yield) else None,
            indice_base,
        ),
        "vpa": data.vpa,
    }

    renderer = _get_renderer(json, plain)
    renderer.render_fii(data.ticker, data.cotacao, tetos, idx)


@app.command()
def indices(
    json: Annotated[bool, typer.Option("--json")] = False,
    plain: Annotated[bool, typer.Option("--plain")] = False,
):
    """Exibe índices de referência BR e US."""
    br = fetch_indices_br()
    us = fetch_indices_us()
    renderer = _get_renderer(json, plain)
    renderer.render_indices(br, us)

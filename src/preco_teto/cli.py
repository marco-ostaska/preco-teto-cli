from typing import Annotated
import typer

from preco_teto.services.acao import fetch_acao
from preco_teto.services.fii import fetch_fii
from preco_teto.services.referencia import fetch_indices_br, fetch_indices_us
from preco_teto.formulas import (
    teto_por_lucro, teto_por_dy, teto_bazin, teto_graham, teto_dcf
)

app = typer.Typer(help="Preço teto de ativos — ações BR/US e FIIs", no_args_is_help=True)


def _get_renderer(json_flag: bool, plain_flag: bool):
    if json_flag:
        from preco_teto.output import json_out
        return json_out
    if plain_flag:
        from preco_teto.output import plain
        return plain
    from preco_teto.output import tabela
    return tabela


def _todos_none(tetos: dict) -> bool:
    return all(v is None for v in tetos.values())


def _is_fii(ticker: str) -> bool:
    return ticker.endswith("11")


@app.command()
def main(
    ticker: str,
    json: Annotated[bool, typer.Option("--json")] = False,
    plain: Annotated[bool, typer.Option("--plain")] = False,
):
    """Consulta preço teto de um ativo (ação BR/US ou FII). Use 'indices' para ver CDI e IPCA."""
    ticker = ticker.upper()

    if ticker == "INDICES":
        _indices(json=json, plain=plain)
        return

    renderer = _get_renderer(json, plain)

    # Tenta como FII se termina em 11
    if _is_fii(ticker):
        try:
            data = fetch_fii(ticker)
            idx = fetch_indices_br()
            indice_base = idx.melhor_indice
            div_anual = (data.cotacao * data.dividend_yield / 100) if data.dividend_yield and data.cotacao else None
            tetos = {
                "teto_por_dy": teto_por_dy(div_anual, indice_base) if data.cotacao else None,
                "vpa": data.vpa,
            }
            if _todos_none(tetos):
                typer.echo(f"{ticker} — cálculo de preço teto não disponível para este ativo.")
                return
            renderer.render_fii(data.ticker, data.cotacao, tetos, idx)
            return
        except Exception:
            pass  # fallback para ação BR

    # Ação BR ou US
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
        "teto_por_dy": teto_por_dy(data.dividendo_medio, indice_base) if data.dividendo_medio else None,
        "teto_bazin": teto_bazin(data.dividend_rate, indice_base),
        "teto_graham": teto_graham(data.lpa, data.vpa),
        "teto_dcf": teto_dcf(
            data.free_cashflow, data.shares_outstanding, data.beta,
            data.earnings_growth, taxa_livre or 0, premio, inflacao
        ),
    }

    if _todos_none(tetos):
        typer.echo(f"{ticker} — cálculo de preço teto não disponível para este ativo.")
        return

    renderer.render_acao(data.ticker, data.cotacao, data.is_br, tetos, idx)


def _indices(
    json: bool = False,
    plain: bool = False,
):
    """Exibe índices de referência BR (CDI e IPCA)."""
    br = fetch_indices_br()
    renderer = _get_renderer(json, plain)
    renderer.render_indices(br)

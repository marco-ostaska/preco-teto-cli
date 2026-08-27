from typing import Annotated
import typer

from preco_teto.services.acao import fetch_acao
from preco_teto.services.etf import fetch_etf
from preco_teto.services.etf_br import EtfBrFetchError, fetch_etf_br
from preco_teto.services.fii import fetch_fii
from preco_teto.services.referencia import fetch_indices_br, fetch_indices_us
from preco_teto.formulas import (
    teto_por_lucro, teto_por_dy, teto_bazin, teto_graham, teto_dcf,
    teto_margem, teto_vpa_roe, termometro_margem, p_fcf, media_ponderada_renorm
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


def _render_etf(ticker: str, renderer) -> bool:
    data = fetch_etf(ticker)
    idx = fetch_indices_br()
    tetos = {
        "teto_pl": round(data.pl_cota * 0.94, 2) if data.pl_cota is not None else None,
        "teto_margem": teto_margem(data.cotacao, data.low_52, data.high_52),
        "pl_cota": data.pl_cota,
    }
    if _todos_none(tetos):
        typer.echo(f"{ticker} — cálculo de preço teto não disponível para este ativo.")
        return True
    _margem_val = (
        (data.cotacao - data.low_52) / (data.high_52 - data.low_52)
        if data.cotacao and data.low_52 and data.high_52 and (data.high_52 - data.low_52) != 0
        else None
    )
    termometro = termometro_margem(_margem_val)
    p_fcf_agg = peg_agg = cov_p = cov_peg = None
    if data.cnpj == "":
        pares_p = []
        pares_peg = []
        for h in data.holdings:
            v = p_fcf(h.price, h.free_cashflow, h.shares_outstanding)
            if v is not None:
                pares_p.append((h.weight, v))
            if h.peg_ratio is not None:
                pares_peg.append((h.weight, h.peg_ratio))
        p_fcf_agg, cov_p = media_ponderada_renorm(pares_p)
        peg_agg, cov_peg = media_ponderada_renorm(pares_peg)
    renderer.render_etf(
        data.ticker, data.cotacao, tetos, idx,
        termometro=termometro, nome=data.nome,
        p_fcf_agregado=p_fcf_agg, peg_agregado=peg_agg,
        cobertura_p_fcf=cov_p, cobertura_peg=cov_peg,
    )
    return True


def _render_etfbr(ticker: str, renderer) -> None:
    try:
        data = fetch_etf_br(ticker)
    except EtfBrFetchError:
        typer.echo(f"{ticker} — não foi possível obter dados do ETF (etfsbrasil.com.br).")
        return
    idx = fetch_indices_br()
    tetos = {
        "teto_nav": round(data.pl_cota, 2),
        "pl_cota": round(data.pl_cota, 2),
        "teto_margem": teto_margem(data.cotacao, data.low_52, data.high_52),
        "premio_desconto_pct": round(data.premio_desconto_pct, 2),
    }
    if _todos_none({"teto_nav": tetos["teto_nav"], "teto_margem": tetos["teto_margem"]}):
        typer.echo(f"{ticker} — não foi possível obter dados do ETF (etfsbrasil.com.br).")
        return
    _margem_val = (
        (data.cotacao - data.low_52) / (data.high_52 - data.low_52)
        if data.cotacao and data.low_52 and data.high_52 and (data.high_52 - data.low_52) != 0
        else None
    )
    termometro = termometro_margem(_margem_val)
    renderer.render_etfbr(data, tetos, idx, termometro=termometro)


def _render_fii(ticker: str, renderer) -> bool:
    data = fetch_fii(ticker)
    idx = fetch_indices_br()
    indice_base = idx.melhor_indice
    div_anual = (data.cotacao * data.dividend_yield / 100) if data.dividend_yield and data.cotacao else None
    div_12m = (data.cotacao * data.dividend_yield_12m / 100) if getattr(data, "dividend_yield_12m", None) and data.cotacao else None
    tetos = {
        "teto_por_dy": teto_por_dy(div_anual, indice_base) if data.cotacao else None,
        "teto_por_dy_cdi_12m": teto_por_dy(div_12m, idx.cdi),
        "teto_bazin": teto_bazin(data.dividendo_estimado, indice_base),
        "vpa": data.vpa,
        "teto_margem": teto_margem(data.cotacao, data.low_52, data.high_52),
    }
    if _todos_none(tetos):
        typer.echo(f"{ticker} — cálculo de preço teto não disponível para este ativo.")
        return True
    _margem_val = (
        (data.cotacao - data.low_52) / (data.high_52 - data.low_52)
        if data.cotacao and data.low_52 and data.high_52 and (data.high_52 - data.low_52) != 0
        else None
    )
    termometro = termometro_margem(_margem_val)
    renderer.render_fii(
        data.ticker, data.cotacao, tetos, idx,
        termometro=termometro, nome=data.nome,
        ultimo_dividendo=data.ultimo_dividendo,
        mes_ano_dividendo=data.mes_ano_dividendo,
        dy_mensal=data.dy_mensal,
        dividend_yield_12m=getattr(data, "dividend_yield_12m", None),
    )
    return True


@app.command()
def main(
    ticker: str,
    json: Annotated[bool, typer.Option("--json")] = False,
    plain: Annotated[bool, typer.Option("--plain")] = False,
    etf: Annotated[bool, typer.Option("--etf")] = False,
    fii: Annotated[bool, typer.Option("--fii")] = False,
    etfbr: Annotated[bool, typer.Option("--etfbr")] = False,
):
    """Consulta preço teto de um ativo (ação BR/US ou FII). Use 'indices' para ver CDI e IPCA."""
    ticker = ticker.upper()

    if ticker == "INDICES":
        _indices(json=json, plain=plain)
        return

    renderer = _get_renderer(json, plain)

    if sum([etf, fii, etfbr]) > 1:
        raise typer.BadParameter("Use apenas uma flag entre --etf, --fii e --etfbr.")

    if etfbr:
        _render_etfbr(ticker, renderer)
        return

    if etf:
        _render_etf(ticker, renderer)
        return

    if fii:
        _render_fii(ticker, renderer)
        return

    # Tenta como FII se termina em 11
    if _is_fii(ticker):
        try:
            _render_fii(ticker, renderer)
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
        "teto_vpa_roe_taxa": teto_vpa_roe(data.vpa, data.roe_ajustado, taxa_livre),
        "teto_vpa_roe_inflacao": teto_vpa_roe(data.vpa, data.roe_ajustado, inflacao),
        "teto_dcf": teto_dcf(
            data.free_cashflow, data.shares_outstanding, data.beta,
            data.earnings_growth, taxa_livre or 0, premio, inflacao
        ),
        "teto_margem": teto_margem(data.cotacao, data.low_52, data.high_52),
    }

    if _todos_none(tetos):
        typer.echo(f"{ticker} — cálculo de preço teto não disponível para este ativo.")
        return

    _margem_val = (
        (data.cotacao - data.low_52) / (data.high_52 - data.low_52)
        if data.cotacao and data.low_52 and data.high_52 and (data.high_52 - data.low_52) != 0
        else None
    )
    termometro = termometro_margem(_margem_val)
    renderer.render_acao(
        data.ticker, data.cotacao, data.is_br, tetos, idx,
        termometro=termometro, nome=data.nome,
        dividend_yield=data.dividend_yield,
        dy_medio=data.dy_medio,
        roe=data.roe,
        roe_medio_5a=data.roe_medio_5a,
        roe_tendencia=data.roe_tendencia,
        roe_r2=data.roe_r2,
        roe_ajustado=data.roe_ajustado,
        ultimo_dividendo=data.ultimo_dividendo,
        mes_ano_dividendo=data.mes_ano_dividendo,
    )


def _indices(
    json: bool = False,
    plain: bool = False,
):
    """Exibe índices de referência BR (CDI e IPCA)."""
    br = fetch_indices_br()
    renderer = _get_renderer(json, plain)
    renderer.render_indices(br)

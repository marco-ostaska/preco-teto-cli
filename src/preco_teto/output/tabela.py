from __future__ import annotations

import textwrap

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

from preco_teto.formulas import (
    sinal_cobertura, sinal_p_fcf, sinal_peg, termometro_margem,
)
from preco_teto.output.alavancagem import linhas

console = Console()


def _teto_row(label: str, valor: float | None, cotacao: float | None) -> tuple:
    if valor is None:
        return label, "—", "", ""
    fmt = f"R$ {valor:.2f}" if cotacao and cotacao > 1 else f"$ {valor:.2f}"
    if cotacao:
        pct = (valor - cotacao) / cotacao * 100
        pct_str = f"{pct:+.2f}%"
    else:
        pct_str = ""
    if cotacao and valor >= cotacao:
        return label, f"[green]{fmt}[/green]", f"[green]{pct_str}[/green]", "[green]✓[/green]"
    return label, f"[red]{fmt}[/red]", f"[red]{pct_str}[/red]", "[red]✗[/red]"


def _title(ticker, nome, moeda, cotacao):
    prefixo = f"{ticker} - {nome}" if nome else ticker
    return f"{prefixo}  {moeda} {cotacao:.2f}"


def _print_cabecalho_ativo(ticker: str, nome: str | None, moeda: str, cotacao: float) -> None:
    linha = Text()
    linha.append(f"{ticker}  ", style="bold")
    linha.append(f"{moeda} {cotacao:.2f}", style="bold")
    console.print(linha)
    if nome:
        console.print(textwrap.fill(nome, width=72), style="dim")


def _print_rodape_etfbr(data, indices, termometro=None) -> None:
    linha1 = [f"CDI: {indices.cdi}%", f"IPCA: {indices.ipca}%"]
    if termometro:
        linha1.append(f"Termômetro: {termometro}")
    if data.taxa_adm_pct is not None:
        linha1.append(f"Taxa adm: {data.taxa_adm_pct:.2f}%")
    console.print("   ".join(linha1))
    if data.indice:
        console.print(f"Índice: {data.indice}")
    linha3 = []
    if data.cotistas is not None:
        linha3.append(f"Cotistas: {data.cotistas:,}".replace(",", "."))
    if data.cnpj:
        linha3.append(f"CNPJ: {data.cnpj}")
    if linha3:
        console.print("   ".join(linha3))


def render_acao(ticker, cotacao, is_br, tetos: dict, indices, termometro=None, nome=None, dividend_yield=None, dy_medio=None, roe=None, roe_medio_5a=None, roe_tendencia=None, roe_r2=None, roe_ajustado=None, alavancagem=None, ultimo_dividendo=None, mes_ano_dividendo=None):
    moeda = "R$" if is_br else "$"
    console.print()
    console.print()
    t = Table(title=_title(ticker, nome, moeda, cotacao), box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("Potencial", justify="right")
    t.add_column("")

    labels = {
        "teto_por_lucro": "Teto por Lucro  (heurística)",
        "teto_por_dy":    "Teto por DY     (DY médio 3a)",
        "teto_bazin":     f"Teto Bazin      ({'CDI dinâmico' if is_br else 'Fed Funds dinâmico'})",
        "teto_graham":    "Teto Graham     (LPA×VPA)",
        "teto_dcf":       "Teto DCF        (FCL/CAPM)",
        "teto_vpa_roe_taxa": "Teto VPA/ROE    (CDI/Fed Funds)",
        "teto_vpa_roe_inflacao": "Teto VPA/ROE    (IPCA/CPI)",
        "teto_margem":    "Teto Margem     (52w high/low)",
    }
    for key, label in labels.items():
        t.add_row(*_teto_row(label, tetos.get(key), cotacao))

    console.print(t)

    if roe is not None:
        console.print(f"ROE: {roe:.2f}%")
    if roe_medio_5a is not None:
        tendencia = f"{roe_tendencia:+.2f} p.p./ano" if roe_tendencia is not None else "—"
        confianca = f"{roe_r2:.2f}" if roe_r2 is not None else "—"
        ajustado = f"{roe_ajustado:.2f}%" if roe_ajustado is not None else "—"
        console.print(f"ROE médio: {roe_medio_5a:.2f}%   Ajustado: {ajustado}   Tendência: {tendencia}   R²: {confianca}")
    for linha in linhas(alavancagem, is_br):
        console.print(linha)

    if is_br:
        console.print(f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%" + (f"   Termômetro: {termometro}" if termometro else ""))
    else:
        console.print(f"Fed Funds: {indices.fed_funds}%   CPI: {indices.cpi}%" + (f"   Termômetro: {termometro}" if termometro else ""))

    if ultimo_dividendo is not None and mes_ano_dividendo is not None:
        moeda = "R$" if is_br else "$"
        dy_str = f"   DY: {dividend_yield:.2f}%" if dividend_yield else ""
        console.print(f"Último div: {moeda} {ultimo_dividendo:.2f} ({mes_ano_dividendo}){dy_str}")


def render_fii(ticker, cotacao, tetos: dict, indices, termometro=None, nome=None,
               ultimo_dividendo=None, mes_ano_dividendo=None, dy_mensal=None,
               dividend_yield_12m=None):
    console.print()
    console.print()
    t = Table(title=_title(ticker, nome, "R$", cotacao), box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("Potencial", justify="right")
    t.add_column("")

    for label, key in [
        ("Teto por DY  (heurística)", "teto_por_dy"),
        ("Teto DY 12m     (CDI)", "teto_por_dy_cdi_12m"),
        ("Teto Bazin   (proventos)", "teto_bazin"),
        ("VPA", "vpa"),
        ("Teto Margem  (52w high/low)", "teto_margem"),
    ]:
        t.add_row(*_teto_row(label, tetos.get(key), cotacao))
    console.print(t)
    footer = f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%"
    if ultimo_dividendo is not None and mes_ano_dividendo is not None:
        footer += f"   Último div: R$ {ultimo_dividendo:.2f} ({mes_ano_dividendo}) DY: {dy_mensal:.2f}%" if dy_mensal else f"   Último div: R$ {ultimo_dividendo:.2f} ({mes_ano_dividendo})"
    if termometro:
        footer += f"   Termômetro: {termometro}"
    if dividend_yield_12m is not None:
        footer += f"   DY 12m: {dividend_yield_12m:.2f}%"
    console.print(footer)


def render_etf(ticker, cotacao, tetos: dict, indices, termometro=None, nome=None,
               p_fcf_agregado=None, peg_agregado=None, cobertura_p_fcf=None, cobertura_peg=None):
    console.print()
    console.print()
    t = Table(title=_title(ticker, nome, "R$", cotacao), box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("Potencial", justify="right")
    t.add_column("")
    t.add_row(*_teto_row("Teto PL (-6%)", tetos.get("teto_pl"), cotacao))
    t.add_row(*_teto_row("PL por Cota", tetos.get("pl_cota"), cotacao))
    t.add_row(*_teto_row("Teto Margem (52w high/low)", tetos.get("teto_margem"), cotacao))
    console.print(t)
    _render_etf_multiplos(p_fcf_agregado, peg_agregado, cobertura_p_fcf, cobertura_peg)
    footer = f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%"
    if termometro:
        footer += f"   Termômetro: {termometro}"
    console.print(footer)


def render_etfbr(data, tetos: dict, indices, termometro=None):
    console.print()
    console.print()
    _print_cabecalho_ativo(data.ticker, data.nome, "R$", data.cotacao)
    t = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold",
        pad_edge=False,
        padding=(0, 1),
    )
    t.add_column("Teto", style="bold", min_width=18)
    t.add_column("Valor", justify="right", min_width=12)
    t.add_column("Potencial", justify="right", min_width=10)
    t.add_column("", min_width=3)
    t.add_row(*_teto_row("VP/cota", tetos.get("pl_cota"), data.cotacao))
    t.add_row(*_teto_row("Teto NAV", tetos.get("teto_nav"), data.cotacao))
    premio = tetos.get("premio_desconto_pct")
    if premio is not None:
        cor = "green" if premio <= 0 else "red"
        t.add_row("Prêmio/desconto", f"[{cor}]{premio:+.2f}%[/{cor}]", "", "")
    t.add_row(*_teto_row("Teto Margem (52w)", tetos.get("teto_margem"), data.cotacao))
    console.print(t)
    _print_rodape_etfbr(data, indices, termometro)


def _color(texto: str, sinal: str) -> str:
    return f"[{sinal}]{texto}[/{sinal}]"


def _render_etf_multiplos(p_fcf_agregado, peg_agregado, cobertura_p_fcf, cobertura_peg):
    if p_fcf_agregado is None and peg_agregado is None:
        return

    coberturas = [c for c in (cobertura_p_fcf, cobertura_peg) if c is not None]
    if coberturas and min(coberturas) < 0.70:
        nivel = "baixa" if min(coberturas) < 0.50 else "moderada"
        console.print(
            f"[yellow]Aviso: cobertura {nivel} nos top holdings "
            f"— múltiplos são aproximação, não o fundo inteiro.[/yellow]"
        )

    m = Table(title="Múltiplos (top holdings)", box=box.SIMPLE_HEAVY)
    m.add_column("Métrica", style="bold")
    m.add_column("Valor", justify="right")
    m.add_column("Cobertura", justify="right")
    m.add_column("")

    if p_fcf_agregado is not None:
        s_val = sinal_p_fcf(p_fcf_agregado)
        cov = cobertura_p_fcf
        s_cov = sinal_cobertura(cov) if cov is not None else None
        cov_str = _color(f"{cov * 100:.1f}%", s_cov) if s_cov is not None else "—"
        mark = {"green": "✓", "yellow": "~", "red": "✗"}[s_val]
        m.add_row(
            "P/FCF",
            _color(f"{p_fcf_agregado:.2f}", s_val),
            cov_str,
            _color(mark, s_val),
        )
    if peg_agregado is not None:
        s_val = sinal_peg(peg_agregado)
        cov = cobertura_peg
        s_cov = sinal_cobertura(cov) if cov is not None else None
        cov_str = _color(f"{cov * 100:.1f}%", s_cov) if s_cov is not None else "—"
        mark = {"green": "✓", "yellow": "~", "red": "✗"}[s_val]
        m.add_row(
            "PEG",
            _color(f"{peg_agregado:.2f}", s_val),
            cov_str,
            _color(mark, s_val),
        )
    console.print(m)


def _linhas_usd(data, tetos, r2_dxy, r2_cot):
    """Linhas da tabela de câmbio; o R² acompanha as linhas de relação fraca."""
    linhas = [
        ("Teto Margem  (52w PTAX)", "teto_margem", None),
        ("Teto Carrego (CDI×Fed)", "teto_carrego", None),
        ("Teto EWZ     (fluxo)", "teto_ewz", None),
    ]
    if data.dxy is not None:
        linhas.append((
            "Teto DXY     (hoje)",
            "teto_dxy",
            f"R² {r2_dxy:.2f}" if r2_dxy is not None else None,
        ))
    if data.cot is not None:
        linhas.append((
            "Teto COT     (26 sem)",
            "teto_cot",
            f"R² {r2_cot:.2f}" if r2_cot is not None else None,
        ))
    return linhas


def render_usd(data, tetos: dict, indices, fed=None, r2_dxy=None, r2_cot=None):
    console.print()
    console.print()
    titulo = (
        f"Spot comercial  USD/BRL  R$ {data.spot_comercial:.4f}"
        if data.spot_comercial is not None
        else f"PTAX  USD/BRL  R$ {data.spot:.4f}"
    )
    t = Table(title=titulo, box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("Potencial", justify="right")
    t.add_column("")

    for label, chave, nota in _linhas_usd(data, tetos, r2_dxy, r2_cot):
        rotulo, valor_cell, pct_cell, mark = _teto_row(
            label, tetos.get(chave), data.spot_ref
        )
        if nota:
            mark = f"{mark} [dim]{nota}[/dim]" if mark else f"[dim]{nota}[/dim]"
        t.add_row(rotulo, valor_cell, pct_cell, mark)
    console.print(t)

    posicao = f"{data.margem_52 * 100:.0f}%" if data.margem_52 is not None else "—"
    faixa = (
        f"R$ {data.low_52:.4f}–{data.high_52:.4f}"
        if data.low_52 is not None and data.high_52 is not None
        else "—"
    )
    console.print(
        f"Termômetro: {termometro_margem(data.margem_52)}   "
        f"Posição 52w: {posicao}   Faixa: {faixa}"
    )
    fed_txt = f"{fed}%" if fed is not None else "—"
    if data.spot is not None:
        ptax_dt = (
            f"{data.data_spot.day:02d}/{data.data_spot.month:02d}/{data.data_spot.year}"
            if data.data_spot
            else "—"
        )
        ptax_txt = f"R$ {data.spot:.4f} ({ptax_dt})"
    else:
        ptax_txt = "—"
    console.print(f"CDI: {indices.cdi}%   Fed: {fed_txt}   PTAX: {ptax_txt}")

    if data.dxy is not None:
        pctl = f"   (%il 3a: {data.dxy_pctl:.0f})" if data.dxy_pctl is not None else ""
        console.print(f"DXY: {data.dxy:.2f}{pctl}")
    if data.cot is not None:
        cot_dt = f"{data.cot.data.day:02d}/{data.cot.data.month:02d}/{data.cot.data.year}"
        console.print(
            f"COT BRL {cot_dt}: asset_mgr {data.cot.am_net_pct:+.1f}% OI "
            f"(%il {data.cot.am_pctl:.0f})   "
            f"lev_net {data.cot.lev_net_pct:+.1f}% OI (%il {data.cot.lev_pctl:.0f})"
        )
    if data.ewz is not None and data.ibov is not None:
        desvio = f"   Desvio fluxo: z={data.desvio_z:+.2f}" if data.desvio_z is not None else ""
        console.print(f"EWZ: {data.ewz:.2f}   IBOV: {data.ibov:,.0f}{desvio}".replace(",", "."))
    uup_px, uup_nav = data.uup
    udn_px, udn_nav = data.udn
    if uup_px is not None or udn_px is not None:
        uup_txt = f"{uup_px:.2f} (NAV {uup_nav:.2f})" if uup_px and uup_nav else "—"
        udn_txt = f"{udn_px:.2f} (NAV {udn_nav:.2f})" if udn_px and udn_nav else "—"
        console.print(f"UUP: {uup_txt}   UDN: {udn_txt}")


def render_indices(br):
    console.print()
    console.print()
    t = Table(title="Índices de Referência BR", box=box.SIMPLE_HEAVY)
    t.add_column("Índice")
    t.add_column("Valor", justify="right")
    t.add_row("CDI", f"{br.cdi}%" if br.cdi else "—")
    t.add_row("IPCA (12m)", f"{br.ipca}%" if br.ipca else "—")
    console.print(t)


def _pct(v):
    return "—" if v is None else f"{v * 100:.2f}%"


def render_backtest(report):
    """Poder preditivo: faixas de ratio × retorno futuro (sem trading)."""
    console.print()
    console.print()
    meta = report.meta
    mode = "cascata PL→DY→VPA/ROE" if getattr(meta, "cascade", False) else "PL"
    title = (
        f"Poder preditivo {mode} — {meta.ticker}  "
        f"semanas_com_teto={meta.n_weeks_with_teto}  cadência=semanal  lag={meta.lag_days}d"
    )
    console.print(f"[bold]{title}[/bold]")
    console.print(
        f"[dim]PIT YE+{meta.lag_days}d · ratio=preço/teto · retorno=Adj futuro · "
        f"sem compra/venda/cruzamento · bench={meta.benchmark}[/dim]"
    )

    ni_rows = getattr(report, "ni_sticky", None) or []
    if ni_rows:
        ni_t = Table(
            title="Net Income anual sticky (YE+90d → não expira)",
            box=box.SIMPLE_HEAVY,
        )
        ni_t.add_column("year_end", style="bold")
        ni_t.add_column("available_date")
        ni_t.add_column("net_income", justify="right")
        ni_t.add_column("usado_de")
        ni_t.add_column("usado_até")
        for r in ni_rows:
            ni_t.add_row(
                str(r.get("year_end")),
                str(r.get("available_date")),
                f"{r.get('net_income'):,.0f}" if r.get("net_income") is not None else "—",
                str(r.get("used_from")),
                str(r.get("used_until")),
            )
        console.print(ni_t)

    horizons = (3, 6, 12, 24)
    for h in horizons:
        t = Table(
            title=f"Horizonte {h}m — retorno futuro por faixa de ratio",
            box=box.SIMPLE_HEAVY,
        )
        t.add_column("Faixa ratio", style="bold")
        t.add_column("N barras", justify="right")
        t.add_column("N episódios", justify="right")
        t.add_column("Mean", justify="right")
        t.add_column("Median", justify="right")
        t.add_column("Win%", justify="right")
        t.add_column("MFE", justify="right")
        t.add_column("MAE", justify="right")
        t.add_column("Exc. Ibov mean", justify="right")
        t.add_column("Exc. Ibov med", justify="right")
        for block in report.buckets or []:
            s = (block.by_horizon or {}).get(h)
            if s is None:
                continue
            t.add_row(
                block.bucket,
                str(s.n_bars),
                str(s.n_episodes),
                _pct(s.mean),
                _pct(s.median),
                _pct(s.win_rate),
                _pct(s.mfe_mean),
                _pct(s.mae_mean),
                _pct(s.excess_ibov_mean),
                _pct(s.excess_ibov_median),
            )
        console.print(t)

    console.print(
        "[dim]Episódios = trechos contíguos na mesma faixa (não são trades). "
        "Exc. Ibov = retorno ativo − retorno índice nas mesmas datas.[/dim]"
    )

    sp = Table(title="Spearman(ratio, retorno futuro)", box=box.SIMPLE_HEAVY)
    sp.add_column("Horizonte", style="bold")
    sp.add_column("N", justify="right")
    sp.add_column("ρ", justify="right")
    sp.add_column("p-value", justify="right")
    for row in report.spearman or []:
        sp.add_row(
            f"{row.horizon_months}m",
            str(row.n),
            f"{row.rho:.3f}" if row.rho is not None else "—",
            f"{row.pvalue:.4g}" if row.pvalue is not None else "—",
        )
    console.print(sp)
    console.print(
        "[dim]ρ negativo ⇒ ratio mais baixo (mais barato vs teto) associado a retorno futuro maior.[/dim]"
    )

    console.print(
        f"Período: {meta.date_start} → {meta.date_end}   "
        f"semanas_com_teto={meta.n_weeks_with_teto}"
        + (
            f"  ratio_min={meta.ratio_min:.3f}  ratio_med={meta.ratio_median:.3f}"
            if meta.ratio_min is not None and meta.ratio_median is not None
            else ""
        )
    )
    for note in getattr(meta, "notes", None) or []:
        console.print(f"[yellow]Nota:[/yellow] {note}")

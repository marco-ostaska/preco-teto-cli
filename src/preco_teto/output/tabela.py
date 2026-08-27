from __future__ import annotations

import textwrap

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

from preco_teto.formulas import sinal_cobertura, sinal_p_fcf, sinal_peg

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


def render_acao(ticker, cotacao, is_br, tetos: dict, indices, termometro=None, nome=None, dividend_yield=None, dy_medio=None, roe=None, roe_medio_5a=None, roe_tendencia=None, roe_r2=None, roe_ajustado=None, ultimo_dividendo=None, mes_ano_dividendo=None):
    moeda = "R$" if is_br else "$"
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
    t.add_row(*_teto_row("Teto por DY  (heurística)", tetos.get("teto_por_dy"), cotacao))
    t.add_row(*_teto_row("Teto DY 12m     (CDI)", tetos.get("teto_por_dy_cdi_12m"), cotacao))
    t.add_row(*_teto_row("Teto Bazin   (proventos)", tetos.get("teto_bazin"), cotacao))
    t.add_row(*_teto_row("VPA", tetos.get("vpa"), cotacao))
    t.add_row(*_teto_row("Teto Margem  (52w high/low)", tetos.get("teto_margem"), cotacao))
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


def render_indices(br):
    t = Table(title="Índices de Referência BR", box=box.SIMPLE_HEAVY)
    t.add_column("Índice")
    t.add_column("Valor", justify="right")
    t.add_row("CDI", f"{br.cdi}%" if br.cdi else "—")
    t.add_row("IPCA (12m)", f"{br.ipca}%" if br.ipca else "—")
    console.print(t)

from rich.console import Console
from rich.table import Table
from rich import box

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


def render_acao(ticker, cotacao, is_br, tetos: dict, indices, termometro=None, nome=None):
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
        "teto_margem":    "Teto Margem     (52w high/low)",
    }
    for key, label in labels.items():
        t.add_row(*_teto_row(label, tetos.get(key), cotacao))

    console.print(t)

    if is_br:
        console.print(f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%" + (f"   Termômetro: {termometro}" if termometro else ""))
    else:
        console.print(f"Fed Funds: {indices.fed_funds}%   CPI: {indices.cpi}%" + (f"   Termômetro: {termometro}" if termometro else ""))


def render_fii(ticker, cotacao, tetos: dict, indices, termometro=None, nome=None,
               ultimo_dividendo=None, mes_ano_dividendo=None, dy_mensal=None):
    t = Table(title=_title(ticker, nome, "R$", cotacao), box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("Potencial", justify="right")
    t.add_column("")
    t.add_row(*_teto_row("Teto por DY  (heurística)", tetos.get("teto_por_dy"), cotacao))
    t.add_row(*_teto_row("Teto Bazin   (proventos)", tetos.get("teto_bazin"), cotacao))
    t.add_row(*_teto_row("VPA", tetos.get("vpa"), cotacao))
    t.add_row(*_teto_row("Teto Margem  (52w high/low)", tetos.get("teto_margem"), cotacao))
    console.print(t)
    footer = f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%"
    if ultimo_dividendo is not None and mes_ano_dividendo is not None:
        footer += f"   Último div: R$ {ultimo_dividendo:.2f} ({mes_ano_dividendo}) DY: {dy_mensal:.2f}%" if dy_mensal else f"   Último div: R$ {ultimo_dividendo:.2f} ({mes_ano_dividendo})"
    if termometro:
        footer += f"   Termômetro: {termometro}"
    console.print(footer)


def render_etf(ticker, cotacao, tetos: dict, indices, termometro=None, nome=None):
    t = Table(title=_title(ticker, nome, "R$", cotacao), box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("Potencial", justify="right")
    t.add_column("")
    t.add_row(*_teto_row("Teto PL (-6%)", tetos.get("teto_pl"), cotacao))
    t.add_row(*_teto_row("PL por Cota", tetos.get("pl_cota"), cotacao))
    t.add_row(*_teto_row("Teto Margem (52w high/low)", tetos.get("teto_margem"), cotacao))
    console.print(t)
    console.print(f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%" + (f"   Termômetro: {termometro}" if termometro else ""))


def render_indices(br):
    t = Table(title="Índices de Referência BR", box=box.SIMPLE_HEAVY)
    t.add_column("Índice")
    t.add_column("Valor", justify="right")
    t.add_row("CDI", f"{br.cdi}%" if br.cdi else "—")
    t.add_row("IPCA (12m)", f"{br.ipca}%" if br.ipca else "—")
    console.print(t)

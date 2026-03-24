from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def _teto_row(label: str, valor: float | None, cotacao: float | None) -> tuple:
    if valor is None:
        return label, "—", ""
    fmt = f"R$ {valor:.2f}" if cotacao and cotacao > 1 else f"$ {valor:.2f}"
    if cotacao and valor >= cotacao:
        return label, f"[green]{fmt}[/green]", "[green]✓[/green]"
    return label, f"[red]{fmt}[/red]", "[red]✗[/red]"


def render_acao(ticker, cotacao, is_br, tetos: dict, indices, termometro=None):
    moeda = "R$" if is_br else "$"
    t = Table(title=f"{ticker}  {moeda} {cotacao:.2f}", box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
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


def render_fii(ticker, cotacao, tetos: dict, indices, termometro=None):
    t = Table(title=f"{ticker}  R$ {cotacao:.2f}", box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("")
    t.add_row(*_teto_row("Teto por DY  (heurística)", tetos.get("teto_por_dy"), cotacao))
    t.add_row(*_teto_row("VPA", tetos.get("vpa"), cotacao))
    t.add_row(*_teto_row("Teto Margem  (52w high/low)", tetos.get("teto_margem"), cotacao))
    console.print(t)
    console.print(f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%" + (f"   Termômetro: {termometro}" if termometro else ""))


def render_indices(br):
    t = Table(title="Índices de Referência BR", box=box.SIMPLE_HEAVY)
    t.add_column("Índice")
    t.add_column("Valor", justify="right")
    t.add_row("CDI", f"{br.cdi}%" if br.cdi else "—")
    t.add_row("IPCA (12m)", f"{br.ipca}%" if br.ipca else "—")
    console.print(t)

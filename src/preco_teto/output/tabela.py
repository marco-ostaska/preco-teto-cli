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


def render_acao(ticker, cotacao, is_br, tetos: dict, indices):
    moeda = "R$" if is_br else "$"
    t = Table(title=f"{ticker}  {moeda} {cotacao:.2f}", box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("")

    labels = {
        "teto_por_lucro": "Teto por Lucro  (heurística)",
        "teto_por_dy":    "Teto por DY     (heurística)",
        "teto_bazin":     f"Teto Bazin      ({'CDI dinâmico' if is_br else 'TFLO dinâmico'})",
        "teto_graham":    "Teto Graham     (LPA×VPA)",
        "teto_dcf":       "Teto DCF        (FCL/CAPM)",
    }
    for key, label in labels.items():
        t.add_row(*_teto_row(label, tetos.get(key), cotacao))

    console.print(t)

    if is_br:
        console.print(
            f"IPCA: {indices.ipca}%   CDI: {indices.selic}%"
            + (f"   Juro Futuro: {indices.juro_futuro}%" if indices.juro_futuro else "")
        )
    else:
        console.print(
            f"TLT Yield (20yr): {indices.taxa_longo}%   CPI: {indices.cpi}%"
        )


def render_fii(ticker, cotacao, tetos: dict, indices):
    t = Table(title=f"{ticker}  R$ {cotacao:.2f}", box=box.SIMPLE_HEAVY)
    t.add_column("Teto", style="bold")
    t.add_column("Valor", justify="right")
    t.add_column("")
    t.add_row(*_teto_row("Teto por DY  (heurística)", tetos.get("teto_por_dy"), cotacao))
    t.add_row(*_teto_row("VPA", tetos.get("vpa"), cotacao))
    console.print(t)
    console.print(f"IPCA: {indices.ipca}%   CDI: {indices.selic}%")


def render_indices(br, us):
    t = Table(title="Índices de Referência", box=box.SIMPLE_HEAVY)
    t.add_column("Índice")
    t.add_column("Valor", justify="right")
    t.add_row("CDI (SELIC)", f"{br.selic}%" if br.selic else "—")
    t.add_row("IPCA (12m)", f"{br.ipca}%" if br.ipca else "—")
    t.add_row("Juro Futuro Pré ~2yr", f"{br.juro_futuro}%" if br.juro_futuro else "—")
    t.add_row("TFLO Yield (curto)", f"{us.taxa_curto}%" if us.taxa_curto else "—")
    t.add_row("TLT Yield (20yr)", f"{us.taxa_longo}%" if us.taxa_longo else "—")
    t.add_row("CPI (US)", f"{us.cpi}%")
    console.print(t)

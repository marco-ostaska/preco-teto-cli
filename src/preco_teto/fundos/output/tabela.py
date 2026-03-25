from __future__ import annotations
from rich.console import Console
from rich.table import Table
from preco_teto.fundos.services.cadastro import FundInfo
from preco_teto.fundos.termometro import cor_pct_benchmark

console = Console()


def _fmt_pct(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%"


def _fmt_pct_bench(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _fmt_pl(pl: float | None) -> str:
    if pl is None:
        return "—"
    if pl >= 1e9:
        return f"R$ {pl/1e9:.1f} bi"
    if pl >= 1e6:
        return f"R$ {pl/1e6:.1f} mi"
    return f"R$ {pl:,.0f}"


def _fmt_taxa(taxa: float | None) -> str:
    if taxa is None:
        return "—"
    return f"{taxa:.2f}% a.a."


def exibir(
    info: FundInfo,
    benchmark_label: str,
    periodos: list[dict],  # [{label, ret_fundo, ret_bench, pct_bench, perf_label}]
    volatilidade: float | None,
    drawdown: float | None,
    consistencia_acima: int,
    consistencia_total: int,
    consistencia_label: str,
    alerta_label: str,
    benchmark_fallback: bool = False,
) -> None:
    # Header
    console.print()
    console.print(f"[bold]{info.nome}[/bold]")
    console.print(
        f"CNPJ: {info.cnpj} | Classe: {info.classe_anbima}"
    )
    console.print(
        f"Gestor: {info.gestor} | "
        f"Taxa Adm: {_fmt_taxa(info.taxa_adm)} | "
        f"Taxa Perf: {_fmt_taxa(info.taxa_perf)}"
    )
    console.print(
        f"PL: {_fmt_pl(info.pl)} | Cotistas: {info.cotistas or '—'}"
    )
    if benchmark_fallback:
        console.print("[yellow]Aviso: classe não mapeada, usando CDI como benchmark.[/yellow]")
    console.print()

    # Performance table
    table = Table(
        title=f"Rentabilidade vs {benchmark_label} (bruto)",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Período", style="bold")
    table.add_column("Fundo", justify="right")
    table.add_column(benchmark_label, justify="right")
    table.add_column(f"% {benchmark_label}", justify="right")
    table.add_column("Performance")

    for p in periodos:
        pct = p.get("pct_bench")
        cor = cor_pct_benchmark(pct)
        pct_str = _fmt_pct_bench(pct)
        pct_cell = f"[{cor}]{pct_str}[/]" if cor else pct_str
        table.add_row(
            p["label"],
            _fmt_pct(p.get("ret_fundo")),
            _fmt_pct(p.get("ret_bench")),
            pct_cell,
            p.get("perf_label", "—"),
        )

    console.print(table)

    # Risk section
    n_avail = consistencia_total
    consist_suffix = (
        f"({consistencia_acima}/{n_avail} meses acima {benchmark_label})"
        if n_avail > 0
        else "(sem dados)"
    )
    console.print()
    console.rule("Risco")
    console.print(f"Volatilidade 12m:  {_fmt_pct(volatilidade, 2)} a.a." if volatilidade is not None else "Volatilidade 12m:  —")
    console.print(f"Drawdown máximo:   {_fmt_pct(drawdown, 2)}" if drawdown is not None else "Drawdown máximo:   —")
    console.print(f"Consistência 36m:  {consistencia_label}  {consist_suffix}")
    console.print(f"Alerta:            {alerta_label}")
    console.print()

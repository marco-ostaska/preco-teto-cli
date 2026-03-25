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


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_signed_money(value: float | None) -> str:
    if value is None:
        return "—"
    sinal = "+" if value >= 0 else "-"
    return f"{sinal}{_fmt_money(abs(value))}"


def _fmt_signed_pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    sinal = "+" if value >= 0 else "-"
    numero = f"{abs(value) * 100:.{decimals}f}".replace(".", ",")
    return f"{sinal}{numero}%"


def _benchmark_locucao(benchmark_label: str) -> str:
    if benchmark_label == "CDI":
        return f"do {benchmark_label}"
    return f"de {benchmark_label}"


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
    analise_label: str | None = None,
    simulacao_12m: dict[str, float | None] | None = None,
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
        console.print("[yellow]Aviso: benchmark não informado fora do terminal; usando CDI.[/yellow]")
    console.print()

    # Performance table
    table = Table(
        title=(
            f"Rentabilidade vs {benchmark_label} (bruto)"
            if benchmark_label == "CDI"
            else f"Rentabilidade vs {benchmark_label}"
        ),
        show_header=True,
        header_style="bold",
    )
    table.add_column("Período", style="bold")
    table.add_column("Fundo", justify="right")
    table.add_column(benchmark_label, justify="right")
    table.add_column(f"% {benchmark_label}", justify="right")
    if benchmark_label == "CDI":
        table.add_column(f"{benchmark_label} Líq.", justify="right")
        table.add_column(f"% {benchmark_label} Líq.", justify="right")
    table.add_column("Performance")

    for p in periodos:
        pct = p.get("pct_bench")
        cor = cor_pct_benchmark(pct)
        pct_str = _fmt_pct_bench(pct)
        pct_cell = f"[{cor}]{pct_str}[/]" if cor else pct_str
        row = [
            p["label"],
            _fmt_pct(p.get("ret_fundo")),
            _fmt_pct(p.get("ret_bench")),
            pct_cell,
        ]
        if benchmark_label == "CDI":
            pct_liq = p.get("pct_bench_liq")
            pct_liq_str = _fmt_pct_bench(pct_liq)
            cor_liq = cor_pct_benchmark(pct_liq)
            pct_liq_cell = f"[{cor_liq}]{pct_liq_str}[/]" if cor_liq else pct_liq_str
            row.extend([
                _fmt_pct(p.get("ret_bench_liq")),
                pct_liq_cell,
            ])
        row.append(p.get("perf_label", "—"))
        table.add_row(*row)

    console.print(table)

    if analise_label:
        console.print()
        console.print(f"Análise do Fundo: {analise_label}")

    console.print()
    console.print("Se tivesse investido R$ 100 há 12 meses:")
    if simulacao_12m is None:
        console.print("Fundo: —")
        if benchmark_label == "CDI":
            console.print(f"CDB 100% {benchmark_label} bruto: —")
            console.print(f"CDB 100% {benchmark_label} líquido: —")
            console.print("Diferença vs CDB líquido: —")
        else:
            console.print(f"{benchmark_label}: —")
            console.print(f"Diferença vs {benchmark_label}: —")
    else:
        console.print(f"Fundo: {_fmt_money(simulacao_12m.get('fundo'))}")
        if benchmark_label == "CDI":
            console.print(f"CDB 100% {benchmark_label} bruto: {_fmt_money(simulacao_12m.get('benchmark'))}")
            console.print(f"CDB 100% {benchmark_label} líquido: {_fmt_money(simulacao_12m.get('benchmark_liquido'))}")
            console.print(
                f"Diferença vs CDB líquido: {_fmt_signed_money(simulacao_12m.get('diff_valor'))} ({_fmt_signed_pct(simulacao_12m.get('diff_pct'), 1)})"
            )
        else:
            console.print(f"{benchmark_label}: {_fmt_money(simulacao_12m.get('benchmark'))}")
            console.print(
                f"Diferença vs {benchmark_label}: {_fmt_signed_money(simulacao_12m.get('diff_valor'))} ({_fmt_signed_pct(simulacao_12m.get('diff_pct'), 1)})"
            )

    # Risk section
    n_avail = consistencia_total
    consist_pct = f"{(consistencia_acima / n_avail) * 100:.1f}%".replace(".", ",") if n_avail > 0 else None
    benchmark_locucao = _benchmark_locucao(benchmark_label)
    consist_suffix = (
        f"({consistencia_acima}/{n_avail} ({consist_pct}) meses acima {benchmark_locucao})"
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

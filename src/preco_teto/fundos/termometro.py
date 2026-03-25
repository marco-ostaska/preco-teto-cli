from __future__ import annotations


def performance(pct: float | None) -> str:
    """Performance thermometer based on % benchmark (as decimal, e.g. 0.99 = 99%)."""
    if pct is None:
        return "—"
    if pct >= 1.00:
        return "Excelente"
    if pct >= 0.95:
        return "Bom"
    if pct >= 0.90:
        return "Neutro"
    if pct >= 0.80:
        return "Fraco"
    return "Ruim"


def performance_relativa(
    ret_fundo: float | None,
    ret_bench: float | None,
    pct: float | None,
) -> str:
    """Uses % benchmark when available; falls back to direct return comparison when benchmark <= 0."""
    if pct is not None:
        return performance(pct)
    if ret_fundo is None or ret_bench is None:
        return "—"
    if ret_bench <= 0:
        if ret_fundo > ret_bench:
            return "Melhor"
        if ret_fundo < ret_bench:
            return "Pior"
        return "Igual"
    return "—"


def consistencia(acima: int, total: int) -> str:
    """Consistency thermometer: % of months above benchmark."""
    if total == 0:
        return "—"
    ratio = acima / total
    if ratio >= 0.60:
        return "Consistente"
    if ratio >= 0.50:
        return "Irregular"
    return "Inconsistente"


def alerta(consecutivos_abaixo: int) -> str:
    """Alert thermometer for consecutive months below benchmark."""
    if consecutivos_abaixo >= 12:
        return "Crítico"
    if consecutivos_abaixo >= 6:
        return "Atenção"
    return "Nenhum"


def analise_fundo(pct_bench_12m: float | None, consistencia_label: str, alerta_label: str) -> str:
    """Resumo mecanico do fundo com base em 12m, consistencia e alerta."""
    if alerta_label == "Crítico":
        return "Ruim"
    if pct_bench_12m is None:
        return "Fraco"
    if pct_bench_12m < 0.90:
        return "Ruim"
    if pct_bench_12m >= 1.00 and consistencia_label == "Consistente" and alerta_label == "Nenhum":
        return "Excelente"
    if pct_bench_12m >= 0.95 and alerta_label != "Crítico":
        return "Bom"
    if pct_bench_12m >= 0.90 or consistencia_label == "Inconsistente":
        return "Fraco"
    return "Ruim"


def cor_pct_benchmark(pct: float | None) -> str | None:
    """Rich color name for the % benchmark column. None means no color."""
    if pct is None:
        return None
    if pct >= 1.00:
        return "green"
    if pct >= 0.95:
        return "yellow"
    return "red"

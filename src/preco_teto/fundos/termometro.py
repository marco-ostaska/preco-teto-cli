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


def cor_pct_benchmark(pct: float | None) -> str | None:
    """Rich color name for the % benchmark column. None means no color."""
    if pct is None:
        return None
    if pct >= 1.00:
        return "green"
    if pct >= 0.95:
        return "yellow"
    return "red"

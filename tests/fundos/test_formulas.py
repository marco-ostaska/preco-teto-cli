import pytest
import pandas as pd
from datetime import date, datetime
from preco_teto.fundos.formulas import (
    rentabilidade,
    acumular_cdi,
    acumular_cdi_liquido,
    pct_benchmark,
    volatilidade_anual,
    drawdown_maximo,
    meses_acima_benchmark,
    meses_consecutivos_abaixo,
)


def make_cotas(dates, values):
    return pd.DataFrame({
        "DT_COMPTC": pd.to_datetime(dates),
        "VL_QUOTA": values,
    })


def make_cdi(dates, taxas):
    return pd.DataFrame({
        "data": pd.to_datetime(dates),
        "taxa": taxas,
    })


# --- rentabilidade ---

def test_rentabilidade_basico():
    cotas = make_cotas(["2024-01-02", "2024-01-03", "2024-02-01"], [10.0, 10.1, 10.5])
    r = rentabilidade(cotas, date(2024, 1, 2), date(2024, 2, 1))
    assert r == pytest.approx(0.05)  # (10.5 / 10.0) - 1


def test_rentabilidade_sem_dados_suficientes():
    cotas = make_cotas(["2024-03-01"], [10.0])
    r = rentabilidade(cotas, date(2024, 1, 1), date(2024, 3, 1))
    assert r is None


# --- acumular_cdi ---

def test_acumular_cdi_dois_dias():
    # prod((1 + 0.052319/100)^2) - 1
    taxas = pd.Series([0.052319, 0.052319])
    result = acumular_cdi(taxas)
    expected = (1 + 0.052319 / 100) ** 2 - 1
    assert result == pytest.approx(expected, rel=1e-6)


def test_acumular_cdi_zero_taxas():
    result = acumular_cdi(pd.Series([], dtype=float))
    assert result == 0.0


def test_acumular_cdi_liquido_aplica_desconto_de_15_porcento_na_taxa():
    taxas = pd.Series([0.10, 0.20])
    result = acumular_cdi_liquido(taxas)
    expected = ((1 + 0.10 * 0.85 / 100) * (1 + 0.20 * 0.85 / 100)) - 1
    assert result == pytest.approx(expected, rel=1e-6)


# --- pct_benchmark ---

def test_pct_benchmark_normal():
    assert pct_benchmark(0.10, 0.108) == pytest.approx(0.10 / 0.108)


def test_pct_benchmark_bench_zero():
    assert pct_benchmark(0.05, 0.0) is None


def test_pct_benchmark_bench_negativo():
    assert pct_benchmark(0.05, -0.01) is None


# --- volatilidade_anual ---

def test_volatilidade_anual_constante():
    # constant quota → zero volatility
    cotas = make_cotas(
        [f"2024-01-{d:02d}" for d in range(2, 32)],
        [10.0] * 30,
    )
    assert volatilidade_anual(cotas) == pytest.approx(0.0, abs=1e-10)


def test_volatilidade_anual_poucos_dados():
    cotas = make_cotas(["2024-01-02"], [10.0])
    assert volatilidade_anual(cotas) is None


# --- drawdown_maximo ---

def test_drawdown_maximo_queda():
    cotas = make_cotas(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        [10.0, 11.0, 9.0, 9.5],
    )
    dd = drawdown_maximo(cotas)
    # peak=11.0, trough=9.0 → drawdown = (9.0/11.0) - 1 ≈ -0.1818
    assert dd == pytest.approx((9.0 / 11.0) - 1, rel=1e-4)


def test_drawdown_maximo_sem_queda():
    cotas = make_cotas(["2024-01-02", "2024-01-03"], [10.0, 11.0])
    dd = drawdown_maximo(cotas)
    assert dd == pytest.approx(0.0, abs=1e-10)


# --- meses_acima_benchmark ---

def test_meses_acima_benchmark():
    # Two months: Jan fundo > CDI, Feb fundo < CDI
    cotas = make_cotas(
        ["2024-01-01", "2024-01-31", "2024-02-01", "2024-02-29"],
        [10.0, 10.10, 10.10, 10.15],
    )
    cdi = make_cdi(
        pd.date_range("2024-01-01", "2024-02-29", freq="B"),
        [0.052] * len(pd.date_range("2024-01-01", "2024-02-29", freq="B")),
    )
    acima, total = meses_acima_benchmark(cotas, cdi, n_meses=2)
    assert total == 2


# --- meses_consecutivos_abaixo ---

def test_meses_consecutivos_abaixo_nenhum():
    cotas = make_cotas(
        ["2024-01-01", "2024-01-31", "2024-02-01", "2024-02-29"],
        [10.0, 10.10, 10.10, 10.20],
    )
    cdi = make_cdi(
        pd.date_range("2024-01-01", "2024-02-29", freq="B"),
        [0.040] * len(pd.date_range("2024-01-01", "2024-02-29", freq="B")),
    )
    assert meses_consecutivos_abaixo(cotas, cdi) == 0

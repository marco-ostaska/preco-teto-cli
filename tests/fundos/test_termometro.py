import pytest
from preco_teto.fundos.termometro import (
    performance,
    consistencia,
    alerta,
    cor_pct_benchmark,
)


# --- performance ---
def test_performance_excelente():
    assert performance(1.00) == "Excelente"
    assert performance(1.05) == "Excelente"

def test_performance_bom():
    assert performance(0.99) == "Bom"
    assert performance(0.95) == "Bom"

def test_performance_neutro():
    assert performance(0.94) == "Neutro"
    assert performance(0.90) == "Neutro"

def test_performance_fraco():
    assert performance(0.89) == "Fraco"
    assert performance(0.80) == "Fraco"

def test_performance_ruim():
    assert performance(0.79) == "Ruim"
    assert performance(0.50) == "Ruim"

def test_performance_none():
    assert performance(None) == "—"


# --- consistencia ---
def test_consistencia_consistente():
    assert consistencia(acima=22, total=36) == "Consistente"   # 61.1%

def test_consistencia_irregular():
    assert consistencia(acima=18, total=36) == "Irregular"    # 50%

def test_consistencia_inconsistente():
    assert consistencia(acima=17, total=36) == "Inconsistente"  # 47.2%

def test_consistencia_sem_dados():
    assert consistencia(acima=0, total=0) == "—"


# --- alerta ---
def test_alerta_nenhum():
    assert alerta(0) == "Nenhum"
    assert alerta(5) == "Nenhum"

def test_alerta_atencao():
    assert alerta(6) == "Atenção"
    assert alerta(11) == "Atenção"

def test_alerta_critico():
    assert alerta(12) == "Crítico"
    assert alerta(24) == "Crítico"


# --- cor_pct_benchmark ---
def test_cor_verde():
    assert cor_pct_benchmark(1.00) == "green"
    assert cor_pct_benchmark(1.10) == "green"

def test_cor_amarelo():
    assert cor_pct_benchmark(0.99) == "yellow"
    assert cor_pct_benchmark(0.95) == "yellow"

def test_cor_vermelho():
    assert cor_pct_benchmark(0.94) == "red"
    assert cor_pct_benchmark(0.50) == "red"

def test_cor_none():
    assert cor_pct_benchmark(None) is None

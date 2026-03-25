import pytest
from preco_teto.fundos.termometro import (
    performance,
    performance_relativa,
    consistencia,
    alerta,
    analise_fundo,
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


def test_performance_relativa_usa_pct_quando_benchmark_positivo():
    assert performance_relativa(0.12, 0.10, 1.20) == "Excelente"


def test_performance_relativa_mostra_pior_com_benchmark_negativo():
    assert performance_relativa(-0.0295, -0.0270, None) == "Pior"


def test_performance_relativa_mostra_melhor_com_benchmark_negativo():
    assert performance_relativa(-0.0100, -0.0270, None) == "Melhor"


def test_performance_relativa_mostra_igual_com_benchmark_negativo():
    assert performance_relativa(-0.0270, -0.0270, None) == "Igual"


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


# --- analise_fundo ---
def test_analise_fundo_excelente():
    assert analise_fundo(1.00, "Consistente", "Nenhum") == "Excelente"


def test_analise_fundo_bom():
    assert analise_fundo(0.97, "Irregular", "Atenção") == "Bom"


def test_analise_fundo_fraco():
    assert analise_fundo(0.92, "Inconsistente", "Nenhum") == "Fraco"


def test_analise_fundo_ruim_por_alerta_critico():
    assert analise_fundo(0.99, "Consistente", "Crítico") == "Ruim"


def test_analise_fundo_ruim_por_desempenho():
    assert analise_fundo(0.89, "Consistente", "Nenhum") == "Ruim"


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

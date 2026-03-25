from types import SimpleNamespace

from preco_teto.fundos.output import tabela


def test_exibir_colore_pct_cdi_liquido_com_a_mesma_regra_do_pct_cdi(monkeypatch):
    capturados = []

    monkeypatch.setattr(tabela.console, "print", lambda obj="": capturados.append(obj))
    monkeypatch.setattr(tabela.console, "rule", lambda obj="": capturados.append(obj))

    info = SimpleNamespace(
        nome="Fundo Teste",
        cnpj="00.000.000/0001-00",
        classe_anbima="Renda Fixa",
        gestor="Gestor",
        taxa_adm=None,
        taxa_perf=None,
        pl=1_000_000.0,
        cotistas=10,
    )

    tabela.exibir(
        info=info,
        benchmark_label="CDI",
        periodos=[{
            "label": "12m",
            "ret_fundo": 0.12,
            "ret_bench": 0.10,
            "pct_bench": 1.20,
            "ret_bench_liq": 0.085,
            "pct_bench_liq": 1.41,
            "perf_label": "Excelente",
        }],
        volatilidade=None,
        drawdown=None,
        consistencia_acima=0,
        consistencia_total=0,
        consistencia_label="—",
        alerta_label="Nenhum",
    )

    tabela_rentabilidade = next(obj for obj in capturados if hasattr(obj, "columns"))
    assert tabela_rentabilidade.columns[3]._cells[0] == "[green]120.0%[/]"
    assert tabela_rentabilidade.columns[5]._cells[0] == "[green]141.0%[/]"


def test_exibir_mostra_resumo_simulacao_e_percentual_da_consistencia(monkeypatch):
    capturados = []

    monkeypatch.setattr(tabela.console, "print", lambda obj="": capturados.append(obj))
    monkeypatch.setattr(tabela.console, "rule", lambda obj="": capturados.append(obj))

    info = SimpleNamespace(
        nome="Fundo Teste",
        cnpj="00.000.000/0001-00",
        classe_anbima="Renda Fixa",
        gestor="Gestor",
        taxa_adm=None,
        taxa_perf=None,
        pl=1_000_000.0,
        cotistas=10,
    )

    tabela.exibir(
        info=info,
        benchmark_label="CDI",
        periodos=[{
            "label": "12m",
            "ret_fundo": 0.12,
            "ret_bench": 0.10,
            "pct_bench": 1.20,
            "ret_bench_liq": 0.085,
            "pct_bench_liq": 1.41,
            "perf_label": "Excelente",
        }],
        volatilidade=None,
        drawdown=None,
        consistencia_acima=13,
        consistencia_total=28,
        consistencia_label="Inconsistente",
        alerta_label="Crítico",
        analise_label="Ruim",
        simulacao_12m={
            "fundo": 112.0,
            "benchmark": 110.0,
            "benchmark_liquido": 108.5,
            "diff_valor": 3.5,
            "diff_pct": 0.032258,
        },
    )

    linhas = [obj for obj in capturados if isinstance(obj, str)]
    assert "Análise do Fundo: Ruim" in linhas
    assert "Se tivesse investido R$ 100 há 12 meses:" in linhas
    assert "Fundo: R$ 112,00" in linhas
    assert "CDB 100% CDI bruto: R$ 110,00" in linhas
    assert "CDB 100% CDI líquido: R$ 108,50" in linhas
    assert "Diferença vs CDB líquido: +R$ 3,50 (+3,2%)" in linhas
    assert "Consistência 36m:  Inconsistente  (13/28 (46,4%) meses acima do CDI)" in linhas


def test_exibir_oculta_colunas_liquidas_e_usa_simulacao_generica_fora_do_cdi(monkeypatch):
    capturados = []

    monkeypatch.setattr(tabela.console, "print", lambda obj="": capturados.append(obj))
    monkeypatch.setattr(tabela.console, "rule", lambda obj="": capturados.append(obj))

    info = SimpleNamespace(
        nome="Fundo Exterior",
        cnpj="00.000.000/0001-00",
        classe_anbima="Ações Livre",
        gestor="Gestor",
        taxa_adm=None,
        taxa_perf=None,
        pl=1_000_000.0,
        cotistas=10,
    )

    tabela.exibir(
        info=info,
        benchmark_label="IVV",
        periodos=[{
            "label": "12m",
            "ret_fundo": 0.12,
            "ret_bench": 0.10,
            "pct_bench": 1.20,
            "perf_label": "Excelente",
        }],
        volatilidade=None,
        drawdown=None,
        consistencia_acima=13,
        consistencia_total=28,
        consistencia_label="Inconsistente",
        alerta_label="Crítico",
        analise_label="Fraco",
        simulacao_12m={
            "fundo": 112.0,
            "benchmark": 110.0,
            "diff_valor": 2.0,
            "diff_pct": 0.018182,
        },
    )

    tabela_rentabilidade = next(obj for obj in capturados if hasattr(obj, "columns"))
    assert [col.header for col in tabela_rentabilidade.columns] == [
        "Período",
        "Fundo",
        "IVV",
        "% IVV",
        "Performance",
    ]

    linhas = [obj for obj in capturados if isinstance(obj, str)]
    assert "IVV: R$ 110,00" in linhas
    assert "Diferença vs IVV: +R$ 2,00 (+1,8%)" in linhas
    assert "Consistência 36m:  Inconsistente  (13/28 (46,4%) meses acima de IVV)" in linhas

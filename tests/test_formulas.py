import pytest
import pandas as pd
from preco_teto.formulas import teto_por_lucro, teto_vpa_roe


def make_income(values):
    """5 years of net income, indexed by year strings."""
    return pd.Series(values, index=["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31"])


def make_prices(year_price: dict):
    return year_price


def test_teto_por_lucro_growing():
    income = make_income([100, 120, 140, 160, 180])
    prices = {2019: 10.0, 2020: 12.0, 2021: 14.0, 2022: 16.0, 2023: 18.0}
    result = teto_por_lucro(income, prices, previous_close=18.0)
    assert result is not None
    assert result > 0


def test_teto_por_lucro_negative_income():
    income = make_income([100, 120, 140, 160, -50])
    prices = {2019: 10.0, 2020: 12.0, 2021: 14.0, 2022: 16.0, 2023: 8.0}
    result = teto_por_lucro(income, prices, previous_close=8.0)
    assert result is not None  # applies geometric adjustment


def test_teto_por_lucro_insufficient_data():
    income = pd.Series([100], index=["2023-12-31"])
    prices = {2023: 10.0}
    result = teto_por_lucro(income, prices, previous_close=10.0)
    assert result is None


def test_teto_por_lucro_zero_range():
    """All lucros equal → division by zero → None."""
    income = make_income([100, 100, 100, 100, 100])
    prices = {2019: 10.0, 2020: 10.0, 2021: 10.0, 2022: 10.0, 2023: 10.0}
    result = teto_por_lucro(income, prices, previous_close=10.0)
    assert result is None


def test_teto_vpa_roe_usa_taxa_em_percentual():
    assert teto_vpa_roe(vpa=32.0, roe=17.12, taxa=14.65) == pytest.approx(37.40)


def test_teto_vpa_roe_none_se_dado_invalido():
    assert teto_vpa_roe(vpa=None, roe=17.12, taxa=14.65) is None


# --- remaining formulas ---
from preco_teto.formulas import teto_por_dy, teto_bazin, teto_graham, teto_dcf, teto_margem, termometro_margem, p_fcf, media_ponderada_renorm, sinal_peg, sinal_p_fcf, sinal_cobertura


def test_teto_por_dy_usa_dividendo_medio():
    """teto_por_dy agora recebe dividendo_anual direto (não cotacao * dy)."""
    # dividendo_medio = 14.40, indice_base = 11.69%
    resultado = teto_por_dy(14.40, 11.69)
    assert resultado == pytest.approx(14.40 / 0.1169, rel=1e-2)


def test_teto_por_dy_none_se_dividendo_none():
    assert teto_por_dy(None, 11.69) is None


def test_teto_por_dy_none_se_taxa_zero():
    assert teto_por_dy(14.40, 0) is None


def test_teto_bazin_positive():
    result = teto_bazin(dividendo_anual=3.0, indice_base=13.75)
    assert result == pytest.approx(3.0 / 0.1375, rel=1e-3)


def test_teto_bazin_zero_dividendo():
    result = teto_bazin(dividendo_anual=0.0, indice_base=13.75)
    assert result is None


def test_teto_bazin_none_dividendo():
    result = teto_bazin(dividendo_anual=None, indice_base=13.75)
    assert result is None


def test_teto_graham_positive():
    result = teto_graham(lpa=5.0, vpa=20.0)
    from math import sqrt
    assert result == pytest.approx(sqrt(22.5 * 5.0 * 20.0), rel=1e-3)


def test_teto_graham_negative_lpa():
    result = teto_graham(lpa=-1.0, vpa=20.0)
    assert result is None


def test_teto_graham_none_vpa():
    result = teto_graham(lpa=5.0, vpa=None)
    assert result is None


def test_teto_dcf_complete():
    result = teto_dcf(
        free_cashflow=1_000_000_000,
        shares_outstanding=500_000_000,
        beta=1.1,
        earnings_growth=0.10,
        taxa_livre_risco=13.75,
        premio_risco=5.5,
        inflacao=4.8,
    )
    assert result is not None
    assert result > 0


def test_teto_dcf_missing_fcl():
    result = teto_dcf(
        free_cashflow=None,
        shares_outstanding=500_000_000,
        beta=1.1,
        earnings_growth=0.10,
        taxa_livre_risco=13.75,
        premio_risco=5.5,
        inflacao=4.8,
    )
    assert result is None


def test_teto_dcf_missing_beta():
    result = teto_dcf(
        free_cashflow=1_000_000_000,
        shares_outstanding=500_000_000,
        beta=None,
        earnings_growth=0.10,
        taxa_livre_risco=13.75,
        premio_risco=5.5,
        inflacao=4.8,
    )
    assert result is None


def test_teto_dcf_growth_clamp_high():
    """earningsGrowth acima de 30% deve ser clampado a 30%."""
    r1 = teto_dcf(1e9, 5e8, 1.0, 0.30, 13.75, 5.5, 4.8)
    r2 = teto_dcf(1e9, 5e8, 1.0, 0.99, 13.75, 5.5, 4.8)
    assert r1 == pytest.approx(r2, rel=1e-6)


def test_teto_dcf_growth_clamp_low():
    """earningsGrowth abaixo de -20% deve ser clampado a -20%."""
    r1 = teto_dcf(1e9, 5e8, 1.0, -0.20, 13.75, 5.5, 4.8)
    r2 = teto_dcf(1e9, 5e8, 1.0, -0.99, 13.75, 5.5, 4.8)
    assert r1 == pytest.approx(r2, rel=1e-6)


def test_teto_margem_abaixo_meio():
    """margem <= 0.5: teto = low + range * margem^(1-margem)"""
    resultado = teto_margem(cotacao=30.0, low_52=20.0, high_52=60.0)
    margem = (30.0 - 20.0) / (60.0 - 20.0)  # 0.25
    esperado = round(20.0 + 40.0 * (0.25 ** (1 - 0.25)), 2)
    assert resultado == pytest.approx(esperado, rel=1e-3)


def test_teto_margem_acima_meio():
    """margem > 0.5: teto = low + range * (1 - margem^margem)"""
    resultado = teto_margem(cotacao=50.0, low_52=20.0, high_52=60.0)
    margem = (50.0 - 20.0) / (60.0 - 20.0)  # 0.75
    esperado = round(20.0 + 40.0 * (1 - 0.75 ** 0.75), 2)
    assert resultado == pytest.approx(esperado, rel=1e-3)


def test_teto_margem_none_se_range_zero():
    assert teto_margem(cotacao=30.0, low_52=30.0, high_52=30.0) is None


def test_teto_margem_none_se_none():
    assert teto_margem(cotacao=None, low_52=20.0, high_52=60.0) is None


def test_termometro_margem():
    assert termometro_margem(0.10) == "Pessimista"
    assert termometro_margem(0.30) == "Barata"
    assert termometro_margem(0.55) == "Neutro"
    assert termometro_margem(0.80) == "Otimista"
    assert termometro_margem(0.95) == "Euforia"
    assert termometro_margem(None) is None


def test_p_fcf_happy():
    # price 100, FCF 1e9, shares 1e8 → FCF/ação=10 → P/FCF=10
    assert p_fcf(100.0, 1_000_000_000, 100_000_000) == pytest.approx(10.0)


def test_p_fcf_fcf_nao_positivo():
    assert p_fcf(100.0, 0, 100_000_000) is None
    assert p_fcf(100.0, -1e9, 100_000_000) is None


def test_p_fcf_shares_none_ou_zero():
    assert p_fcf(100.0, 1e9, None) is None
    assert p_fcf(100.0, 1e9, 0) is None


def test_media_ponderada_renorm_dois_pesos():
    media, cobertura = media_ponderada_renorm([(0.10, 20.0), (0.30, 40.0)])
    # renorm: 0.10/0.40*20 + 0.30/0.40*40 = 5 + 30 = 35
    assert media == pytest.approx(35.0)
    assert cobertura == pytest.approx(0.40)


def test_media_ponderada_renorm_ignora_peso_invalido():
    media, cobertura = media_ponderada_renorm([(0.10, 20.0), (0.0, 99.0), (-0.1, 50.0)])
    assert media == pytest.approx(20.0)
    assert cobertura == pytest.approx(0.10)


def test_media_ponderada_renorm_vazia():
    media, cobertura = media_ponderada_renorm([])
    assert media is None
    assert cobertura == 0.0

def test_sinal_peg_faixas():
    assert sinal_peg(1.3) == "green"
    assert sinal_peg(1.31) == "yellow"
    assert sinal_peg(1.8) == "yellow"
    assert sinal_peg(1.81) == "red"


def test_sinal_p_fcf_faixas():
    assert sinal_p_fcf(35) == "green"
    assert sinal_p_fcf(35.01) == "yellow"
    assert sinal_p_fcf(55) == "yellow"
    assert sinal_p_fcf(55.01) == "red"


def test_sinal_cobertura_faixas():
    assert sinal_cobertura(0.70) == "green"
    assert sinal_cobertura(0.50) == "yellow"
    assert sinal_cobertura(0.499) == "red"


# --- câmbio USD/BRL ---


def test_teto_carrego_paridade_coberta():
    from preco_teto.formulas import teto_carrego

    # spot 5.00, CDI 15%, Fed 5% -> 5.00 * 1.15 / 1.05 = 5.4762
    assert teto_carrego(5.00, 15.0, 5.0) == pytest.approx(5.48, abs=0.01)


def test_teto_carrego_sem_dados_retorna_none():
    from preco_teto.formulas import teto_carrego

    assert teto_carrego(None, 15.0, 5.0) is None
    assert teto_carrego(5.0, None, 5.0) is None
    assert teto_carrego(5.0, 15.0, None) is None
    # Fed a -100% zeraria o denominador
    assert teto_carrego(5.0, 15.0, -100.0) is None


def test_teto_por_regressao_log_recupera_relacao_exata():
    import numpy as np

    from preco_teto.formulas import teto_por_regressao

    driver = pd.Series(np.linspace(90, 110, 60))
    alvo = pd.Series(np.exp(1.0 + 0.8 * np.log(driver)))

    teto, r2 = teto_por_regressao(driver, alvo, driver_alvo=100.0)

    assert teto == pytest.approx(float(np.exp(1.0 + 0.8 * np.log(100.0))), abs=0.01)
    assert r2 == pytest.approx(1.0, abs=1e-6)


def test_teto_por_regressao_linear_no_driver():
    import numpy as np

    from preco_teto.formulas import teto_por_regressao

    # posicionamento % OI pode ser negativo, então o driver não pode ir para log
    driver = pd.Series(np.linspace(-20, 40, 60))
    alvo = pd.Series(np.exp(1.6 + 0.01 * driver))

    teto, r2 = teto_por_regressao(driver, alvo, driver_alvo=0.0, log_driver=False)

    assert teto == pytest.approx(float(np.exp(1.6)), abs=0.01)
    assert r2 == pytest.approx(1.0, abs=1e-6)


def test_teto_por_regressao_poucos_pontos_retorna_none():
    from preco_teto.formulas import teto_por_regressao

    teto, r2 = teto_por_regressao(pd.Series([1.0, 2.0]), pd.Series([2.0, 3.0]), 1.5)

    assert teto is None
    assert r2 is None


def test_teto_por_regressao_ignora_driver_invalido():
    import numpy as np

    from preco_teto.formulas import teto_por_regressao

    driver = pd.Series(np.linspace(90, 110, 60))
    alvo = pd.Series(np.exp(1.0 + 0.8 * np.log(driver)))

    assert teto_por_regressao(driver, alvo, driver_alvo=0.0) == (None, None)


def test_teto_por_fluxo_calibra_pelo_ibov_em_dolar():
    from preco_teto.formulas import teto_por_fluxo

    # k_hat × IBOV / EWZ -> câmbio implícito pelo fluxo de equity
    assert teto_por_fluxo(0.00106, 170000, 33.14) == pytest.approx(5.44, abs=0.01)


def test_teto_por_fluxo_sem_dados_retorna_none():
    from preco_teto.formulas import teto_por_fluxo

    assert teto_por_fluxo(None, 170000, 33.14) is None
    assert teto_por_fluxo(0.00106, None, 33.14) is None
    assert teto_por_fluxo(0.00106, 170000, 0) is None
    assert teto_por_fluxo(0.00106, 170000, None) is None


def test_expectativa_por_posicionamento_recupera_relacao_do_retorno_futuro():
    import numpy as np

    from preco_teto.formulas import expectativa_por_posicionamento

    n = 80
    posicao = pd.Series(np.linspace(-20.0, 20.0, n))
    # retorno log semanal = c + d·posição => alvo é o acumulado disso
    c, d = 0.001, -0.0002
    log_alvo = np.log(5.0) + np.r_[0.0, np.cumsum(c + d * posicao.to_numpy()[:-1])]
    alvo = pd.Series(np.exp(log_alvo))

    esperado, r2 = expectativa_por_posicionamento(posicao, alvo, spot=5.0, horizonte=1)

    assert r2 == pytest.approx(1.0, abs=1e-6)
    assert esperado == pytest.approx(5.0 * float(np.exp(c + d * posicao.iloc[-1])), abs=0.01)


def test_expectativa_por_posicionamento_usa_horizonte_padrao_de_26_semanas():
    import numpy as np

    from preco_teto.formulas import expectativa_por_posicionamento

    n = 120
    posicao = pd.Series(np.linspace(-20.0, 20.0, n))
    alvo = pd.Series(np.exp(np.log(5.0) + np.cumsum(np.zeros(n))))

    # série constante: sem variação no alvo não há regressão possível
    assert expectativa_por_posicionamento(posicao, alvo, spot=5.0) == (None, None)


def test_expectativa_por_posicionamento_sem_spot_retorna_none():
    from preco_teto.formulas import expectativa_por_posicionamento

    assert expectativa_por_posicionamento(pd.Series([1.0]), pd.Series([5.0]), spot=None) == (None, None)


def test_expectativa_por_posicionamento_poucos_pontos_retorna_none():
    from preco_teto.formulas import expectativa_por_posicionamento

    posicao = pd.Series([1.0, 2.0, 3.0])
    alvo = pd.Series([5.0, 5.1, 5.2])

    assert expectativa_por_posicionamento(posicao, alvo, spot=5.0) == (None, None)


def test_teto_por_multiplo_recupera_preco_constante():
    import numpy as np

    from preco_teto.formulas import teto_por_multiplo

    idx = pd.bdate_range("2025-01-01", periods=20)
    # mcap/metric constante = 10 → preço = 10 * metric / supply
    circ = 1_000_000.0
    metric = pd.Series(np.linspace(1e6, 2e6, 20), index=idx)
    price = (10.0 * metric) / circ
    atual = float(metric.iloc[-1])

    result = teto_por_multiplo(price, metric, atual, circ)
    assert result == pytest.approx(float(price.iloc[-1]), abs=0.02)


def test_teto_por_multiplo_none_se_poucos_pontos():
    from preco_teto.formulas import teto_por_multiplo

    idx = pd.bdate_range("2025-01-01", periods=10)
    price = pd.Series([1.0] * 10, index=idx)
    metric = pd.Series([100.0] * 10, index=idx)
    assert teto_por_multiplo(price, metric, 100.0, 1_000.0) is None


def test_teto_por_multiplo_none_se_metric_zero_ou_negativa():
    from preco_teto.formulas import teto_por_multiplo

    idx = pd.bdate_range("2025-01-01", periods=20)
    price = pd.Series([1.0] * 20, index=idx)
    metric = pd.Series([0.0] * 20, index=idx)
    assert teto_por_multiplo(price, metric, 0.0, 1_000.0) is None
    assert teto_por_multiplo(price, pd.Series([100.0] * 20, index=idx), -1.0, 1_000.0) is None


def test_teto_por_multiplo_none_se_supply_invalido():
    from preco_teto.formulas import teto_por_multiplo

    idx = pd.bdate_range("2025-01-01", periods=20)
    price = pd.Series([1.0] * 20, index=idx)
    metric = pd.Series([100.0] * 20, index=idx)
    assert teto_por_multiplo(price, metric, 100.0, None) is None
    assert teto_por_multiplo(price, metric, 100.0, 0.0) is None

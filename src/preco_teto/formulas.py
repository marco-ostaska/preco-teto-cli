from math import sqrt
import numpy as np
import pandas as pd


def teto_por_lucro(
    income: pd.Series,
    year_prices: dict[int, float],
    previous_close: float,
) -> float | None:
    """
    Heurística de interpolação linear lucro↔cotação (mantida da API original).
    income: pd.Series com índice de datas (últimos 5 anos de Net Income).
    year_prices: {ano: trim_mean(10%) dos últimos 30 pregões do ano}.
    """
    try:
        income = income.dropna().tail(5)
        if len(income) < 2:
            return None
        years = list(pd.to_datetime(income.index).year)
        lucros = list(income.values)
        cotacoes = [year_prices.get(y) for y in years]
        if any(c is None for c in cotacoes):
            return None
        # reverse: oldest→newest (mantido da API original — interpolação usa sequência cronológica)
        years, lucros, cotacoes = years[::-1], lucros[::-1], cotacoes[::-1]

        df = pd.DataFrame({"Lucro": lucros, "Cotacao": cotacoes})
        ultimo_lucro = df["Lucro"].iloc[-1]
        min_cot, max_cot = df["Cotacao"].min(), df["Cotacao"].max()
        min_lucro, max_lucro = df["Lucro"].min(), df["Lucro"].max()

        if max_lucro == min_lucro:
            return None

        normalizado = round(
            min_cot + (ultimo_lucro - min_lucro) * (max_cot - min_cot) / (max_lucro - min_lucro), 2
        )

        if ultimo_lucro < 0:
            # Ajuste geométrico mantido idêntico à API original (acoes.py:80-86).
            # O branch `previous_close < 1` trata penny stocks (ex: US stocks < $1).
            # `min(ajuste, normalizado)` evita que o ajuste piore o teto — também da API original.
            if previous_close < 1:
                ajuste = round(sqrt(normalizado * previous_close) / (previous_close * 100), 2)
            else:
                ajuste = round(sqrt(normalizado * previous_close), 2)
            return min(ajuste, normalizado)

        return normalizado
    except Exception:
        return None


def teto_por_dy(dividendo_anual: float | None, indice_base: float) -> float | None:
    """
    teto = dividendo_anual_medio / (indice_base / 100)
    dividendo_anual: média dos últimos 1-3 anos de dividendos pagos (R$ ou $)
    indice_base: melhor_indice BR ou FED_FUNDS_US, em % (ex: 11.69)
    """
    try:
        if not dividendo_anual or not indice_base:
            return None
        return round(dividendo_anual / (indice_base / 100), 2)
    except Exception:
        return None


def teto_bazin(dividendo_anual: float | None, indice_base: float) -> float | None:
    """teto = dividendo_anual / (indice_base / 100) — taxa dinâmica, não 6% fixo."""
    try:
        if not dividendo_anual:
            return None
        return round(dividendo_anual / (indice_base / 100), 2)
    except Exception:
        return None


def teto_graham(lpa: float | None, vpa: float | None) -> float | None:
    """teto = sqrt(22.5 * LPA * VPA). Retorna None se LPA <= 0."""
    try:
        if lpa is None or vpa is None or lpa <= 0 or vpa <= 0:
            return None
        return round(sqrt(22.5 * lpa * vpa), 2)
    except Exception:
        return None


def teto_vpa_roe(vpa: float | None, roe: float | None, taxa: float | None) -> float | None:
    """Teto pelo valor patrimonial e retorno sobre o patrimonio."""
    try:
        if vpa is None or roe is None or not taxa or vpa <= 0 or roe <= 0:
            return None
        return round(vpa * roe / taxa, 2)
    except Exception:
        return None


def teto_dcf(
    free_cashflow: float | None,
    shares_outstanding: float | None,
    beta: float | None,
    earnings_growth: float | None,
    taxa_livre_risco: float,   # em % (ex: 13.75)
    premio_risco: float,       # em % (ex: 5.5 para BR, 5.0 para US)
    inflacao: float,           # em % (ex: 4.8)
) -> float | None:
    """
    DCF simplificado com dados yfinance.
    taxa_desconto = taxa_livre_risco + beta * premio_risco  (tudo em %)
    crescimento clampado em [-20%, +30%]
    """
    try:
        if any(v is None for v in [free_cashflow, shares_outstanding, beta, earnings_growth]):
            return None
        fcl_por_acao = free_cashflow / shares_outstanding
        g = min(max(earnings_growth, -0.20), 0.30)
        r = (taxa_livre_risco + beta * premio_risco) / 100
        inflacao_dec = inflacao / 100

        fluxos = sum(
            fcl_por_acao * (1 + g) ** t / (1 + r) ** t
            for t in range(1, 11)
        )
        fcl_ano10 = fcl_por_acao * (1 + g) ** 10
        valor_terminal = fcl_ano10 * (1 + inflacao_dec) / (r - inflacao_dec)
        vt_presente = valor_terminal / (1 + r) ** 10

        return round(fluxos + vt_presente, 2)
    except Exception:
        return None


def teto_margem(cotacao: float | None, low_52: float | None, high_52: float | None) -> float | None:
    """
    Teto baseado em margem de segurança 52 semanas.
    margem = (cotacao - low) / (high - low)
    se margem > 0.5: teto = low + range * (1 - margem^margem)
    caso contrário:  teto = low + range * (margem^(1-margem))
    """
    try:
        if cotacao is None or low_52 is None or high_52 is None:
            return None
        rng = high_52 - low_52
        if rng == 0:
            return None
        margem = (cotacao - low_52) / rng
        if margem > 0.5:
            teto = low_52 + rng * (1 - margem ** margem)
        else:
            teto = low_52 + rng * (margem ** (1 - margem))
        return round(teto, 2)
    except Exception:
        return None


def teto_carrego(
    spot: float | None,
    taxa_local: float | None,
    taxa_externa: float | None,
) -> float | None:
    """
    Paridade coberta de juros: nível de câmbio em que carregar BRL e USD empata.
    spot: USD/BRL atual
    taxa_local / taxa_externa: taxas em % (ex: CDI 13.65, Fed 3.98)
    """
    try:
        if spot is None or taxa_local is None or taxa_externa is None:
            return None
        denominador = 1 + taxa_externa / 100
        if denominador <= 0:
            return None
        return round(spot * (1 + taxa_local / 100) / denominador, 2)
    except Exception:
        return None


def teto_por_regressao(
    driver: pd.Series,
    alvo: pd.Series,
    driver_alvo: float,
    log_driver: bool = True,
    min_pontos: int = 30,
) -> tuple[float | None, float | None]:
    """
    OLS de ln(alvo) contra o driver; devolve (nível do alvo em driver_alvo, R²).
    alvo são datas de calendário (o alinhamento é interseção de índices).
    log_driver=False usa o driver em nível — necessário para posicionamento, que
    pode ser negativo (COT). O R² volta junto para a saída não sugerir precisão
    que a relação não tem.
    """
    try:
        if log_driver:
            if driver_alvo is None or driver_alvo <= 0:
                return None, None
            x = np.log(driver.astype(float))
            driver_nivel = float(np.log(driver_alvo))
        else:
            if driver_alvo is None:
                return None, None
            x = driver.astype(float)
            driver_nivel = float(driver_alvo)
        y = np.log(alvo.astype(float))
        base = pd.concat([x.rename("driver"), y.rename("alvo")], axis=1).dropna()
        if len(base) < min_pontos:
            return None, None
        coeficiente, intercepto = np.polyfit(base["driver"].to_numpy(), base["alvo"].to_numpy(), 1)
        previsto = intercepto + coeficiente * base["driver"]
        sst = ((base["alvo"] - base["alvo"].mean()) ** 2).sum()
        if sst == 0:
            return None, None
        r2 = 1 - ((base["alvo"] - previsto) ** 2).sum() / sst
        ln_alvo = intercepto + coeficiente * driver_nivel
        return round(float(np.exp(ln_alvo)), 2), round(float(r2), 4)
    except Exception:
        return None, None


def expectativa_por_posicionamento(
    posicao: pd.Series,
    alvo: pd.Series,
    spot: float | None,
    horizonte: int = 26,
    min_pontos: int = 30,
) -> tuple[float | None, float | None]:
    """
    OLS do retorno log futuro de `horizonte` semanas contra o posicionamento COT.
    Devolve (nível esperado partindo do spot, R²).

    É uma expectativa futura condicionada ao posicionamento — pergunta diferente
    do teto DXY, que ancora no dólar global de hoje. Ancorar os dois num
    percentil histórico do driver faz as duas linhas convergirem para a mediana
    do câmbio, que era o defeito da primeira versão.
    """
    try:
        if spot is None or horizonte < 1:
            return None, None
        base = pd.concat([posicao.rename("pos"), alvo.rename("alvo")], axis=1).dropna()
        if len(base) <= horizonte + min_pontos:
            return None, None
        dados = pd.DataFrame({
            "pos": base["pos"],
            "fwd": np.log(base["alvo"].shift(-horizonte) / base["alvo"]),
        }).dropna()
        if len(dados) < min_pontos:
            return None, None
        coeficiente, intercepto = np.polyfit(dados["pos"].to_numpy(), dados["fwd"].to_numpy(), 1)
        previsto = intercepto + coeficiente * dados["pos"]
        sst = ((dados["fwd"] - dados["fwd"].mean()) ** 2).sum()
        if sst == 0:
            return None, None
        r2 = 1 - ((dados["fwd"] - previsto) ** 2).sum() / sst
        nivel = spot * float(np.exp(intercepto + coeficiente * float(base["pos"].iloc[-1])))
        return round(nivel, 2), round(float(r2), 4)
    except Exception:
        return None, None


def teto_por_multiplo(
    price_hist: pd.Series,
    metric_hist: pd.Series,
    metric_atual: float | None,
    circ_supply: float | None,
    min_pontos: int = 14,
) -> float | None:
    """
    Teto por múltiplo histórico mcap/métrica (fees anualizadas ou TVL).
    mcap_t ≈ price_t * circ_supply; múltiplo = média geométrica(mcap/metric);
    teto = múltiplo * metric_atual / circ_supply.
    """
    try:
        if (
            circ_supply is None
            or circ_supply <= 0
            or metric_atual is None
            or metric_atual <= 0
            or price_hist is None
            or metric_hist is None
            or price_hist.empty
            or metric_hist.empty
        ):
            return None
        price = price_hist.astype(float)
        metric = metric_hist.astype(float)
        base = pd.concat(
            [price.rename("price"), metric.rename("metric")],
            axis=1,
        ).dropna()
        base = base[base["metric"] > 0]
        base = base[base["price"] > 0]
        if len(base) < min_pontos:
            return None
        mcap = base["price"] * float(circ_supply)
        ratios = mcap / base["metric"]
        if (ratios <= 0).any():
            return None
        multiplo = float(np.exp(np.log(ratios).mean()))
        return round(multiplo * float(metric_atual) / float(circ_supply), 2)
    except Exception:
        return None


def teto_por_fluxo(
    k_hat: float | None,
    ibov: float | None,
    ewz: float | None,
) -> float | None:
    """
    Câmbio implícito pelo fluxo de equity: k_hat × IBOV / EWZ.
    k_hat é a calibração (mediana recente de EWZ × USD/BRL / IBOV).
    """
    try:
        if k_hat is None or ibov is None or ewz is None or ewz == 0:
            return None
        return round(k_hat * ibov / ewz, 2)
    except Exception:
        return None


def termometro_margem(margem: float | None) -> str | None:
    """Classifica a margem de segurança em categorias qualitativas."""
    if margem is None:
        return None
    if margem < 0.25:
        return "Pessimista"
    if margem < 0.40:
        return "Barata"
    if margem < 0.75:
        return "Neutro"
    if margem < 0.90:
        return "Otimista"
    return "Euforia"


def classificar_alavancagem(
    divida_sobre_patrimonio: float | None,
    divida_liquida_sobre_ebitda: float | None,
) -> str:
    """Classifica alavancagem por limiares heurísticos informativos."""
    ratios = [
        valor for valor in (divida_sobre_patrimonio, divida_liquida_sobre_ebitda)
        if valor is not None
    ]
    if not ratios:
        return "Indisponível"
    if (
        (divida_sobre_patrimonio is not None and divida_sobre_patrimonio > 1.0)
        or (divida_liquida_sobre_ebitda is not None and divida_liquida_sobre_ebitda > 3.0)
    ):
        return "Elevada"
    if (
        (divida_sobre_patrimonio is not None and divida_sobre_patrimonio > 0.5)
        or (divida_liquida_sobre_ebitda is not None and divida_liquida_sobre_ebitda > 1.5)
    ):
        return "Atenção"
    return "Saudável"


def p_fcf(
    price: float | None,
    free_cashflow: float | None,
    shares_outstanding: float | None,
) -> float | None:
    """Preço / FCF por ação. None se faltar dado, shares<=0 ou fcf<=0."""
    try:
        if price is None or free_cashflow is None or shares_outstanding is None:
            return None
        if shares_outstanding <= 0 or free_cashflow <= 0:
            return None
        return round(price / (free_cashflow / shares_outstanding), 2)
    except Exception:
        return None


def media_ponderada_renorm(
    pares: list[tuple[float, float]],
) -> tuple[float | None, float]:
    """
    Média ponderada renormalizada.
    pares: (peso_original, valor); ignora peso<=0.
    Retorna (média, cobertura) onde cobertura = Σ pesos originais usados.
    """
    validos = [(w, v) for w, v in pares if w is not None and v is not None and w > 0]
    if not validos:
        return None, 0.0
    cobertura = sum(w for w, _ in validos)
    media = sum(w * v for w, v in validos) / cobertura
    return round(media, 2), round(cobertura, 6)


def sinal_peg(peg: float) -> str:
    """green ≤1.3 · yellow ≤1.8 · red >1.8"""
    if peg <= 1.3:
        return "green"
    if peg <= 1.8:
        return "yellow"
    return "red"


def sinal_p_fcf(valor: float) -> str:
    """green ≤35 · yellow ≤55 · red >55"""
    if valor <= 35:
        return "green"
    if valor <= 55:
        return "yellow"
    return "red"


def sinal_cobertura(cobertura: float) -> str:
    """cobertura em fração 0–1: green ≥70% · yellow ≥50% · red <50%"""
    if cobertura >= 0.70:
        return "green"
    if cobertura >= 0.50:
        return "yellow"
    return "red"

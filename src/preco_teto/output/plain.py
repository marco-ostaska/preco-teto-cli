from preco_teto.formulas import sinal_p_fcf, sinal_peg


def _fmt(valor, is_br):
    if valor is None:
        return "—"
    m = "R$" if is_br else "$"
    return f"{m} {valor:.2f}"


def _header(ticker, nome, cotacao, moeda):
    titulo = f"{ticker} - {nome}" if nome else ticker
    return f"{titulo}  {moeda} {cotacao:.2f}"


def render_acao(ticker, cotacao, is_br, tetos, indices, termometro=None, nome=None, dividend_yield=None, dy_medio=None, roe=None, roe_medio_5a=None, roe_tendencia=None, roe_r2=None, roe_ajustado=None, ultimo_dividendo=None, mes_ano_dividendo=None):
    moeda = "R$" if is_br else "$"
    print(_header(ticker, nome, cotacao, moeda))
    print("-" * 46)
    for key, label in [
        ("teto_por_lucro", "Teto por Lucro"),
        ("teto_por_dy",    "Teto por DY"),
        ("teto_bazin",     "Teto Bazin"),
        ("teto_graham",    "Teto Graham"),
        ("teto_dcf",       "Teto DCF"),
        ("teto_vpa_roe_taxa", "Teto VPA/ROE (CDI/Fed Funds)"),
        ("teto_vpa_roe_inflacao", "Teto VPA/ROE (Inflação/CPI)"),
        ("teto_margem",    "Teto Margem (52w)"),
    ]:
        v = tetos.get(key)
        mark = "OK" if (v and cotacao and v >= cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, is_br):>12}  {mark}")
    print("-" * 46)
    if roe is not None:
        print(f"ROE: {roe:.2f}%")
    if roe_medio_5a is not None:
        tendencia = f"{roe_tendencia:+.2f} p.p./ano" if roe_tendencia is not None else "—"
        confianca = f"{roe_r2:.2f}" if roe_r2 is not None else "—"
        ajustado = f"{roe_ajustado:.2f}%" if roe_ajustado is not None else "—"
        print(f"ROE médio: {roe_medio_5a:.2f}%  Ajustado: {ajustado}  Tendência: {tendencia}  R²: {confianca}")
    if is_br:
        print(f"CDI: {indices.cdi}%  IPCA: {indices.ipca}%" + (f"  Termômetro: {termometro}" if termometro else ""))
    else:
        print(f"Fed Funds: {indices.fed_funds}%  CPI: {indices.cpi}%" + (f"  Termômetro: {termometro}" if termometro else ""))

    if ultimo_dividendo is not None and mes_ano_dividendo is not None:
        moeda = "R$" if is_br else "$"
        dy_str = f"  DY: {dividend_yield:.2f}%" if dividend_yield else ""
        print(f"Último div: {moeda} {ultimo_dividendo:.2f} ({mes_ano_dividendo}){dy_str}")


def render_fii(ticker, cotacao, tetos, indices, termometro=None, nome=None,
               ultimo_dividendo=None, mes_ano_dividendo=None, dy_mensal=None):
    print(_header(ticker, nome, cotacao, "R$"))
    print("-" * 46)
    for key, label in [
        ("teto_por_dy", "Teto por DY"),
        ("teto_bazin", "Teto Bazin"),
        ("vpa", "VPA"),
        ("teto_margem", "Teto Margem (52w)"),
    ]:
        v = tetos.get(key)
        mark = "OK" if (v and cotacao and v >= cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, True):>12}  {mark}")
    if ultimo_dividendo is not None and mes_ano_dividendo is not None:
        dy_str = f"  DY: {dy_mensal:.2f}%" if dy_mensal else ""
        print(f"Último div: R$ {ultimo_dividendo:.2f} ({mes_ano_dividendo}){dy_str}")
    if termometro:
        print(f"Termômetro: {termometro}")


def render_etfbr(data, tetos, indices, termometro=None):
    print()
    print(f"{data.ticker}  R$ {data.cotacao:.2f}")
    if data.nome:
        print(data.nome)
    print("-" * 46)
    for key, label in [
        ("pl_cota", "VP/cota"),
        ("teto_nav", "Teto NAV"),
        ("teto_margem", "Teto Margem (52w)"),
    ]:
        v = tetos.get(key)
        mark = "OK" if (v and data.cotacao and v >= data.cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, True):>12}  {mark}")
    premio = tetos.get("premio_desconto_pct")
    if premio is not None:
        print(f"{'Prêmio/desconto':<30} {premio:>+11.2f}%")
    print("-" * 46)
    linha1 = [f"CDI: {indices.cdi}%", f"IPCA: {indices.ipca}%"]
    if termometro:
        linha1.append(f"Termômetro: {termometro}")
    if data.taxa_adm_pct is not None:
        linha1.append(f"Taxa adm: {data.taxa_adm_pct:.2f}%")
    print("   ".join(linha1))
    if data.indice:
        print(f"Índice: {data.indice}")
    linha3 = []
    if data.cotistas is not None:
        linha3.append(f"Cotistas: {data.cotistas:,}".replace(",", "."))
    if data.cnpj:
        linha3.append(f"CNPJ: {data.cnpj}")
    if linha3:
        print("   ".join(linha3))


def render_etf(ticker, cotacao, tetos, indices, termometro=None, nome=None,
               p_fcf_agregado=None, peg_agregado=None, cobertura_p_fcf=None, cobertura_peg=None):
    print()
    print()
    print(_header(ticker, nome, cotacao, "R$"))
    print("-" * 46)
    for key, label in [
        ("teto_pl", "Teto PL (-6%)"),
        ("pl_cota", "PL por Cota"),
        ("teto_margem", "Teto Margem (52w)"),
    ]:
        v = tetos.get(key)
        mark = "OK" if (v and cotacao and v >= cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, True):>12}  {mark}")

    if p_fcf_agregado is not None or peg_agregado is not None:
        coberturas = [c for c in (cobertura_p_fcf, cobertura_peg) if c is not None]
        if coberturas and min(coberturas) < 0.70:
            nivel = "baixa" if min(coberturas) < 0.50 else "moderada"
            print(
                f"Aviso: cobertura {nivel} nos top holdings "
                f"— múltiplos são aproximação, não o fundo inteiro."
            )
        print("Múltiplos (top holdings)")
        print("-" * 46)
        _marks = {"green": "OK", "yellow": "~", "red": "X"}
        if p_fcf_agregado is not None:
            s = sinal_p_fcf(p_fcf_agregado)
            cov = f"{cobertura_p_fcf * 100:.1f}%" if cobertura_p_fcf is not None else "—"
            print(f"{'P/FCF':<30} {p_fcf_agregado:>12.2f}  cov {cov}  {_marks[s]}")
        if peg_agregado is not None:
            s = sinal_peg(peg_agregado)
            cov = f"{cobertura_peg * 100:.1f}%" if cobertura_peg is not None else "—"
            print(f"{'PEG':<30} {peg_agregado:>12.2f}  cov {cov}  {_marks[s]}")

    footer = f"CDI: {indices.cdi}%   IPCA: {indices.ipca}%"
    if termometro:
        footer += f"   Termômetro: {termometro}"
    print(footer)


def render_indices(br):
    print(f"CDI:   {br.cdi}%")
    print(f"IPCA:  {br.ipca}%")

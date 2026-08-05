import json


def render_acao(ticker, cotacao, is_br, tetos, indices, termometro=None, nome=None, dividend_yield=None, dy_medio=None, ultimo_dividendo=None, mes_ano_dividendo=None):
    print(json.dumps({
        "ticker": ticker,
        "nome": nome,
        "cotacao": cotacao,
        "is_br": is_br,
        "tetos": tetos,
        "dividend_yield": dividend_yield,
        "dy_medio": dy_medio,
        "ultimo_dividendo": ultimo_dividendo,
        "mes_ano_dividendo": mes_ano_dividendo,
        "termometro": termometro,
        "indices": {
            "cdi": getattr(indices, "cdi", None),
            "ipca": getattr(indices, "ipca", None),
        },
    }, indent=2, ensure_ascii=False))


def render_fii(ticker, cotacao, tetos, indices, termometro=None, nome=None,
               ultimo_dividendo=None, mes_ano_dividendo=None, dy_mensal=None):
    print(json.dumps({
        "ticker": ticker,
        "nome": nome,
        "cotacao": cotacao,
        "tetos": tetos,
        "ultimo_dividendo": ultimo_dividendo,
        "mes_ano_dividendo": mes_ano_dividendo,
        "dy_mensal": dy_mensal,
        "termometro": termometro,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
    }, indent=2, ensure_ascii=False))


def render_etf(ticker, cotacao, tetos, indices, termometro=None, nome=None,
               p_fcf_agregado=None, peg_agregado=None, cobertura_p_fcf=None, cobertura_peg=None):
    print(json.dumps({
        "ticker": ticker,
        "nome": nome,
        "cotacao": cotacao,
        "tetos": tetos,
        "termometro": termometro,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
        "p_fcf_agregado": p_fcf_agregado,
        "peg_agregado": peg_agregado,
        "cobertura_p_fcf": cobertura_p_fcf,
        "cobertura_peg": cobertura_peg,
    }, indent=2, ensure_ascii=False))


def render_etfbr(data, tetos, indices, termometro=None):
    print(json.dumps({
        "ticker": data.ticker,
        "nome": data.nome,
        "cotacao": data.cotacao,
        "pl_cota": data.pl_cota,
        "premio_desconto_pct": data.premio_desconto_pct,
        "low_52": data.low_52,
        "high_52": data.high_52,
        "pl_total_mm": data.pl_total_mm,
        "taxa_adm_pct": data.taxa_adm_pct,
        "cotistas": data.cotistas,
        "cnpj": data.cnpj,
        "indice": data.indice,
        "tetos": tetos,
        "termometro": termometro,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
    }, indent=2, ensure_ascii=False))


def render_indices(br):
    print(json.dumps({
        "br": {"cdi": br.cdi, "ipca": br.ipca},
    }, indent=2))

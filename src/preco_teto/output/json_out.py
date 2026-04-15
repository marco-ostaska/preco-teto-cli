import json


def render_acao(ticker, cotacao, is_br, tetos, indices, termometro=None, nome=None):
    print(json.dumps({
        "ticker": ticker,
        "nome": nome,
        "cotacao": cotacao,
        "is_br": is_br,
        "tetos": tetos,
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


def render_etf(ticker, cotacao, tetos, indices, termometro=None, nome=None):
    print(json.dumps({
        "ticker": ticker,
        "nome": nome,
        "cotacao": cotacao,
        "tetos": tetos,
        "termometro": termometro,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
    }, indent=2, ensure_ascii=False))


def render_indices(br):
    print(json.dumps({
        "br": {"cdi": br.cdi, "ipca": br.ipca},
    }, indent=2))

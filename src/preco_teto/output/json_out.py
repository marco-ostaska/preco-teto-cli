import json


def render_acao(ticker, cotacao, is_br, tetos, indices):
    print(json.dumps({
        "ticker": ticker,
        "cotacao": cotacao,
        "is_br": is_br,
        "tetos": tetos,
        "indices": {
            "cdi": getattr(indices, "cdi", None),
            "ipca": getattr(indices, "ipca", None),
        },
    }, indent=2, ensure_ascii=False))


def render_fii(ticker, cotacao, tetos, indices):
    print(json.dumps({
        "ticker": ticker,
        "cotacao": cotacao,
        "tetos": tetos,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
    }, indent=2, ensure_ascii=False))


def render_indices(br):
    print(json.dumps({
        "br": {"cdi": br.cdi, "ipca": br.ipca},
    }, indent=2))

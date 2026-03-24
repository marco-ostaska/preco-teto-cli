import json


def render_acao(ticker, cotacao, is_br, tetos, indices):
    print(json.dumps({
        "ticker": ticker,
        "cotacao": cotacao,
        "is_br": is_br,
        "tetos": tetos,
        "indices": {
            "selic": getattr(indices, "selic", None),
            "ipca": getattr(indices, "ipca", None),
            "juro_futuro": getattr(indices, "juro_futuro", None),
            "taxa_curto": getattr(indices, "taxa_curto", None),
            "taxa_longo": getattr(indices, "taxa_longo", None),
            "cpi": getattr(indices, "cpi", None),
        },
    }, indent=2, ensure_ascii=False))


def render_fii(ticker, cotacao, tetos, indices):
    print(json.dumps({
        "ticker": ticker,
        "cotacao": cotacao,
        "tetos": tetos,
        "indices": {"selic": indices.selic, "ipca": indices.ipca},
    }, indent=2, ensure_ascii=False))


def render_indices(br, us):
    print(json.dumps({
        "br": {"selic": br.selic, "ipca": br.ipca, "juro_futuro": br.juro_futuro},
        "us": {"taxa_curto": us.taxa_curto, "taxa_longo": us.taxa_longo, "cpi": us.cpi},
    }, indent=2))

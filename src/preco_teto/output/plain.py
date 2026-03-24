def _fmt(valor, is_br):
    if valor is None:
        return "—"
    m = "R$" if is_br else "$"
    return f"{m} {valor:.2f}"


def render_acao(ticker, cotacao, is_br, tetos, indices):
    moeda = "R$" if is_br else "$"
    print(f"{ticker}  {moeda} {cotacao:.2f}")
    print("-" * 46)
    for key, label in [
        ("teto_por_lucro", "Teto por Lucro"),
        ("teto_por_dy",    "Teto por DY"),
        ("teto_bazin",     "Teto Bazin"),
        ("teto_graham",    "Teto Graham"),
        ("teto_dcf",       "Teto DCF"),
    ]:
        v = tetos.get(key)
        mark = "OK" if (v and cotacao and v >= cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, is_br):>12}  {mark}")
    print("-" * 46)
    if is_br:
        print(f"CDI: {indices.cdi}%  IPCA: {indices.ipca}%")
    else:
        print(f"Fed Funds: {indices.fed_funds}%  CPI: {indices.cpi}%")


def render_fii(ticker, cotacao, tetos, indices):
    print(f"{ticker}  R$ {cotacao:.2f}")
    print("-" * 46)
    for key, label in [("teto_por_dy", "Teto por DY"), ("vpa", "VPA")]:
        v = tetos.get(key)
        mark = "OK" if (v and cotacao and v >= cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, True):>12}  {mark}")


def render_indices(br):
    print(f"CDI:   {br.cdi}%")
    print(f"IPCA:  {br.ipca}%")

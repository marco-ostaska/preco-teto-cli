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
        print(f"IPCA: {indices.ipca}%  CDI: {indices.selic}%")
    else:
        print(f"TLT: {indices.taxa_longo}%  CPI: {indices.cpi}%")


def render_fii(ticker, cotacao, tetos, indices):
    print(f"{ticker}  R$ {cotacao:.2f}")
    print("-" * 46)
    for key, label in [("teto_por_dy", "Teto por DY"), ("vpa", "VPA")]:
        v = tetos.get(key)
        mark = "OK" if (v and cotacao and v >= cotacao) else "X" if v else ""
        print(f"{label:<30} {_fmt(v, True):>12}  {mark}")


def render_indices(br, us):
    print("BR")
    print(f"  CDI:         {br.selic}%")
    print(f"  IPCA:        {br.ipca}%")
    print(f"  Juro Futuro: {br.juro_futuro}%")
    print("US")
    print(f"  TFLO:  {us.taxa_curto}%")
    print(f"  TLT:   {us.taxa_longo}%")
    print(f"  CPI:   {us.cpi}%")

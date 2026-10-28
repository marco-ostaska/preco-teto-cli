def formatar_valor(valor: float | None, is_br: bool) -> str:
    if valor is None:
        return "—"

    moeda = "R$" if is_br else "$"
    absoluto = abs(valor)
    if absoluto >= 1_000_000_000:
        return f"{moeda} {valor / 1_000_000_000:.2f} bi"
    if absoluto >= 1_000_000:
        return f"{moeda} {valor / 1_000_000:.2f} mi"
    return f"{moeda} {valor:.2f}"


def linhas(alavancagem: dict | None, is_br: bool) -> list[str]:
    if not alavancagem:
        return ["Alavancagem: Indisponível"]

    linhas = [f"Alavancagem: {alavancagem.get('status') or 'Indisponível'}"]
    valores = []
    if alavancagem.get("divida_total") is not None:
        valores.append(f"Dívida: {formatar_valor(alavancagem['divida_total'], is_br)}")
    if alavancagem.get("caixa") is not None:
        valores.append(f"Caixa: {formatar_valor(alavancagem['caixa'], is_br)}")
    if alavancagem.get("divida_liquida") is not None:
        valores.append(f"Dívida líquida: {formatar_valor(alavancagem['divida_liquida'], is_br)}")
    if valores:
        linhas.append("   ".join(valores))

    ratios = []
    if alavancagem.get("divida_sobre_patrimonio") is not None:
        ratios.append(f"Dívida/PL: {alavancagem['divida_sobre_patrimonio']:.2f}x")
    if alavancagem.get("divida_liquida_sobre_ebitda") is not None:
        ratios.append(f"Dívida líquida/EBITDA: {alavancagem['divida_liquida_sobre_ebitda']:.2f}x")
    if ratios:
        linhas.append("   ".join(ratios))
    return linhas

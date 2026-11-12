from datetime import date


def _trimestre(ref: date) -> str:
    return f"{(ref.month - 1) // 3 + 1}T{ref.year}"


def linha(fundamentos: dict | None) -> str | None:
    """Referência dos fundamentos vindos do Yahoo e aviso de defasagem pós-balanço."""
    if not fundamentos:
        return None
    ref = fundamentos.get("ref")
    if ref is None:
        return None

    texto = f"Dados: {_trimestre(ref)} ({ref:%d/%m/%Y})"
    balanco = fundamentos.get("balanco")
    if fundamentos.get("defasado") and balanco is not None:
        texto += f"   ⚠ Yahoo ainda sem o balanço de {balanco:%d/%m/%Y}"
    return texto

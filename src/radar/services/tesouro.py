from datetime import datetime, timedelta
import requests


_TESOURO_URL = (
    "https://www.tesourodireto.com.br/json/br/com/b3/tesouro/security/search/SearchApiService.json"
)


def fetch_juro_futuro() -> float | None:
    """
    Retorna taxa do Tesouro Prefixado com vencimento mais próximo de 2 anos.
    Retorna % (ex: 13.10). None se falhar.
    """
    try:
        resp = requests.get(_TESOURO_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        titulos = data["response"]["TrsrBdTradgList"]

        alvo = datetime.now() + timedelta(days=730)
        prefixados = [
            t["TrsrBd"] for t in titulos
            if "Prefixado" in t["TrsrBd"].get("nm", "")
            and "Juros" not in t["TrsrBd"].get("nm", "")
        ]
        if not prefixados:
            return None

        mais_proximo = min(
            prefixados,
            key=lambda t: abs(
                datetime.fromisoformat(t["mtrtyDt"].replace("T00:00:00", "")) - alvo
            ),
        )
        return float(mais_proximo["anulInvstmtRate"])
    except Exception:
        return None

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import requests
import pandas as pd

_CVM_CADASTRO_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"
_CACHE_DIR = Path.home() / ".cache" / "preco-teto" / "cvm"
_TTL = timedelta(days=1)


def _cache_path() -> Path:
    return _CACHE_DIR / "cad_fi.csv"


def _is_stale(path: Path) -> bool:
    if not path.exists():
        return True
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age > _TTL


def _download() -> bytes:
    resp = requests.get(_CVM_CADASTRO_URL, timeout=30)
    resp.raise_for_status()
    return resp.content


def _load_csv() -> pd.DataFrame:
    path = _cache_path()
    if _is_stale(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_download())
    return pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)


@dataclass
class FundInfo:
    cnpj: str
    nome: str
    classe_anbima: str
    taxa_adm: float | None      # % a.a., e.g. 0.20
    taxa_perf: float | None     # % or None
    gestor: str
    pl: float | None            # R$ absolute value
    cotistas: int | None


def _parse_float(value: str | float | None) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "nan", "NaN", "None"):
        return None
    try:
        return float(s.replace(",", "."))
    except (ValueError, TypeError):
        return None


def buscar_fundo(cnpj: str) -> FundInfo:
    """Retorna FundInfo para o CNPJ ou lança ValueError."""
    df = _load_csv()
    row = df[df["CNPJ_FUNDO"] == cnpj]
    if row.empty:
        raise ValueError(f"Fundo {cnpj} não encontrado no cadastro CVM.")
    row = row.iloc[0]
    sit = str(row.get("SIT", "")).strip()
    if sit != "EM FUNCIONAMENTO NORMAL":
        raise ValueError(
            f"Fundo {cnpj} não está EM FUNCIONAMENTO NORMAL (situação: {sit!r})."
        )
    cotistas_raw = _parse_float(row.get("NR_COTST"))
    return FundInfo(
        cnpj=cnpj,
        nome=str(row.get("DENOM_SOCIAL", "")).strip(),
        classe_anbima=str(row.get("CLASSE_ANBIMA", "")).strip(),
        taxa_adm=_parse_float(row.get("TAXA_ADM")),
        taxa_perf=_parse_float(row.get("TAXA_PERFM")),
        gestor=str(row.get("GESTOR", "")).strip(),
        pl=_parse_float(row.get("VL_PATRIM_LIQ")),
        cotistas=int(cotistas_raw) if cotistas_raw is not None else None,
    )

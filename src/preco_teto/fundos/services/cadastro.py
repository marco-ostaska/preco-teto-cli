from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import io
import zipfile
import requests
import pandas as pd

_CVM_CADASTRO_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"
_CVM_REGISTRO_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
_CVM_EXTRATO_URL = "https://dados.cvm.gov.br/dados/FI/DOC/EXTRATO/DADOS/extrato_fi.csv"
_TTL = timedelta(days=1)


def _cache_path() -> Path:
    return Path.home() / ".cache" / "preco-teto" / "cvm" / "cad_fi.csv"


def _registro_cache_path() -> Path:
    return Path.home() / ".cache" / "preco-teto" / "cvm" / "registro_fundo_classe.zip"


def _extrato_cache_path() -> Path:
    return Path.home() / ".cache" / "preco-teto" / "cvm" / "extrato_fi.csv"


def _is_stale(path: Path) -> bool:
    if not path.exists():
        return True
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age > _TTL


def _download() -> bytes:
    resp = requests.get(_CVM_CADASTRO_URL, timeout=30)
    resp.raise_for_status()
    return resp.content


def _download_registro() -> bytes:
    resp = requests.get(_CVM_REGISTRO_URL, timeout=30)
    resp.raise_for_status()
    return resp.content


def _download_extrato() -> bytes:
    resp = requests.get(_CVM_EXTRATO_URL, timeout=30)
    resp.raise_for_status()
    return resp.content


def _load_csv() -> pd.DataFrame:
    path = _cache_path()
    if _is_stale(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_download())
    return pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)


def _load_registro_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = _registro_cache_path()
    if _is_stale(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_download_registro())

    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as zf:
        with zf.open("registro_classe.csv") as classe_file:
            classe_df = pd.read_csv(classe_file, sep=";", encoding="latin-1", dtype=str)
        with zf.open("registro_fundo.csv") as fundo_file:
            fundo_df = pd.read_csv(fundo_file, sep=";", encoding="latin-1", dtype=str)
    return classe_df, fundo_df


def _load_extrato() -> pd.DataFrame:
    path = _extrato_cache_path()
    if _is_stale(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_download_extrato())
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


def _normalize_cnpj(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def _prefer_active_row(df: pd.DataFrame, status_col: str, active_status: str) -> pd.Series:
    normalized = df[status_col].fillna("").astype(str).str.strip().str.lower()
    active_matches = df[normalized == active_status.strip().lower()]
    if not active_matches.empty:
        return active_matches.iloc[0]
    return df.iloc[0]


def _prefer_latest_row(df: pd.DataFrame, date_col: str) -> pd.Series:
    dates = pd.to_datetime(df[date_col], errors="coerce")
    if dates.notna().any():
        return df.loc[dates.idxmax()]
    return df.iloc[0]


def _buscar_no_extrato(cnpj: str) -> FundInfo | None:
    df = _load_extrato()
    cnpj_digits = _normalize_cnpj(cnpj)
    matches = df["CNPJ_FUNDO_CLASSE"].fillna("").map(_normalize_cnpj) == cnpj_digits
    row = df[matches]
    if row.empty:
        return None

    extrato_row = _prefer_latest_row(row, "DT_COMPTC")
    return FundInfo(
        cnpj=cnpj,
        nome=str(extrato_row.get("DENOM_SOCIAL", "")).strip(),
        classe_anbima=str(extrato_row.get("CLASSE_ANBIMA", "")).strip(),
        taxa_adm=_parse_float(extrato_row.get("TAXA_ADM")),
        taxa_perf=_parse_float(extrato_row.get("TAXA_PERFM")),
        gestor="",
        pl=_parse_float(extrato_row.get("VL_PATRIM_LIQ")),
        cotistas=None,
    )


def _buscar_no_cadastro_legado(cnpj: str) -> FundInfo | None:
    df = _load_csv()
    cnpj_digits = _normalize_cnpj(cnpj)
    matches = df["CNPJ_FUNDO"].fillna("").map(_normalize_cnpj) == cnpj_digits
    row = df[matches]
    if row.empty:
        return None

    row = _prefer_active_row(row, "SIT", "EM FUNCIONAMENTO NORMAL")
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


def _buscar_no_registro_classe(cnpj: str) -> FundInfo | None:
    classe_df, fundo_df = _load_registro_frames()
    cnpj_digits = _normalize_cnpj(cnpj)
    classe_matches = classe_df["CNPJ_Classe"].fillna("").map(_normalize_cnpj) == cnpj_digits
    row = classe_df[classe_matches]
    if row.empty:
        return None

    classe_row = _prefer_active_row(row, "Situacao", "Em Funcionamento Normal")
    situacao = str(classe_row.get("Situacao", "")).strip()
    if situacao.lower() != "em funcionamento normal":
        raise ValueError(
            f"Fundo {cnpj} não está EM FUNCIONAMENTO NORMAL (situação: {situacao!r})."
        )

    fundo_row = pd.Series(dtype=object)
    fundo_id = str(classe_row.get("ID_Registro_Fundo", "")).strip()
    if fundo_id:
        fundo_match = fundo_df[fundo_df["ID_Registro_Fundo"].fillna("").astype(str).str.strip() == fundo_id]
        if not fundo_match.empty:
            fundo_row = fundo_match.iloc[0]

    gestor = str(fundo_row.get("Gestor", "")).strip() or str(fundo_row.get("Administrador", "")).strip()

    return FundInfo(
        cnpj=cnpj,
        nome=str(classe_row.get("Denominacao_Social", "")).strip(),
        classe_anbima=str(classe_row.get("Classificacao_Anbima", "")).strip(),
        taxa_adm=None,
        taxa_perf=None,
        gestor=gestor,
        pl=_parse_float(classe_row.get("Patrimonio_Liquido")),
        cotistas=None,
    )


def buscar_fundo(cnpj: str) -> FundInfo:
    """Retorna FundInfo para o CNPJ ou lança ValueError."""
    extrato_error: ValueError | None = None
    try:
        info = _buscar_no_extrato(cnpj)
    except ValueError as exc:
        extrato_error = exc
        info = None
    if info is not None:
        return info

    legado_error: ValueError | None = None
    registro_error: ValueError | None = None

    try:
        info = _buscar_no_registro_classe(cnpj)
    except ValueError as exc:
        registro_error = exc
        info = None
    if info is not None:
        return info

    try:
        info = _buscar_no_cadastro_legado(cnpj)
    except ValueError as exc:
        legado_error = exc
        info = None
    if info is not None:
        return info

    if extrato_error is not None:
        raise extrato_error
    if registro_error is not None:
        raise registro_error
    if legado_error is not None:
        raise legado_error

    raise ValueError(f"Fundo {cnpj} não encontrado no cadastro CVM.")

from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
import io
import zipfile
import requests
import pandas as pd

_CVM_DIARIO_BASE = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"


def _today() -> date:
    return date.today()


def _cache_dir() -> Path:
    return Path.home() / ".cache" / "preco-teto" / "cvm"


def _zip_filename(year: int, month: int) -> str:
    return f"inf_diario_fi_{year}{month:02d}.zip"


def _zip_url(year: int, month: int) -> str:
    return f"{_CVM_DIARIO_BASE}/{_zip_filename(year, month)}"


def _is_stale(path: Path, ttl: timedelta) -> bool:
    if not path.exists():
        return True
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age > ttl


def _download_zip(year: int, month: int) -> bytes:
    resp = requests.get(_zip_url(year, month), timeout=60)
    resp.raise_for_status()
    return resp.content


def _load_zip(year: int, month: int, cache_dir: Path, today: date) -> bytes:
    filename = _zip_filename(year, month)
    path = cache_dir / filename
    is_current_month = (year == today.year and month == today.month)
    ttl = timedelta(days=1) if is_current_month else timedelta(days=36500)

    if _is_stale(path, ttl):
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = _download_zip(year, month)
        path.write_bytes(data)
    return path.read_bytes()


def _parse_zip(zip_bytes: bytes, cnpj: str) -> pd.DataFrame:
    buf = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(buf) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        with zf.open(csv_name) as f:
            df = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)
    col = "CNPJ_FUNDO_CLASSE"
    if col not in df.columns:
        return pd.DataFrame(columns=["DT_COMPTC", "VL_QUOTA"])
    df = df[df[col] == cnpj][["DT_COMPTC", "VL_QUOTA"]].copy()
    df["VL_QUOTA"] = pd.to_numeric(df["VL_QUOTA"].str.replace(",", "."), errors="coerce")
    df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"], errors="coerce")
    return df.dropna().reset_index(drop=True)


def extrair_cotas(cnpj: str, meses: int = 36) -> pd.DataFrame:
    """
    Retorna DataFrame [DT_COMPTC, VL_QUOTA] com cotas diárias dos últimos `meses` meses.
    Lança ValueError se o CNPJ não for encontrado em nenhum ZIP.
    """
    today = _today()
    cache_dir = _cache_dir()
    frames: list[pd.DataFrame] = []

    for i in range(meses):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        try:
            print(f"\rBaixando dados CVM: {i+1}/{meses} meses...", end="", flush=True)
            zip_bytes = _load_zip(year, month, cache_dir, today)
            df = _parse_zip(zip_bytes, cnpj)
            if not df.empty:
                frames.append(df)
        except Exception:
            pass  # month not available yet, skip

    print()  # newline after progress
    if not frames:
        raise ValueError(f"Fundo {cnpj} sem dados de cotas na CVM.")

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values("DT_COMPTC").reset_index(drop=True)
    return result

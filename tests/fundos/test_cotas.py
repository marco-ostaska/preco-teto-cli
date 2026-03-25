import io
import zipfile
import pandas as pd
import pytest
from unittest.mock import patch
from preco_teto.fundos.services.cotas import extrair_cotas, _zip_url, _zip_filename

CNPJ = "26.199.519/0001-34"

CSV_CONTENT = (
    "CNPJ_FUNDO_CLASSE;DT_COMPTC;VL_QUOTA\n"
    f"{CNPJ};2024-01-02;10.500000\n"
    f"{CNPJ};2024-01-03;10.510000\n"
    "99.999.999/0001-00;2024-01-02;5.000000\n"
)


def _make_zip(csv_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("inf_diario_fi_202401.csv", csv_bytes)
    return buf.getvalue()


def test_zip_url_format():
    url = _zip_url(2024, 1)
    assert "inf_diario_fi_202401.zip" in url
    assert url.startswith("https://dados.cvm.gov.br")


def test_zip_filename():
    assert _zip_filename(2024, 1) == "inf_diario_fi_202401.zip"


def test_extrair_cotas_filtra_cnpj(tmp_path, monkeypatch):
    zip_bytes = _make_zip(CSV_CONTENT.encode("latin-1"))

    monkeypatch.setattr(
        "preco_teto.fundos.services.cotas._cache_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "preco_teto.fundos.services.cotas._download_zip",
        lambda year, month: zip_bytes,
    )

    from datetime import date
    with patch("preco_teto.fundos.services.cotas._today", return_value=date(2024, 2, 1)):
        df = extrair_cotas(CNPJ, meses=1)

    assert list(df.columns) == ["DT_COMPTC", "VL_QUOTA"]
    assert len(df) == 2


def test_extrair_cotas_cnpj_nao_encontrado(tmp_path, monkeypatch):
    csv = "CNPJ_FUNDO_CLASSE;DT_COMPTC;VL_QUOTA\n99.999.999/0001-00;2024-01-02;5.0\n"
    zip_bytes = _make_zip(csv.encode("latin-1"))

    monkeypatch.setattr("preco_teto.fundos.services.cotas._cache_dir", lambda: tmp_path)
    monkeypatch.setattr("preco_teto.fundos.services.cotas._download_zip", lambda y, m: zip_bytes)

    from datetime import date
    with patch("preco_teto.fundos.services.cotas._today", return_value=date(2024, 2, 1)):
        with pytest.raises(ValueError, match="sem dados de cotas"):
            extrair_cotas("26.199.519/0001-34", meses=1)

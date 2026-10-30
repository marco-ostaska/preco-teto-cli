import pytest
from types import SimpleNamespace

from preco_teto.output import plain, tabela


def _indices():
    return SimpleNamespace(cdi=10.0, ipca=4.0, melhor_indice=8.0)


def test_plain_render_acao_starts_with_two_blank_lines(capsys):
    plain.render_acao(
        "VALE3",
        58.20,
        True,
        {},
        _indices(),
    )

    assert capsys.readouterr().out.startswith("\n\nVALE3")


def test_tabela_render_acao_starts_with_two_blank_lines(monkeypatch):
    capturados = []
    monkeypatch.setattr(tabela.console, "print", lambda obj="", **kwargs: capturados.append(obj))

    tabela.render_acao("VALE3", 58.20, True, {}, _indices())

    assert capturados[:2] == ["", ""]

TETOS_ACAO = {
    "teto_por_lucro": 9.0,
    "teto_por_dy": 8.0,
    "teto_bazin": 2.0,
    "teto_graham": 11.0,
    "teto_dcf": None,
    "teto_vpa_roe_taxa": 7.0,
    "teto_vpa_roe_inflacao": 30.0,
    "teto_margem": 6.0,
}

TETOS_FII = {
    "teto_por_dy": 80.0,
    "teto_por_dy_cdi_12m": 100.0,
    "teto_bazin": 120.0,
    "vpa": 300.0,
    "teto_margem": 120.0,
}


def _console(monkeypatch):
    import io

    from rich.console import Console

    buf = io.StringIO()
    monkeypatch.setattr(
        tabela, "console", Console(file=buf, width=140, force_terminal=False)
    )
    return buf

def test_tabela_render_acao_sem_coluna_preco_potencial(monkeypatch):
    buf = _console(monkeypatch)
    tabela.render_acao("KEPL3", 6.42, True, TETOS_ACAO, _indices())

    texto = buf.getvalue()
    assert "Preço Potencial" not in texto
    # a coluna derivada saiu, os tetos continuam
    assert texto.count("R$ 9.00") == 1
    assert "R$ 12.62" not in texto
    assert "R$ 140.19" not in texto


def test_tabela_render_acao_sem_tetos_nao_quebra(monkeypatch):
    buf = _console(monkeypatch)
    tabela.render_acao("KEPL3", 6.42, True, {}, _indices())

    texto = buf.getvalue()
    assert "Preço Potencial" not in texto
    assert "R$ 0.00" not in texto


def test_tabela_render_fii_sem_coluna_preco_potencial(monkeypatch):
    buf = _console(monkeypatch)
    tabela.render_fii("HGLG11", 100.0, TETOS_FII, _indices())

    texto = buf.getvalue()
    assert "Preço Potencial" not in texto
    # tetos continuam: 80, 100, 120, 300, 120
    assert texto.count("R$ 120.00") == 2
    assert texto.count("R$ 300.00") == 1
    assert "R$ 144.00" not in texto
    assert "R$ 900.00" not in texto


def test_plain_render_acao_sem_coluna_preco_potencial(capsys):
    plain.render_acao("KEPL3", 6.42, True, TETOS_ACAO, _indices())

    out = capsys.readouterr().out
    assert "Preço Potencial" not in out
    linha = next(l for l in out.splitlines() if l.startswith("Teto por Lucro"))
    assert "R$ 9.00" in linha
    assert "R$ 12.62" not in linha


def test_plain_render_fii_sem_coluna_preco_potencial(capsys):
    plain.render_fii("HGLG11", 100.0, TETOS_FII, _indices())

    out = capsys.readouterr().out
    assert "Preço Potencial" not in out
    val = next(l for l in out.splitlines() if l.startswith("VPA"))
    assert "R$ 300.00" in val
    assert "R$ 900.00" not in out


def test_json_render_acao_nao_expoe_preco_potencial(capsys):
    import json as _json

    from preco_teto.output import json_out

    json_out.render_acao("KEPL3", 6.42, True, TETOS_ACAO, _indices())

    payload = _json.loads(capsys.readouterr().out)
    assert "preco_potencial" not in payload
    assert payload["tetos"]["teto_por_lucro"] == 9.0


def test_json_render_fii_nao_expoe_preco_potencial(capsys):
    import json as _json

    from preco_teto.output import json_out

    json_out.render_fii("HGLG11", 100.0, TETOS_FII, _indices())

    payload = _json.loads(capsys.readouterr().out)
    assert "preco_potencial" not in payload
    assert payload["tetos"]["teto_bazin"] == 120.0


# --- câmbio USD/BRL ---


def _usd_data():
    from datetime import date

    return SimpleNamespace(
        spot=5.3744,
        data_spot=date(2026, 10, 29),
        low_52=4.8973,
        high_52=5.5739,
        margem_52=0.71,
        ptax=None,
        dxy=102.04,
        dxy_pctl=55.0,
        cot=SimpleNamespace(
            data=date(2026, 10, 20),
            lev_net_pct=13.8,
            am_net_pct=37.8,
            lev_pctl=81.0,
            am_pctl=48.0,
        ),
        k_hat=0.00106,
        ibov=169186.0,
        ewz=33.14,
        desvio_z=1.02,
        uup=(29.04, 29.04),
        udn=(17.82, 17.81),
    )


TETOS_USD = {
    "teto_margem": 5.05,
    "teto_carrego": 5.87,
    "teto_ewz": 5.33,
    "teto_dxy": 5.28,
    "teto_cot": 5.28,
}


def test_tabela_render_usd_mostra_linhas_r2_e_rodape(monkeypatch):
    buf = _console(monkeypatch)
    tabela.render_usd(_usd_data(), TETOS_USD, _indices(), r2_dxy=0.06, r2_cot=0.18)

    texto = buf.getvalue()
    assert "USD/BRL" in texto
    assert "Preço Potencial" not in texto
    assert "R$ 5.87" in texto
    # R² das linhas fracas fica visível para não sugerir precisão
    assert texto.count("R²") == 2
    assert "R² 0.06" in texto
    assert "R² 0.18" in texto
    assert "Termômetro: Neutro" in texto
    assert "COT BRL" in texto
    assert "CDI: 10.0%" in texto


def test_tabela_render_usd_sem_cot_nao_quebra(monkeypatch):
    buf = _console(monkeypatch)
    data = _usd_data()
    data.cot = None
    data.desvio_z = None

    tabela.render_usd(data, {}, _indices())

    texto = buf.getvalue()
    assert "USD/BRL" in texto
    assert "COT" not in texto


def test_plain_render_usd_sem_coluna_preco_potencial(capsys):
    plain.render_usd(_usd_data(), TETOS_USD, _indices(), r2_dxy=0.06, r2_cot=0.18)

    out = capsys.readouterr().out
    assert out.startswith("\n\n")
    assert "Preço Potencial" not in out
    linha = next(l for l in out.splitlines() if l.startswith("Teto Carrego"))
    assert "R$ 5.87" in linha
    assert "Termômetro: Neutro" in out


def test_json_render_usd_exibe_tetos_e_indicadores(capsys):
    import json as _json

    from preco_teto.output import json_out

    json_out.render_usd(_usd_data(), TETOS_USD, _indices(), r2_dxy=0.06, r2_cot=0.18)

    payload = _json.loads(capsys.readouterr().out)
    assert payload["moeda"] == "BRL"
    assert payload["spot"] == pytest.approx(5.3744)
    assert payload["tetos"]["teto_carrego"] == pytest.approx(5.87)
    assert payload["regressao"]["r2_dxy"] == pytest.approx(0.06)
    assert payload["cot"]["lev_pctl"] == pytest.approx(81.0)
    assert payload["termometro"] == "Neutro"


def test_render_usd_nao_rotula_dxy_como_percentil(monkeypatch):
    """O teto DXY ancora no DXY de hoje, não num percentil histórico."""
    buf = _console(monkeypatch)
    tabela.render_usd(_usd_data(), TETOS_USD, _indices(), r2_dxy=0.13, r2_cot=0.17)

    assert "p25" not in buf.getvalue()


def test_plain_render_usd_rotula_dxy_e_cot_coerentes(capsys):
    plain.render_usd(_usd_data(), TETOS_USD, _indices(), r2_dxy=0.13, r2_cot=0.17)

    out = capsys.readouterr().out
    assert "Teto DXY (hoje)" in out
    assert "Teto COT (26 sem)" in out
    assert "p25" not in out

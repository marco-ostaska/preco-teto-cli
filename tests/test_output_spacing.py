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

def test_tabela_render_acao_tem_coluna_preco_potencial(monkeypatch):
    buf = _console(monkeypatch)
    tabela.render_acao("KEPL3", 6.42, True, TETOS_ACAO, _indices())

    texto = buf.getvalue()
    assert "Preço Potencial" in texto
    # por linha: valor + o potencial da própria linha (R$ 9.00 +40.19% -> 12.62)
    assert texto.count("R$ 12.62") == 1
    assert texto.count("R$ 9.97") == 1
    assert texto.count("R$ 140.19") == 1
    assert "R$ 10.43" not in texto


def test_tabela_render_acao_sem_tetos_nao_quebra(monkeypatch):
    buf = _console(monkeypatch)
    tabela.render_acao("KEPL3", 6.42, True, {}, _indices())

    texto = buf.getvalue()
    assert "Preço Potencial" in texto
    assert "R$ 0.00" not in texto


def test_tabela_render_fii_tem_coluna_preco_potencial(monkeypatch):
    buf = _console(monkeypatch)
    tabela.render_fii("HGLG11", 100.0, TETOS_FII, _indices())

    texto = buf.getvalue()
    assert "Preço Potencial" in texto
    # 80 +(-20%) -> 64.00 | 120 +20% -> 144.00 | VPA 300 +200% -> 900.00
    assert texto.count("R$ 64.00") == 1
    assert texto.count("R$ 144.00") == 2
    assert texto.count("R$ 900.00") == 1


def test_plain_render_acao_tem_coluna_preco_potencial(capsys):
    plain.render_acao("KEPL3", 6.42, True, TETOS_ACAO, _indices())

    out = capsys.readouterr().out
    assert "Preço Potencial" in out
    linha = next(l for l in out.splitlines() if l.startswith("Teto por Lucro"))
    assert "R$ 9.00" in linha
    assert "R$ 12.62" in linha


def test_plain_render_fii_tem_coluna_preco_potencial(capsys):
    plain.render_fii("HGLG11", 100.0, TETOS_FII, _indices())

    out = capsys.readouterr().out
    val = next(l for l in out.splitlines() if l.startswith("VPA"))
    assert "R$ 900.00" in val


def test_json_render_acao_exibe_preco_potencial(capsys):
    import json as _json

    from preco_teto.output import json_out

    json_out.render_acao("KEPL3", 6.42, True, TETOS_ACAO, _indices())

    payload = _json.loads(capsys.readouterr().out)
    assert payload["preco_potencial"]["teto_por_lucro"] == 12.62
    assert payload["preco_potencial"]["teto_vpa_roe_inflacao"] == 140.19
    assert payload["preco_potencial"]["teto_dcf"] is None


def test_json_render_fii_exibe_preco_potencial(capsys):
    import json as _json

    from preco_teto.output import json_out

    json_out.render_fii("HGLG11", 100.0, TETOS_FII, _indices())

    payload = _json.loads(capsys.readouterr().out)
    assert payload["preco_potencial"]["teto_por_dy"] == 64.00
    assert payload["preco_potencial"]["teto_bazin"] == 144.00

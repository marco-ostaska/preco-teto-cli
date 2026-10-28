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

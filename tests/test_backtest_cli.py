"""CLI / argv router tests for predictive backtest — no network."""
import sys

from typer.testing import CliRunner

from preco_teto.cli import app, entry, quote_app
from preco_teto.backtest.cli import app as backtest_app
from preco_teto.backtest.metrics import PredictiveMeta, PredictiveReport
from preco_teto.backtest.predictive import BucketBlock, HorizonBucketStats, SpearmanRow


runner = CliRunner()


def _fake_report():
    meta = PredictiveMeta(
        ticker="VALE3",
        is_br=True,
        lag_days=90,
        cascade=False,
        benchmark="^BVSP",
        date_start="2019-01-02",
        date_end="2024-01-02",
        n_weeks_with_teto=10,
        income_years=4,
    )
    block = BucketBlock(bucket="<=0.80", n_bars=5, n_episodes=2)
    for h in (3, 6, 12, 24):
        block.by_horizon[h] = HorizonBucketStats(
            horizon_months=h,
            n_bars=5,
            n_episodes=2,
            mean=0.1,
            median=0.08,
            win_rate=0.6,
            mfe_mean=0.2,
            mae_mean=-0.1,
            excess_ibov_mean=0.05,
            excess_ibov_median=0.04,
        )
    return PredictiveReport(
        meta=meta,
        buckets=[block],
        spearman=[SpearmanRow(horizon_months=3, n=5, rho=-0.2, pvalue=0.5)],
        ni_sticky=[],
        observations=[],
    )


def test_cli_quote_vale3_still_works_via_app_alias(mocker):
    from types import SimpleNamespace

    data = SimpleNamespace(
        ticker="VALE3",
        nome="Vale S.A.",
        is_br=True,
        cotacao=58.20,
        dividend_rate=3.60,
        dividend_yield=6.19,
        dy_medio=24.74,
        dividendo_medio=3.60,
        lpa=5.50,
        vpa=32.00,
        free_cashflow=15_000_000_000,
        shares_outstanding=1_300_000_000,
        beta=0.95,
        earnings_growth=0.12,
        revenue_growth=0.08,
        roe=17.12,
        roe_medio_5a=16.0,
        roe_tendencia=-1.0,
        roe_r2=0.9,
        roe_ajustado=15.0,
        income_net=None,
        year_prices={},
        previous_close=57.80,
        low_52=20.0,
        high_52=60.0,
        ultimo_dividendo=0.30,
        mes_ano_dividendo="Dez/2024",
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()
    mocker.patch("preco_teto.cli.fetch_acao", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    assert app is quote_app
    result = runner.invoke(app, ["VALE3"])
    assert result.exit_code == 0
    assert renderer.render_acao.called


def test_cli_backtest_subcommand_routes(mocker):
    report = _fake_report()
    mocker.patch("preco_teto.backtest.cli.run_backtest", return_value=report)
    renderer = mocker.Mock()
    mocker.patch("preco_teto.backtest.cli._get_renderer", return_value=renderer)
    result = runner.invoke(backtest_app, ["VALE3"])
    assert result.exit_code == 0
    renderer.render_backtest.assert_called_once()


def test_cli_argv_router_backtest_before_ticker_detection(mocker):
    called = {}

    def fake_bt():
        called["backtest"] = True

    mocker.patch("preco_teto.backtest.cli.app", fake_bt)
    mocker.patch.object(sys, "argv", ["preco-teto", "backtest", "VALE3"])
    entry()
    assert called.get("backtest") is True


def test_cli_backtest_no_signals_renders_without_error(mocker):
    mocker.patch("preco_teto.backtest.cli.run_backtest", return_value=_fake_report())
    result = runner.invoke(backtest_app, ["VALE3", "--plain"])
    assert result.exit_code == 0
    assert "Poder preditivo" in result.stdout


def test_cli_backtest_json_flag_uses_renderer(mocker):
    mocker.patch("preco_teto.backtest.cli.run_backtest", return_value=_fake_report())
    result = runner.invoke(backtest_app, ["VALE3", "--json"])
    assert result.exit_code == 0
    assert '"ticker": "VALE3"' in result.stdout
    assert '"mode": "predictive"' in result.stdout


def test_cli_backtest_cascade_flag_passed(mocker):
    mock_run = mocker.patch("preco_teto.backtest.cli.run_backtest", return_value=_fake_report())
    result = runner.invoke(backtest_app, ["PETR4", "--cascade"])
    assert result.exit_code == 0
    assert mock_run.call_args.kwargs.get("cascade") is True


def test_cli_rejects_fii_ticker():
    result = runner.invoke(backtest_app, ["HGLG11"])
    assert result.exit_code == 1
    assert "FII" in result.stdout or "ações" in result.stdout


def test_want_progress_off_for_json(mocker):
    from preco_teto.backtest.cli import _want_progress

    mocker.patch("preco_teto.backtest.cli.sys.stderr.isatty", return_value=True)
    assert _want_progress(True) is False
    assert _want_progress(False) is True

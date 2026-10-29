import json

from preco_teto.formulas import preco_potencial


def _precos_potenciais(tetos, cotacao):
    """Por modalidade: teto + o potencial da própria linha."""
    if not cotacao:
        return {k: None for k in tetos}
    return {
        k: preco_potencial(v, (v - cotacao) / cotacao * 100)
        if isinstance(v, (int, float)) else None
        for k, v in tetos.items()
    }


def render_acao(ticker, cotacao, is_br, tetos, indices, termometro=None, nome=None, dividend_yield=None, dy_medio=None, roe=None, roe_medio_5a=None, roe_tendencia=None, roe_r2=None, roe_ajustado=None, alavancagem=None, ultimo_dividendo=None, mes_ano_dividendo=None):
    precos_pot = _precos_potenciais(tetos, cotacao)
    print(json.dumps({
        "ticker": ticker,
        "nome": nome,
        "cotacao": cotacao,
        "is_br": is_br,
        "tetos": tetos,
        "preco_potencial": precos_pot,
        "dividend_yield": dividend_yield,
        "dy_medio": dy_medio,
        "roe": roe,
        "roe_medio_5a": roe_medio_5a,
        "roe_tendencia": roe_tendencia,
        "roe_r2": roe_r2,
        "roe_ajustado": roe_ajustado,
        "alavancagem": alavancagem,
        "ultimo_dividendo": ultimo_dividendo,
        "mes_ano_dividendo": mes_ano_dividendo,
        "termometro": termometro,
        "indices": {
            "cdi": getattr(indices, "cdi", None),
            "ipca": getattr(indices, "ipca", None),
        },
    }, indent=2, ensure_ascii=False))


def render_fii(ticker, cotacao, tetos, indices, termometro=None, nome=None,
               ultimo_dividendo=None, mes_ano_dividendo=None, dy_mensal=None,
               dividend_yield_12m=None):
    precos_pot = _precos_potenciais(tetos, cotacao)
    print(json.dumps({
        "ticker": ticker,
        "nome": nome,
        "cotacao": cotacao,
        "tetos": tetos,
        "preco_potencial": precos_pot,
        "ultimo_dividendo": ultimo_dividendo,
        "mes_ano_dividendo": mes_ano_dividendo,
        "dy_mensal": dy_mensal,
        "dividend_yield_12m": dividend_yield_12m,
        "termometro": termometro,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
    }, indent=2, ensure_ascii=False))


def render_etf(ticker, cotacao, tetos, indices, termometro=None, nome=None,
               p_fcf_agregado=None, peg_agregado=None, cobertura_p_fcf=None, cobertura_peg=None):
    print(json.dumps({
        "ticker": ticker,
        "nome": nome,
        "cotacao": cotacao,
        "tetos": tetos,
        "termometro": termometro,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
        "p_fcf_agregado": p_fcf_agregado,
        "peg_agregado": peg_agregado,
        "cobertura_p_fcf": cobertura_p_fcf,
        "cobertura_peg": cobertura_peg,
    }, indent=2, ensure_ascii=False))


def render_etfbr(data, tetos, indices, termometro=None):
    print(json.dumps({
        "ticker": data.ticker,
        "nome": data.nome,
        "cotacao": data.cotacao,
        "pl_cota": data.pl_cota,
        "premio_desconto_pct": data.premio_desconto_pct,
        "low_52": data.low_52,
        "high_52": data.high_52,
        "pl_total_mm": data.pl_total_mm,
        "taxa_adm_pct": data.taxa_adm_pct,
        "cotistas": data.cotistas,
        "cnpj": data.cnpj,
        "indice": data.indice,
        "tetos": tetos,
        "termometro": termometro,
        "indices": {"cdi": indices.cdi, "ipca": indices.ipca},
    }, indent=2, ensure_ascii=False))


def render_indices(br):
    print(json.dumps({
        "br": {"cdi": br.cdi, "ipca": br.ipca},
    }, indent=2))


def render_backtest(report):
    meta = report.meta

    def _bucket_horizon(block, h):
        s = (block.by_horizon or {}).get(h)
        if s is None:
            return None
        return {
            "n_bars": s.n_bars,
            "n_episodes": s.n_episodes,
            "mean": s.mean,
            "median": s.median,
            "win_rate": s.win_rate,
            "mfe_mean": s.mfe_mean,
            "mae_mean": s.mae_mean,
            "excess_ibov_mean": s.excess_ibov_mean,
            "excess_ibov_median": s.excess_ibov_median,
        }

    print(json.dumps({
        "mode": "predictive",
        "ticker": meta.ticker,
        "is_br": meta.is_br,
        "cascade": meta.cascade,
        "rule": "ratio buckets vs forward Adj returns; no trading/crossing",
        "cadence": "semanal",
        "lag_days": meta.lag_days,
        "benchmark": meta.benchmark,
        "date_start": meta.date_start,
        "date_end": meta.date_end,
        "n_weeks_with_teto": meta.n_weeks_with_teto,
        "income_years": meta.income_years,
        "ratio_min": meta.ratio_min,
        "ratio_median": meta.ratio_median,
        "notes": meta.notes,
        "ni_sticky": getattr(report, "ni_sticky", None) or [],
        "buckets": [
            {
                "bucket": b.bucket,
                "n_bars": b.n_bars,
                "n_episodes": b.n_episodes,
                "horizons": {
                    str(h): _bucket_horizon(b, h)
                    for h in sorted((b.by_horizon or {}).keys())
                },
            }
            for b in (report.buckets or [])
        ],
        "spearman": [
            {
                "horizon_months": r.horizon_months,
                "n": r.n,
                "rho": r.rho,
                "pvalue": r.pvalue,
            }
            for r in (report.spearman or [])
        ],
    }, indent=2, ensure_ascii=False))

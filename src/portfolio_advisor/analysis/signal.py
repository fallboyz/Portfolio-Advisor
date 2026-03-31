from __future__ import annotations

import hashlib
import json
from datetime import date

import pandas as pd


def compute_drawdown(prices_series: pd.Series, lookback_days: int = 252) -> float:
    if len(prices_series) < 2:
        return 0.0
    window = prices_series.tail(lookback_days)
    peak = float(window.max())
    if peak == 0:
        return 0.0
    current = float(prices_series.iloc[-1])
    return round((current - peak) / peak * 100, 2)


def compute_rally(prices_series: pd.Series, lookback_days: int = 126) -> float:
    if len(prices_series) < 2:
        return 0.0
    window = prices_series.tail(lookback_days)
    trough = float(window.min())
    if trough == 0:
        return 0.0
    current = float(prices_series.iloc[-1])
    return round((current - trough) / trough * 100, 2)


def apply_drawdown_overlay(
    s_precious: float,
    s_etf: float,
    dd_silver: float,
    dd_etf: float,
    rally_silver_6m: float,
    overlay_config: dict,
) -> tuple[float, float, float]:
    correction = 0.0
    silver_crash = overlay_config.get("silver_crash_threshold", -40)
    etf_crash = overlay_config.get("etf_crash_threshold", -30)
    silver_rally = overlay_config.get("silver_rally_threshold", 100)

    if dd_silver < silver_crash:
        s_precious -= 0.5
        correction -= 0.5
    if dd_etf < etf_crash:
        s_etf -= 0.5
        correction -= 0.5
    if rally_silver_6m > silver_rally:
        s_precious += 0.5
        correction += 0.5

    return round(s_precious, 4), round(s_etf, 4), round(correction, 4)


# ── 시그널 매핑 ─────────────────────────────────────────

SIGNAL_KO = {
    "strong_precious": {
        "label": "실물 자산 비중 대폭 확대",
        "desc": "실물 자산(금/은)이 역사적으로 크게 저평가된 구간. 실물 자산 비중을 크게 늘리는 게 유리.",
    },
    "mild_precious": {
        "label": "실물 자산 비중 확대",
        "desc": "실물 자산이 상대적으로 저평가. 실물 자산 쪽에 비중을 좀 더 두는 게 유리한 구간.",
    },
    "neutral": {
        "label": "균형 배분",
        "desc": "실물 자산과 ETF 모두 특별히 저평가/고평가 구간이 아님. 기본 비율(50:50) 유지.",
    },
    "mild_etf": {
        "label": "ETF 비중 확대",
        "desc": "ETF가 상대적으로 매력적. ETF 쪽에 비중을 좀 더 두는 게 유리한 구간.",
    },
    "strong_etf": {
        "label": "ETF 비중 대폭 확대",
        "desc": "실물 자산이 역사적으로 크게 고평가된 구간. ETF 비중을 크게 늘리는 게 유리.",
    },
}


def generate_group_signal(r_group: float, thresholds: dict) -> dict:
    """Level 1: 실물 자산 vs ETF 비율 신호."""
    strong_precious = thresholds.get("strong_precious", -2.0)
    mild_precious = thresholds.get("mild_precious", -1.0)
    mild_etf = thresholds.get("mild_etf", 1.0)
    strong_etf = thresholds.get("strong_etf", 2.0)

    if r_group < strong_precious:
        return {"label": "strong_precious", "precious_pct": 75}
    elif r_group < mild_precious:
        return {"label": "mild_precious", "precious_pct": 60}
    elif r_group < mild_etf:
        return {"label": "neutral", "precious_pct": 50}
    elif r_group < strong_etf:
        return {"label": "mild_etf", "precious_pct": 35}
    else:
        return {"label": "strong_etf", "precious_pct": 20}


def generate_comment(result: dict) -> str:
    """한국어 분석 코멘트 생성."""
    info = SIGNAL_KO.get(result["signal"]["label"], SIGNAL_KO["neutral"])
    precious_pct = result["signal"]["precious_pct"]
    etf_pct = 100 - precious_pct

    lines = []
    lines.append(f"[{info['label']}]")
    lines.append(f"  {info['desc']}")
    lines.append("")
    lines.append(f"  실물 자산 {precious_pct}% (금 {result['gold_pct']}% / 은 {result['silver_pct']}%)")
    lines.append(f"  ETF {etf_pct}% (S&P {result['sp500_pct']}% / 나스닥 {result['ndx_pct']}%)")
    lines.append("")
    lines.append(f"  그룹 R={result['r_group']:+.2f} / 실물 자산 점수={result['s_precious']:.2f} / ETF 점수={result['s_etf']:.2f}")

    return "\n".join(lines)


def compute_full_signal(
    store,
    config: dict,
    as_of_date: date | None = None,
) -> dict:
    """2단계 비율 조정: 그룹(실물 자산 vs ETF) + 내부(금/은, S&P/나스닥)."""
    from portfolio_advisor.analysis.composite import (
        compute_etf_composite,
        compute_gold_composite,
        compute_group_scores,
        compute_ndx_composite,
        compute_precious_split,
        compute_silver_composite,
        compute_etf_split,
    )
    from portfolio_advisor.analysis.zscore import compute_all_zscores

    calc_date = as_of_date or date.today()
    weights = config.get("weights", {})
    thresholds = config.get("signals", {})
    overlay_config = config.get("drawdown_overlay", {})

    # 1. Z-Scores
    zscores_df = compute_all_zscores(store, as_of_date=as_of_date)
    if zscores_df.empty:
        return {"error": "No Z-Score data available"}
    store.upsert_zscores(zscores_df)

    # 2. Z-Score dicts per asset
    asset_zscores = {}
    for _, row in zscores_df.iterrows():
        symbol = row["symbol"]
        if symbol not in asset_zscores:
            asset_zscores[symbol] = {}
        asset_zscores[symbol][row["metric"]] = row["zscore"]

    # 3. Individual composites
    s_gold = compute_gold_composite(asset_zscores.get("GOLD", {}), weights)
    s_silver = compute_silver_composite(asset_zscores.get("SILVER", {}), weights)
    s_sp500 = compute_etf_composite(asset_zscores.get("SP500", {}), weights)
    s_ndx = compute_ndx_composite(asset_zscores.get("NDX", {}), weights)

    # 4. Group scores
    s_precious, s_etf = compute_group_scores(s_gold, s_silver, s_sp500, s_ndx)

    # 5. Drawdown overlay (on group scores)
    silver_prices = store.get_prices("SILVER", end=as_of_date)
    sp500_prices = store.get_prices("SP500", end=as_of_date)
    dd_silver = compute_drawdown(silver_prices["close"]) if not silver_prices.empty else 0.0
    dd_etf = compute_drawdown(sp500_prices["close"]) if not sp500_prices.empty else 0.0
    rally_silver = compute_rally(silver_prices["close"]) if not silver_prices.empty else 0.0
    s_precious, s_etf, dd_correction = apply_drawdown_overlay(
        s_precious, s_etf, dd_silver, dd_etf, rally_silver, overlay_config
    )

    # 6. Level 1: 실물 자산 vs ETF
    r_group = round(s_precious - s_etf, 4)
    signal = generate_group_signal(r_group, thresholds)

    # 7. Level 2a: 금 vs 은 (GSR Z-Score 기반)
    gsr_zscore = asset_zscores.get("SILVER", {}).get("gsr", 0.0)
    gold_pct, silver_pct = compute_precious_split(gsr_zscore)

    # 8. Level 2b: S&P vs 나스닥
    sp500_pct, ndx_pct = compute_etf_split(s_sp500, s_ndx)

    # 9. R scores for internal splits
    r_precious = round(s_gold - s_silver, 4)
    r_etf_internal = round(s_sp500 - s_ndx, 4)

    # 10. Save
    weights_hash = hashlib.md5(json.dumps(weights, sort_keys=True).encode()).hexdigest()[:8]
    composite_df = pd.DataFrame([{
        "calc_date": calc_date,
        "s_gold": s_gold,
        "s_silver": s_silver,
        "s_sp500": s_sp500,
        "s_ndx": s_ndx,
        "s_precious": s_precious,
        "s_etf": s_etf,
        "r_group": r_group,
        "r_precious": r_precious,
        "r_etf_internal": r_etf_internal,
        "signal_label": signal["label"],
        "precious_pct": signal["precious_pct"],
        "gold_pct": gold_pct,
        "silver_pct": silver_pct,
        "sp500_pct": sp500_pct,
        "ndx_pct": ndx_pct,
        "dd_silver": dd_silver,
        "dd_etf": dd_etf,
        "dd_correction": dd_correction,
        "weights_hash": weights_hash,
    }])
    store.upsert_composite_scores(composite_df)

    result = {
        "calc_date": calc_date,
        "s_gold": s_gold, "s_silver": s_silver,
        "s_sp500": s_sp500, "s_ndx": s_ndx,
        "s_precious": s_precious, "s_etf": s_etf,
        "r_group": r_group, "r_precious": r_precious, "r_etf_internal": r_etf_internal,
        "signal": signal,
        "gold_pct": gold_pct, "silver_pct": silver_pct,
        "sp500_pct": sp500_pct, "ndx_pct": ndx_pct,
        "dd_silver": dd_silver, "dd_etf": dd_etf,
        "dd_correction": dd_correction,
    }
    result["comment"] = generate_comment(result)

    return result

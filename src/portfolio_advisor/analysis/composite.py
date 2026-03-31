from __future__ import annotations


def compute_silver_composite(zscores: dict[str, float], weights: dict) -> float:
    """은 복합 점수. 낮을수록 저평가."""
    mapping = {
        "return_50y": weights.get("w1_50y", 0.20),
        "return_10y": weights.get("w2_10y", 0.25),
        "return_5y": weights.get("w3_5y", 0.25),
        "price_position": weights.get("w4_valuation", 0.20),
        "gsr": weights.get("w5_gsr", 0.10),
    }
    return _weighted_sum(zscores, mapping)


def compute_gold_composite(zscores: dict[str, float], weights: dict) -> float:
    """금 복합 점수. 낮을수록 저평가. GSR 미적용."""
    mapping = {
        "return_50y": weights.get("w1_50y", 0.20),
        "return_10y": weights.get("w2_10y", 0.25),
        "return_5y": weights.get("w3_5y", 0.25),
        "price_position": weights.get("w4_valuation", 0.20),
    }
    return _weighted_sum(zscores, mapping)


def compute_etf_composite(zscores: dict[str, float], weights: dict) -> float:
    """S&P500 ETF 복합 점수. 높을수록 고평가."""
    mapping = {
        "return_50y": weights.get("w1_50y", 0.20),
        "return_10y": weights.get("w2_10y", 0.25),
        "return_5y": weights.get("w3_5y", 0.25),
        "cape": weights.get("w4_valuation", 0.20),
    }
    return _weighted_sum(zscores, mapping)


def compute_ndx_composite(zscores: dict[str, float], weights: dict) -> float:
    """나스닥100 복합 점수. 10년/5년만 사용 (1985년~)."""
    mapping = {
        "return_10y": weights.get("w2_10y", 0.25),
        "return_5y": weights.get("w3_5y", 0.25),
    }
    return _weighted_sum(zscores, mapping)


def compute_group_scores(
    s_gold: float, s_silver: float, s_sp500: float, s_ndx: float
) -> tuple[float, float]:
    """그룹 복합 점수 계산.

    Returns:
        (s_precious, s_etf) where:
        - s_precious = 금/은 평균
        - s_etf = S&P500 70% + 나스닥 30% (S&P500이 CAPE 등 장기 데이터가 있어서 가중)
    """
    s_precious = round((s_gold + s_silver) / 2, 4)
    s_etf = round(s_sp500 * 0.7 + s_ndx * 0.3, 4)
    return s_precious, s_etf


def compute_precious_split(gsr_zscore: float) -> tuple[int, int]:
    """금/은 내부 비율 결정. GSR Z-Score 기반.

    GSR(금은비)이 높을수록 은이 저평가 → 은 비중 높임.

    Returns:
        (gold_pct, silver_pct)
    """
    if gsr_zscore > 1.0:
        return 30, 70  # 은 크게 저평가
    elif gsr_zscore > 0.0:
        return 40, 60  # 은 약간 저평가
    elif gsr_zscore > -1.0:
        return 50, 50  # 중립
    else:
        return 60, 40  # 금이 더 매력적


def compute_etf_split(s_sp500: float, s_ndx: float) -> tuple[int, int]:
    """ETF 내부 비율 결정. 상대 점수 기반.

    점수가 낮은 쪽이 저평가 → 비중 높임.

    Returns:
        (sp500_pct, ndx_pct)
    """
    diff = s_sp500 - s_ndx  # 양수면 S&P가 고평가, 나스닥이 저평가
    if diff > 0.5:
        return 40, 60  # 나스닥이 상대적으로 저평가
    elif diff > -0.5:
        return 50, 50  # 비슷
    else:
        return 60, 40  # S&P가 상대적으로 저평가


def _weighted_sum(zscores: dict[str, float], mapping: dict[str, float]) -> float:
    """Compute weighted sum with automatic renormalization for missing values."""
    total_weight = 0.0
    total_score = 0.0

    for metric, weight in mapping.items():
        if metric in zscores and zscores[metric] is not None:
            total_score += weight * zscores[metric]
            total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(total_score / total_weight * sum(mapping.values()), 4)

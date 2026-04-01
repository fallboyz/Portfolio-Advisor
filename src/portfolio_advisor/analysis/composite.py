from __future__ import annotations


def compute_gold_composite(zscores: dict[str, float], config: dict) -> float:
    """금 복합 점수. 검증된 지표 기반. 낮을수록 저평가."""
    w = config.get("weights_gold", {})
    mapping = {
        "real_rate": w.get("real_rate", 0.30),
        "m2_gold": w.get("m2_gold", 0.30),
        "price_position": w.get("price_position", 0.20),
        "return_10y": w.get("return_10y", 0.20),
    }
    return _weighted_sum(zscores, mapping)


def compute_silver_composite(zscores: dict[str, float], config: dict) -> float:
    """은 복합 점수. 검증된 지표 + GSR. 낮을수록 저평가."""
    w = config.get("weights_silver", {})
    mapping = {
        "real_rate": w.get("real_rate", 0.25),
        "m2_gold": w.get("m2_gold", 0.25),
        "price_position": w.get("price_position", 0.15),
        "return_10y": w.get("return_10y", 0.15),
        "gsr": w.get("gsr", 0.20),
    }
    return _weighted_sum(zscores, mapping)


def compute_etf_composite(zscores: dict[str, float], config: dict) -> float:
    """S&P500 복합 점수. CAPE + Buffett + Yield Curve. 높을수록 고평가."""
    w = config.get("weights_sp500", {})
    mapping = {
        "cape": w.get("cape", 0.35),
        "buffett": w.get("buffett", 0.25),
        "yield_curve": w.get("yield_curve", 0.15),
        "return_10y": w.get("return_10y", 0.25),
    }
    return _weighted_sum(zscores, mapping)


def compute_ndx_composite(zscores: dict[str, float], config: dict) -> float:
    """나스닥100 복합 점수. 데이터 제약으로 수익률 + 가격 위치."""
    w = config.get("weights_ndx", {})
    mapping = {
        "return_10y": w.get("return_10y", 0.40),
        "return_5y": w.get("return_5y", 0.40),
        "price_position": w.get("price_position", 0.20),
    }
    return _weighted_sum(zscores, mapping)


def compute_group_scores(
    s_gold: float, s_silver: float, s_sp500: float, s_ndx: float
) -> tuple[float, float]:
    """그룹 복합 점수. s_precious = 금/은 평균, s_etf = S&P 70% + 나스닥 30%."""
    s_precious = round((s_gold + s_silver) / 2, 4)
    s_etf = round(s_sp500 * 0.7 + s_ndx * 0.3, 4)
    return s_precious, s_etf


def compute_precious_split(gsr_zscore: float) -> tuple[int, int]:
    """금/은 내부 비율. GSR(금은비) 높을수록 은 저평가 -> 은 비중 높임."""
    if gsr_zscore > 1.0:
        return 30, 70
    elif gsr_zscore > 0.0:
        return 40, 60
    elif gsr_zscore > -1.0:
        return 50, 50
    else:
        return 60, 40


def compute_etf_split(s_sp500: float, s_ndx: float) -> tuple[int, int]:
    """ETF 내부 비율. 점수 낮은 쪽이 저평가 -> 비중 높임."""
    diff = s_sp500 - s_ndx
    if diff > 0.5:
        return 40, 60
    elif diff > -0.5:
        return 50, 50
    else:
        return 60, 40


def _weighted_sum(zscores: dict[str, float], mapping: dict[str, float]) -> float:
    """가중합. missing value 자동 renormalization."""
    total_weight = 0.0
    total_score = 0.0

    for metric, weight in mapping.items():
        if metric in zscores and zscores[metric] is not None:
            total_score += weight * zscores[metric]
            total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(total_score / total_weight, 4)

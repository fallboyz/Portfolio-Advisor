from __future__ import annotations

from datetime import date

import pandas as pd

MIN_DATA_POINTS = 3


# ── YoY Returns ─────────────────────────────────────────────


def calculate_yoy_returns(
    prices_df: pd.DataFrame, freq: str = "annual"
) -> pd.DataFrame:
    """Calculate Year-over-Year returns from price data.

    Args:
        prices_df: DataFrame with 'date' and 'close' columns.
        freq: 'annual' for year-end YoY, 'monthly' for rolling 12-month return.

    Returns:
        DataFrame with 'date', 'yoy_pct' columns.
    """
    if prices_df.empty:
        return pd.DataFrame(columns=["date", "yoy_pct"])

    df = prices_df[["date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    df = df[df["close"].notna()]

    if freq == "annual":
        yearly = df.resample("YE").last().dropna()
        yearly["yoy_pct"] = yearly["close"].pct_change() * 100
        result = yearly[["yoy_pct"]].dropna().reset_index()
        result["date"] = result["date"].dt.date
        return result

    elif freq == "monthly":
        monthly = df.resample("ME").last().dropna()
        monthly["yoy_pct"] = monthly["close"].pct_change(periods=12) * 100
        result = monthly[["yoy_pct"]].dropna().reset_index()
        result["date"] = result["date"].dt.date
        return result

    raise ValueError(f"Unknown freq: {freq}")


# ── Z-Score Functions ───────────────────────────────────────


def zscore_yoy_return(
    yoy_series: pd.Series, current_value: float, window_years: int
) -> dict:
    """Z-Score of current YoY return vs historical window.

    Args:
        yoy_series: Series of historical YoY return percentages, most recent last.
        current_value: The current year's YoY return %.
        window_years: How many years of history to use.

    Returns:
        Dict with zscore, mean, stdev, current_value, window_years.
    """
    window = yoy_series.tail(window_years)

    if len(window) < MIN_DATA_POINTS:
        return _empty_zscore(current_value, window_years)

    mean = float(window.mean())
    stdev = float(window.std(ddof=1))

    if stdev == 0:
        return _empty_zscore(current_value, window_years)

    z = (current_value - mean) / stdev
    return {
        "zscore": round(z, 4),
        "mean_val": round(mean, 4),
        "stdev_val": round(stdev, 4),
        "current_val": round(current_value, 4),
        "window_years": window_years,
    }


def zscore_price_position(
    prices: pd.Series, current_price: float, ma_years: int = 10
) -> dict:
    """Z-Score of current price vs N-year moving average.

    Args:
        prices: Series of historical prices (monthly or annual).
        current_price: Current price.
        ma_years: Number of years for moving average (assumes ~12 monthly points/year).
    """
    window_size = ma_years * 12
    window = prices.tail(window_size)

    if len(window) < MIN_DATA_POINTS:
        return _empty_zscore(current_price, ma_years)

    mean = float(window.mean())
    stdev = float(window.std(ddof=1))

    if stdev == 0:
        return _empty_zscore(current_price, ma_years)

    z = (current_price - mean) / stdev
    return {
        "zscore": round(z, 4),
        "mean_val": round(mean, 4),
        "stdev_val": round(stdev, 4),
        "current_val": round(current_price, 4),
        "window_years": ma_years,
    }


def zscore_indicator(
    series: pd.Series, current_value: float, window_years: int = 0
) -> dict:
    """범용 지표 Z-Score. 전체 이력 또는 window 기반."""
    if window_years > 0:
        window_size = window_years * 12
        window = series.tail(window_size)
    else:
        window = series

    if len(window) < MIN_DATA_POINTS:
        return _empty_zscore(current_value, window_years)

    mean = float(window.mean())
    stdev = float(window.std(ddof=1))

    if stdev == 0:
        return _empty_zscore(current_value, window_years)

    z = (current_value - mean) / stdev
    return {
        "zscore": round(z, 4),
        "mean_val": round(mean, 4),
        "stdev_val": round(stdev, 4),
        "current_val": round(current_value, 4),
        "window_years": window_years,
    }


def _empty_zscore(current_val: float, window_years: int) -> dict:
    """Return a neutral Z-Score when data is insufficient."""
    return {
        "zscore": 0.0,
        "mean_val": None,
        "stdev_val": None,
        "current_val": round(current_val, 4),
        "window_years": window_years,
    }


# ── Master Orchestrator ─────────────────────────────────────


def compute_all_zscores(
    store, as_of_date: date | None = None
) -> pd.DataFrame:
    """Compute all Z-Scores for SILVER, GOLD, SP500, NDX."""
    calc_date = as_of_date or date.today()
    rows = []

    # 공통 데이터 fetch
    real_rate = store.get_indicator("REAINTRATREARAT10Y", end=as_of_date)
    m2_gold = store.get_indicator("M2_GOLD", end=as_of_date)

    _compute_silver_zscores(store, calc_date, as_of_date, real_rate, m2_gold, rows)
    _compute_gold_zscores(store, calc_date, as_of_date, real_rate, m2_gold, rows)
    _compute_sp500_zscores(store, calc_date, as_of_date, rows)
    _compute_ndx_zscores(store, calc_date, as_of_date, rows)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _filter_by_date(df: pd.DataFrame, as_of_date: date | None) -> pd.DataFrame:
    if as_of_date and not df.empty:
        return df[pd.to_datetime(df["date"]).dt.date <= as_of_date]
    return df


def _add_yoy_zscores(rows, calc_date, symbol, yoy_df, windows):
    if yoy_df.empty:
        return
    current_yoy = float(yoy_df.iloc[-1]["yoy_pct"])
    for window in windows:
        result = zscore_yoy_return(yoy_df["yoy_pct"], current_yoy, window)
        rows.append(_zscore_row(calc_date, symbol, f"return_{window}y", result))


def _add_indicator_zscore(rows, calc_date, symbol, metric, indicator_df, invert=False):
    if indicator_df.empty:
        return
    current = float(indicator_df.iloc[-1]["value"])
    result = zscore_indicator(indicator_df["value"], current)
    if invert:
        result["zscore"] = -result["zscore"]
    rows.append(_zscore_row(calc_date, symbol, metric, result))


def _compute_silver_zscores(store, calc_date, as_of_date, real_rate, m2_gold, rows):
    prices = store.get_prices("SILVER", end=as_of_date)
    yoy = _filter_by_date(store.get_yoy_returns("SILVER", period="annual"), as_of_date)

    _add_yoy_zscores(rows, calc_date, "SILVER", yoy, [50, 10, 5])

    if not prices.empty:
        result = zscore_price_position(prices["close"], float(prices.iloc[-1]["close"]))
        rows.append(_zscore_row(calc_date, "SILVER", "price_position", result))

    _add_indicator_zscore(rows, calc_date, "SILVER", "real_rate", real_rate, invert=True)
    _add_indicator_zscore(rows, calc_date, "SILVER", "m2_gold", m2_gold)

    gsr_data = store.get_indicator("GSR", end=as_of_date)
    if not gsr_data.empty:
        result = zscore_indicator(gsr_data["value"], float(gsr_data.iloc[-1]["value"]), window_years=50)
        rows.append(_zscore_row(calc_date, "SILVER", "gsr", result))


def _compute_gold_zscores(store, calc_date, as_of_date, real_rate, m2_gold, rows):
    prices = store.get_prices("GOLD", end=as_of_date)
    yoy = _filter_by_date(store.get_yoy_returns("GOLD", period="annual"), as_of_date)

    _add_yoy_zscores(rows, calc_date, "GOLD", yoy, [50, 10, 5])

    if not prices.empty:
        result = zscore_price_position(prices["close"], float(prices.iloc[-1]["close"]))
        rows.append(_zscore_row(calc_date, "GOLD", "price_position", result))

    _add_indicator_zscore(rows, calc_date, "GOLD", "real_rate", real_rate, invert=True)
    _add_indicator_zscore(rows, calc_date, "GOLD", "m2_gold", m2_gold)


def _compute_sp500_zscores(store, calc_date, as_of_date, rows):
    yoy = _filter_by_date(store.get_yoy_returns("SP500", period="annual"), as_of_date)
    _add_yoy_zscores(rows, calc_date, "SP500", yoy, [50, 10, 5])

    cape = store.get_indicator("CAPE", end=as_of_date)
    if not cape.empty:
        result = zscore_indicator(cape["value"], float(cape.iloc[-1]["value"]))
        rows.append(_zscore_row(calc_date, "SP500", "cape", result))

    _add_indicator_zscore(rows, calc_date, "SP500", "buffett",
                          store.get_indicator("BUFFETT", end=as_of_date))
    _add_indicator_zscore(rows, calc_date, "SP500", "yield_curve",
                          store.get_indicator("YIELD_CURVE", end=as_of_date))


def _compute_ndx_zscores(store, calc_date, as_of_date, rows):
    prices = store.get_prices("NDX", end=as_of_date)
    yoy = _filter_by_date(store.get_yoy_returns("NDX", period="annual"), as_of_date)
    _add_yoy_zscores(rows, calc_date, "NDX", yoy, [10, 5])

    if not prices.empty:
        result = zscore_price_position(prices["close"], float(prices.iloc[-1]["close"]))
        rows.append(_zscore_row(calc_date, "NDX", "price_position", result))


def _zscore_row(calc_date: date, symbol: str, metric: str, result: dict) -> dict:
    return {
        "calc_date": calc_date,
        "symbol": symbol,
        "metric": metric,
        "window_years": result["window_years"],
        "zscore": result["zscore"],
        "mean_val": result["mean_val"],
        "stdev_val": result["stdev_val"],
        "current_val": result["current_val"],
    }

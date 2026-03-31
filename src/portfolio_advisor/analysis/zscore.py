from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

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


def zscore_cape(cape_series: pd.Series, current_cape: float) -> dict:
    """Z-Score of current CAPE vs full historical distribution."""
    if len(cape_series) < MIN_DATA_POINTS:
        return _empty_zscore(current_cape, 0)

    mean = float(cape_series.mean())
    stdev = float(cape_series.std(ddof=1))

    if stdev == 0:
        return _empty_zscore(current_cape, 0)

    z = (current_cape - mean) / stdev
    return {
        "zscore": round(z, 4),
        "mean_val": round(mean, 4),
        "stdev_val": round(stdev, 4),
        "current_val": round(current_cape, 4),
        "window_years": 0,  # uses full history
    }


def zscore_gsr(
    gsr_series: pd.Series, current_gsr: float, window_years: int = 50
) -> dict:
    """Z-Score of Gold/Silver Ratio.

    Positive Z → ratio is high → silver undervalued → bullish for silver.
    """
    window_size = window_years * 12
    window = gsr_series.tail(window_size)

    if len(window) < MIN_DATA_POINTS:
        return _empty_zscore(current_gsr, window_years)

    mean = float(window.mean())
    stdev = float(window.std(ddof=1))

    if stdev == 0:
        return _empty_zscore(current_gsr, window_years)

    z = (current_gsr - mean) / stdev
    return {
        "zscore": round(z, 4),
        "mean_val": round(mean, 4),
        "stdev_val": round(stdev, 4),
        "current_val": round(current_gsr, 4),
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
    """Compute all Z-Scores for SILVER, GOLD, SP500, NDX.

    Args:
        store: Store instance for data access.
        as_of_date: If set, only uses data up to this date (for backtest).

    Returns:
        DataFrame ready for upsert into zscores table.
    """
    calc_date = as_of_date or date.today()
    rows = []

    # ── SILVER ──
    silver_prices = store.get_prices("SILVER", end=as_of_date)
    silver_yoy = store.get_yoy_returns("SILVER", period="annual")
    if as_of_date:
        silver_yoy = silver_yoy[pd.to_datetime(silver_yoy["date"]).dt.date <= as_of_date]

    if not silver_yoy.empty:
        current_yoy = float(silver_yoy.iloc[-1]["yoy_pct"])
        yoy_series = silver_yoy["yoy_pct"]

        for window in [50, 10, 5]:
            result = zscore_yoy_return(yoy_series, current_yoy, window)
            rows.append(_zscore_row(calc_date, "SILVER", f"return_{window}y", result))

    if not silver_prices.empty:
        current_price = float(silver_prices.iloc[-1]["close"])
        price_series = silver_prices["close"]
        result = zscore_price_position(price_series, current_price, ma_years=10)
        rows.append(_zscore_row(calc_date, "SILVER", "price_position", result))

    # GSR
    gsr_data = store.get_indicator("GSR", end=as_of_date)
    if not gsr_data.empty:
        current_gsr = float(gsr_data.iloc[-1]["value"])
        gsr_series = gsr_data["value"]
        result = zscore_gsr(gsr_series, current_gsr)
        rows.append(_zscore_row(calc_date, "SILVER", "gsr", result))

    # ── GOLD ──
    gold_prices = store.get_prices("GOLD", end=as_of_date)
    gold_yoy = store.get_yoy_returns("GOLD", period="annual")
    if as_of_date:
        gold_yoy = gold_yoy[pd.to_datetime(gold_yoy["date"]).dt.date <= as_of_date]

    if not gold_yoy.empty:
        current_yoy = float(gold_yoy.iloc[-1]["yoy_pct"])
        yoy_series = gold_yoy["yoy_pct"]

        for window in [50, 10, 5]:
            result = zscore_yoy_return(yoy_series, current_yoy, window)
            rows.append(_zscore_row(calc_date, "GOLD", f"return_{window}y", result))

    if not gold_prices.empty:
        current_price = float(gold_prices.iloc[-1]["close"])
        price_series = gold_prices["close"]
        result = zscore_price_position(price_series, current_price, ma_years=10)
        rows.append(_zscore_row(calc_date, "GOLD", "price_position", result))

    # ── SP500 ──
    sp500_yoy = store.get_yoy_returns("SP500", period="annual")
    if as_of_date:
        sp500_yoy = sp500_yoy[pd.to_datetime(sp500_yoy["date"]).dt.date <= as_of_date]

    if not sp500_yoy.empty:
        current_yoy = float(sp500_yoy.iloc[-1]["yoy_pct"])
        yoy_series = sp500_yoy["yoy_pct"]

        for window in [50, 10, 5]:
            result = zscore_yoy_return(yoy_series, current_yoy, window)
            rows.append(_zscore_row(calc_date, "SP500", f"return_{window}y", result))

    # CAPE
    cape_data = store.get_indicator("CAPE", end=as_of_date)
    if not cape_data.empty:
        current_cape = float(cape_data.iloc[-1]["value"])
        cape_series = cape_data["value"]
        result = zscore_cape(cape_series, current_cape)
        rows.append(_zscore_row(calc_date, "SP500", "cape", result))

    # ── NDX ──
    ndx_yoy = store.get_yoy_returns("NDX", period="annual")
    if as_of_date:
        ndx_yoy = ndx_yoy[pd.to_datetime(ndx_yoy["date"]).dt.date <= as_of_date]

    if not ndx_yoy.empty:
        current_yoy = float(ndx_yoy.iloc[-1]["yoy_pct"])
        yoy_series = ndx_yoy["yoy_pct"]

        for window in [10, 5]:
            result = zscore_yoy_return(yoy_series, current_yoy, window)
            rows.append(_zscore_row(calc_date, "NDX", f"return_{window}y", result))

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


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

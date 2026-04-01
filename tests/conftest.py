from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def tmp_config() -> dict:
    """Test configuration matching config.toml structure."""
    return {
        "api_keys": {"fred": "test_key"},
        "data": {
            "db_path": ":memory:",
            "raw_dir": "data/raw",
            "macrotrends_csv": "data/raw/silver_historical.csv",
            "shiller_excel": "data/raw/ie_data.xls",
            "shiller_url": "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
        },
        "symbols": {
            "silver": "SI=F",
            "gold": "GC=F",
            "sp500": "^GSPC",
            "ndx": "^NDX",
            "dxy": "DX-Y.NYB",
            "vix": "^VIX",
        },
        "fred_series": {"fed_funds": "FEDFUNDS", "cpi": "CPIAUCSL"},
        "server": {"web_port": 8501, "mcp_port": 8001, "mcp_host": "0.0.0.0"},
        "weights": {
            "w1_50y": 0.20,
            "w2_10y": 0.25,
            "w3_5y": 0.25,
            "w4_valuation": 0.20,
            "w5_gsr": 0.10,
        },
        "signals": {
            "strong_precious": -2.0,
            "mild_precious": -1.0,
            "mild_etf": 1.0,
            "strong_etf": 2.0,
        },
        "drawdown_overlay": {
            "silver_crash_threshold": -40,
            "etf_crash_threshold": -30,
            "silver_rally_threshold": 100,
        },
    }


@pytest.fixture
def sample_prices() -> pd.DataFrame:
    """Generate 20 years of synthetic monthly price data for SILVER, GOLD, SP500, NDX."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2004-01-31", periods=240, freq="ME")

    silver_prices = 15.0 * np.cumprod(1 + rng.normal(0.005, 0.06, 240))
    gold_prices = 500.0 * np.cumprod(1 + rng.normal(0.006, 0.04, 240))
    sp500_prices = 1200.0 * np.cumprod(1 + rng.normal(0.007, 0.04, 240))
    ndx_prices = 1500.0 * np.cumprod(1 + rng.normal(0.008, 0.05, 240))

    symbols_data = {
        "SILVER": silver_prices,
        "GOLD": gold_prices,
        "SP500": sp500_prices,
        "NDX": ndx_prices,
    }

    rows = []
    for i, dt in enumerate(dates):
        for symbol, prices in symbols_data.items():
            rows.append({
                "date": dt.date(),
                "symbol": symbol,
                "close": round(prices[i], 2),
                "open": None,
                "high": None,
                "low": None,
                "source": "test",
                "is_real": False,
            })

    return pd.DataFrame(rows)

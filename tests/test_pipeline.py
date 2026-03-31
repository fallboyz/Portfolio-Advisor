from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from portfolio_advisor.data.store import Store
from portfolio_advisor.scripts.update_data import _run_pipeline


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


@pytest.fixture
def config(tmp_path):
    return {
        "api_keys": {"fred": "test_key"},
        "data": {
            "db_path": ":memory:",
            "raw_dir": str(tmp_path / "raw"),
            "macrotrends_csv": str(tmp_path / "raw" / "silver.csv"),
            "shiller_excel": str(tmp_path / "raw" / "ie_data.xls"),
            "shiller_url": "http://fake.url/ie_data.xls",
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
        "server": {"streamlit_port": 8501, "mcp_port": 8001, "mcp_host": "0.0.0.0"},
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


def _make_price_df(symbol: str, n_months: int = 120) -> pd.DataFrame:
    """Generate mock price data."""
    import numpy as np

    rng = np.random.default_rng(42)
    dates = pd.date_range("2014-01-31", periods=n_months, freq="ME")
    base = 20.0 if symbol in ("SILVER", "GOLD") else 2000.0
    prices = base * np.cumprod(1 + rng.normal(0.005, 0.04, n_months))

    return pd.DataFrame(
        {
            "date": dates.date,
            "symbol": symbol,
            "close": prices,
            "open": prices * 0.99,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "source": "yfinance",
            "is_real": False,
        }
    )


def _make_fred_df(indicator: str) -> pd.DataFrame:
    dates = pd.date_range("2014-01-01", periods=120, freq="MS")
    return pd.DataFrame(
        {
            "date": dates.date,
            "indicator": indicator,
            "value": [5.0 + i * 0.01 for i in range(120)],
            "source": "fred",
        }
    )


@patch("portfolio_advisor.scripts.update_data.download_shiller_excel")
@patch("portfolio_advisor.scripts.update_data.fetch_shiller_excel")
@patch("portfolio_advisor.scripts.update_data.fetch_fed_funds")
@patch("portfolio_advisor.scripts.update_data.fetch_cpi")
@patch("portfolio_advisor.scripts.update_data.fetch_yfinance_symbol")
def test_pipeline_integration(
    mock_yf, mock_cpi, mock_fed, mock_shiller, mock_download_shiller, store, config
):
    """Integration test: mock all external fetchers, verify DB is populated."""

    # Setup mocks
    def yf_side_effect(symbol, display_name, start="1970-01-01", end=None):
        return _make_price_df(display_name)

    mock_yf.side_effect = yf_side_effect

    mock_shiller.return_value = (
        _make_price_df("SP500"),
        pd.DataFrame(
            [
                {"date": date(2014 + i, 1, 1), "indicator": "CAPE", "value": 20 + i, "source": "shiller"}
                for i in range(10)
            ]
        ),
    )
    mock_download_shiller.return_value = config["data"]["shiller_excel"]

    mock_fed.return_value = _make_fred_df("FEDFUNDS")
    mock_cpi.return_value = _make_fred_df("CPIAUCSL")

    # Run pipeline
    _run_pipeline(store, config)

    # Verify data was stored
    silver = store.get_prices("SILVER")
    assert len(silver) > 0

    gold = store.get_prices("GOLD")
    assert len(gold) > 0

    sp500 = store.get_prices("SP500")
    assert len(sp500) > 0

    # Verify derived calculations
    gsr = store.get_indicator("GSR")
    assert len(gsr) > 0

    # Verify YoY returns were computed
    silver_yoy = store.get_yoy_returns("SILVER")
    assert len(silver_yoy) > 0

    # Verify composite scores were computed
    latest = store.get_latest_composite()
    assert latest is not None
    assert latest["signal_label"] in {"strong_precious", "mild_precious", "neutral", "mild_etf", "strong_etf"}

    # Verify sync log
    sync = store.get_sync_status()
    assert len(sync) > 0

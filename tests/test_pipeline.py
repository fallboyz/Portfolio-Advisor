from __future__ import annotations

from datetime import date
from unittest.mock import patch

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
def config(tmp_config, tmp_path):
    tmp_config["data"]["macrotrends_csv"] = str(tmp_path / "raw" / "silver.csv")
    tmp_config["data"]["shiller_excel"] = str(tmp_path / "raw" / "ie_data.xls")
    tmp_config["data"]["shiller_url"] = "http://fake.url/ie_data.xls"
    return tmp_config


def _make_price_df(symbol: str, n_months: int = 120) -> pd.DataFrame:
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


def _make_fred_df(indicator: str, n_months: int = 120) -> pd.DataFrame:
    dates = pd.date_range("2014-01-01", periods=n_months, freq="MS")
    return pd.DataFrame(
        {
            "date": dates.date,
            "indicator": indicator,
            "value": [5.0 + i * 0.01 for i in range(n_months)],
            "source": "fred",
        }
    )


def _make_gdp_df() -> pd.DataFrame:
    dates = pd.date_range("2014-01-01", periods=40, freq="QS")
    return pd.DataFrame(
        {
            "date": dates.date,
            "indicator": "GDP",
            "value": [17000 + i * 100 for i in range(40)],
            "source": "fred",
        }
    )


def _make_treasury_df(indicator: str) -> pd.DataFrame:
    dates = pd.date_range("2014-01-01", periods=120, freq="MS")
    base = 3.0 if indicator == "DGS10" else 1.5
    return pd.DataFrame(
        {
            "date": dates.date,
            "indicator": indicator,
            "value": [base + i * 0.005 for i in range(120)],
            "source": "fred",
        }
    )


@patch("portfolio_advisor.scripts.update_data.download_shiller_excel")
@patch("portfolio_advisor.scripts.update_data.fetch_shiller_excel")
@patch("portfolio_advisor.scripts.update_data.fetch_real_rate")
@patch("portfolio_advisor.scripts.update_data.fetch_m2")
@patch("portfolio_advisor.scripts.update_data.fetch_gdp")
@patch("portfolio_advisor.scripts.update_data.fetch_treasury_10y")
@patch("portfolio_advisor.scripts.update_data.fetch_treasury_3m")
@patch("portfolio_advisor.scripts.update_data.fetch_yfinance_symbol")
def test_pipeline_integration(
    mock_yf, mock_t3m, mock_t10y, mock_gdp, mock_m2, mock_real_rate,
    mock_shiller, mock_download_shiller, store, config
):
    """Integration test: mock all external fetchers, verify DB is populated."""

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

    mock_real_rate.return_value = _make_fred_df("REAINTRATREARAT10Y")
    mock_m2.return_value = _make_fred_df("M2SL")
    mock_gdp.return_value = _make_gdp_df()
    mock_t10y.return_value = _make_treasury_df("DGS10")
    mock_t3m.return_value = _make_treasury_df("DGS3MO")

    # Run pipeline
    _run_pipeline(store, config)

    # Verify prices
    assert len(store.get_prices("SILVER")) > 0
    assert len(store.get_prices("GOLD")) > 0
    assert len(store.get_prices("SP500")) > 0

    # Verify derived: GSR
    gsr = store.get_indicator("GSR")
    assert len(gsr) > 0

    # Verify derived: M2/Gold ratio
    m2_gold = store.get_indicator("M2_GOLD")
    assert len(m2_gold) > 0

    # Verify derived: Buffett Indicator
    buffett = store.get_indicator("BUFFETT")
    assert len(buffett) > 0

    # Verify derived: Yield Curve
    yc = store.get_indicator("YIELD_CURVE")
    assert len(yc) > 0

    # Verify YoY returns
    assert len(store.get_yoy_returns("SILVER")) > 0

    # Verify composite scores
    latest = store.get_latest_composite()
    assert latest is not None
    assert latest["signal_label"] in {"strong_precious", "mild_precious", "neutral", "mild_etf", "strong_etf"}

    # Verify sync log
    sync = store.get_sync_status()
    assert len(sync) > 0

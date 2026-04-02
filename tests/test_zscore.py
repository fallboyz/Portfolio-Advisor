from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from portfolio_advisor.analysis.zscore import (
    calculate_yoy_returns,
    compute_all_zscores,
    zscore_indicator,
    zscore_price_position,
    zscore_yoy_return,
)
from portfolio_advisor.data.store import Store


# ── YoY Returns ─────────────────────────────────────────────


class TestYoyReturns:
    def test_annual_basic(self):
        df = pd.DataFrame(
            {
                "date": [date(2020, 12, 31), date(2021, 12, 31), date(2022, 12, 31)],
                "close": [100.0, 110.0, 99.0],
            }
        )
        result = calculate_yoy_returns(df, freq="annual")
        assert len(result) == 2
        assert abs(result.iloc[0]["yoy_pct"] - 10.0) < 0.01
        assert abs(result.iloc[1]["yoy_pct"] - (-10.0)) < 0.01

    def test_monthly_rolling(self):
        dates = pd.date_range("2020-01-31", periods=24, freq="ME")
        prices = [100.0] * 12 + [120.0] * 12  # jump at month 13
        df = pd.DataFrame({"date": dates.date, "close": prices})

        result = calculate_yoy_returns(df, freq="monthly")
        assert len(result) == 12  # first 12 months have no prior year
        assert all(abs(r - 20.0) < 0.01 for r in result["yoy_pct"])

    def test_empty_input(self):
        df = pd.DataFrame(columns=["date", "close"])
        result = calculate_yoy_returns(df)
        assert result.empty


# ── Z-Score Functions ───────────────────────────────────────


class TestZscoreYoyReturn:
    def test_known_values(self):
        # Mean=0, StdDev=~10 for uniform-ish data
        yoy = pd.Series([10.0, -10.0, 10.0, -10.0, 10.0, -10.0, 10.0, -10.0])
        result = zscore_yoy_return(yoy, 10.0, window_years=8)

        assert result["zscore"] == pytest.approx(10.0 / result["stdev_val"], abs=0.01)
        assert result["mean_val"] == pytest.approx(0.0, abs=0.01)
        assert result["window_years"] == 8

    def test_window_slicing(self):
        # 20 years of data, use only last 5
        yoy = pd.Series(range(20), dtype=float)
        result = zscore_yoy_return(yoy, 20.0, window_years=5)

        # Window should be [15, 16, 17, 18, 19]
        assert result["mean_val"] == pytest.approx(17.0, abs=0.01)

    def test_insufficient_data(self):
        yoy = pd.Series([5.0, 10.0])  # only 2 points
        result = zscore_yoy_return(yoy, 7.0, window_years=10)
        assert result["zscore"] == 0.0

    def test_zero_stdev(self):
        yoy = pd.Series([5.0, 5.0, 5.0, 5.0])
        result = zscore_yoy_return(yoy, 5.0, window_years=4)
        assert result["zscore"] == 0.0


class TestZscorePricePosition:
    def test_above_ma(self):
        rng = np.random.default_rng(42)
        prices = pd.Series(10.0 + rng.normal(0, 1, 120))  # mean ~10, stdev ~1
        result = zscore_price_position(prices, 20.0, ma_years=10)
        assert result["zscore"] > 0

    def test_below_ma(self):
        rng = np.random.default_rng(42)
        prices = pd.Series(10.0 + rng.normal(0, 1, 120))
        result = zscore_price_position(prices, 5.0, ma_years=10)
        assert result["zscore"] < 0

    def test_at_mean(self):
        rng = np.random.default_rng(42)
        prices = pd.Series(10.0 + rng.normal(0, 1, 120))
        mean_price = float(prices.mean())
        result = zscore_price_position(prices, mean_price, ma_years=10)
        assert abs(result["zscore"]) < 0.1


class TestZscoreIndicator:
    def test_high_value(self):
        rng = np.random.default_rng(42)
        history = pd.Series(rng.normal(16, 5, 1000))
        result = zscore_indicator(history, 38.0)
        assert result["zscore"] > 3.0

    def test_low_value(self):
        rng = np.random.default_rng(42)
        history = pd.Series(rng.normal(16, 5, 1000))
        result = zscore_indicator(history, 8.0)
        assert result["zscore"] < -1.0

    def test_insufficient_data(self):
        result = zscore_indicator(pd.Series([15.0]), 38.0)
        assert result["zscore"] == 0.0

    def test_with_window(self):
        rng = np.random.default_rng(42)
        series = pd.Series(rng.normal(60, 10, 600))
        result = zscore_indicator(series, 90.0, window_years=50)
        assert result["zscore"] > 2.0


# ── Orchestrator ────────────────────────────────────────────


class TestComputeAllZscores:
    @pytest.fixture
    def populated_store(self, sample_prices):
        store = Store(":memory:")
        store.upsert_prices(sample_prices)

        # Compute and store YoY returns for SILVER and SP500
        from portfolio_advisor.analysis.zscore import calculate_yoy_returns

        for symbol in ["SILVER", "GOLD", "SP500", "NDX"]:
            prices = store.get_prices(symbol)
            yoy = calculate_yoy_returns(prices, freq="annual")
            if not yoy.empty:
                yoy["symbol"] = symbol
                yoy["period"] = "annual"
                store.upsert_yoy_returns(yoy)

        # Add some CAPE data
        cape_df = pd.DataFrame(
            [
                {"date": date(2004 + i, 1, 1), "indicator": "CAPE", "value": 16 + i * 0.5, "source": "test"}
                for i in range(20)
            ]
        )
        store.upsert_economic_indicators(cape_df)

        # Add GSR data
        gsr_df = pd.DataFrame(
            [
                {"date": date(2004 + i, 1, 1), "indicator": "GSR", "value": 60 + i, "source": "test"}
                for i in range(20)
            ]
        )
        store.upsert_economic_indicators(gsr_df)

        yield store
        store.close()

    def test_produces_results(self, populated_store):
        result = compute_all_zscores(populated_store)
        assert not result.empty
        assert "calc_date" in result.columns
        assert "zscore" in result.columns

        # Should have SILVER and SP500 entries
        symbols = result["symbol"].unique()
        assert "SILVER" in symbols
        assert "SP500" in symbols

    def test_as_of_date_prevents_look_ahead(self, populated_store):
        cutoff = date(2015, 12, 31)

        result1 = compute_all_zscores(populated_store, as_of_date=cutoff)

        # Add future data
        future_prices = pd.DataFrame(
            [
                {
                    "date": date(2025, 6, 30),
                    "symbol": "SILVER",
                    "close": 999.99,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                }
            ]
        )
        populated_store.upsert_prices(future_prices)

        result2 = compute_all_zscores(populated_store, as_of_date=cutoff)

        # Results should be identical
        silver1 = result1[result1["symbol"] == "SILVER"].sort_values("metric").reset_index(drop=True)
        silver2 = result2[result2["symbol"] == "SILVER"].sort_values("metric").reset_index(drop=True)

        pd.testing.assert_frame_equal(silver1, silver2)

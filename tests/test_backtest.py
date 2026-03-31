from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from portfolio_advisor.analysis.zscore import calculate_yoy_returns
from portfolio_advisor.backtest.engine import BacktestEngine
from portfolio_advisor.data.store import Store


@pytest.fixture
def bt_store(sample_prices):
    """Store with enough data for backtesting."""
    store = Store(":memory:")
    store.upsert_prices(sample_prices)

    for symbol in ["SILVER", "GOLD", "SP500", "NDX"]:
        prices = store.get_prices(symbol)
        yoy = calculate_yoy_returns(prices, freq="annual")
        if not yoy.empty:
            yoy["symbol"] = symbol
            yoy["period"] = "annual"
            store.upsert_yoy_returns(yoy)

    cape_df = pd.DataFrame(
        [{"date": date(2004 + i, 1, 1), "indicator": "CAPE", "value": 16 + i * 0.5, "source": "test"} for i in range(20)]
    )
    store.upsert_economic_indicators(cape_df)

    gsr_df = pd.DataFrame(
        [{"date": date(2004 + i, 1, 1), "indicator": "GSR", "value": 60 + i, "source": "test"} for i in range(20)]
    )
    store.upsert_economic_indicators(gsr_df)

    yield store
    store.close()


@pytest.fixture
def bt_config(tmp_config):
    return tmp_config


class TestBacktestEngine:
    def test_basic_run(self, bt_store, bt_config):
        engine = BacktestEngine(bt_store, bt_config)
        result = engine.run(start_year=2010, end_year=2020, rebalance_freq="annual")

        assert not result.portfolio_values.empty
        assert not result.trades.empty
        assert "cagr_pct" in result.metrics
        assert "max_drawdown_pct" in result.metrics
        assert result.metrics["num_rebalances"] > 0

    def test_no_look_ahead_bias(self, bt_store, bt_config):
        """Verify that adding future data doesn't change past results."""
        engine = BacktestEngine(bt_store, bt_config)

        # Run backtest for 2010-2015
        result1 = engine.run(start_year=2010, end_year=2015)

        # Add future data beyond 2015
        future = pd.DataFrame(
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
        bt_store.upsert_prices(future)

        # Re-run same period
        result2 = engine.run(start_year=2010, end_year=2015)

        # Portfolio values should be identical
        pd.testing.assert_frame_equal(
            result1.portfolio_values.reset_index(drop=True),
            result2.portfolio_values.reset_index(drop=True),
        )

    def test_compare_with_fixed(self, bt_store, bt_config):
        engine = BacktestEngine(bt_store, bt_config)
        comparison = engine.compare_with_fixed(
            [(50, 50), (30, 70)],
            start_year=2010,
            end_year=2020,
        )

        assert "model" in comparison.columns
        assert "fixed_50_50" in comparison.columns
        assert "fixed_30_70" in comparison.columns

    def test_metrics_calculation(self, bt_store, bt_config):
        engine = BacktestEngine(bt_store, bt_config)
        result = engine.run(start_year=2010, end_year=2020, initial_capital=10000)

        assert result.metrics["initial_capital"] == 10000
        assert result.metrics["final_value"] > 0
        assert result.metrics["max_drawdown_pct"] <= 0  # drawdown is negative

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from portfolio_advisor.analysis.signal import (
    apply_drawdown_overlay,
    compute_drawdown,
    compute_full_signal,
    compute_rally,
    generate_group_signal,
)
from portfolio_advisor.data.store import Store


class TestDrawdown:
    def test_basic(self):
        prices = pd.Series([100.0, 110.0, 120.0, 90.0])
        dd = compute_drawdown(prices, lookback_days=4)
        assert dd == pytest.approx(-25.0, abs=0.1)

    def test_no_drawdown(self):
        prices = pd.Series([100.0, 110.0, 120.0, 130.0])
        dd = compute_drawdown(prices, lookback_days=4)
        assert dd == pytest.approx(0.0, abs=0.1)

    def test_empty(self):
        assert compute_drawdown(pd.Series(dtype=float)) == pytest.approx(0.0)


class TestRally:
    def test_basic(self):
        prices = pd.Series([100.0, 50.0, 75.0, 100.0])
        rally = compute_rally(prices, lookback_days=4)
        assert rally == pytest.approx(100.0, abs=0.1)

    def test_no_rally(self):
        prices = pd.Series([100.0, 90.0, 80.0, 70.0])
        rally = compute_rally(prices, lookback_days=4)
        assert rally == pytest.approx(0.0, abs=0.1)


class TestDrawdownOverlay:
    def test_silver_crash_triggers(self):
        s_precious, s_etf, correction = apply_drawdown_overlay(
            0.0, 0.0, -45.0, -10.0, 20.0,
            {"silver_crash_threshold": -40, "etf_crash_threshold": -30, "silver_rally_threshold": 100},
        )
        assert s_precious == pytest.approx(-0.5, abs=0.01)
        assert s_etf == pytest.approx(0.0, abs=0.01)
        assert correction == pytest.approx(-0.5, abs=0.01)

    def test_etf_crash_triggers(self):
        _, s_etf, _ = apply_drawdown_overlay(
            0.0, 0.0, -10.0, -35.0, 20.0,
            {"silver_crash_threshold": -40, "etf_crash_threshold": -30, "silver_rally_threshold": 100},
        )
        assert s_etf == pytest.approx(-0.5, abs=0.01)

    def test_silver_rally_triggers(self):
        s_precious, _, _ = apply_drawdown_overlay(
            0.0, 0.0, -10.0, -10.0, 120.0,
            {"silver_crash_threshold": -40, "etf_crash_threshold": -30, "silver_rally_threshold": 100},
        )
        assert s_precious == pytest.approx(0.5, abs=0.01)

    def test_no_triggers(self):
        s_precious, s_etf, correction = apply_drawdown_overlay(
            1.0, 1.0, -10.0, -10.0, 20.0,
            {"silver_crash_threshold": -40, "etf_crash_threshold": -30, "silver_rally_threshold": 100},
        )
        assert s_precious == pytest.approx(1.0, abs=0.01)
        assert s_etf == pytest.approx(1.0, abs=0.01)
        assert correction == pytest.approx(0.0, abs=0.01)


class TestGenerateGroupSignal:
    def test_strong_precious(self):
        signal = generate_group_signal(-2.5, {"strong_precious": -2.0})
        assert signal["label"] == "strong_precious"
        assert signal["precious_pct"] == 75

    def test_mild_precious(self):
        signal = generate_group_signal(-1.5, {"strong_precious": -2.0, "mild_precious": -1.0})
        assert signal["label"] == "mild_precious"
        assert signal["precious_pct"] == 60

    def test_neutral(self):
        signal = generate_group_signal(0.0, {"strong_precious": -2.0, "mild_precious": -1.0, "mild_etf": 1.0})
        assert signal["label"] == "neutral"
        assert signal["precious_pct"] == 50

    def test_mild_etf(self):
        signal = generate_group_signal(1.5, {"strong_precious": -2.0, "mild_precious": -1.0, "mild_etf": 1.0, "strong_etf": 2.0})
        assert signal["label"] == "mild_etf"
        assert signal["precious_pct"] == 35

    def test_strong_etf(self):
        signal = generate_group_signal(2.5, {"strong_precious": -2.0, "mild_precious": -1.0, "mild_etf": 1.0, "strong_etf": 2.0})
        assert signal["label"] == "strong_etf"
        assert signal["precious_pct"] == 20

    def test_boundary_exact(self):
        signal = generate_group_signal(-2.0, {"strong_precious": -2.0, "mild_precious": -1.0})
        assert signal["label"] == "mild_precious"


class TestComputeFullSignal:
    @pytest.fixture
    def populated_store(self, sample_prices):
        store = Store(":memory:")
        store.upsert_prices(sample_prices)

        from portfolio_advisor.analysis.zscore import calculate_yoy_returns

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

    def test_full_pipeline(self, populated_store, tmp_config):
        result = compute_full_signal(populated_store, tmp_config)

        assert "error" not in result
        assert "s_precious" in result
        assert "s_etf" in result
        assert "r_group" in result
        assert "signal" in result
        assert result["signal"]["label"] in {"strong_precious", "mild_precious", "neutral", "mild_etf", "strong_etf"}
        assert "gold_pct" in result
        assert "silver_pct" in result
        assert "sp500_pct" in result
        assert "ndx_pct" in result

        latest = populated_store.get_latest_composite()
        assert latest is not None

from __future__ import annotations

import pytest

from portfolio_advisor.analysis.composite import (
    compute_etf_composite,
    compute_gold_composite,
    compute_silver_composite,
)


class TestGoldComposite:
    def test_basic_weighted_sum(self):
        zscores = {
            "real_rate": -1.0,
            "m2_gold": 0.5,
            "price_position": 1.0,
            "return_10y": -0.5,
        }
        config = {"weights_gold": {
            "real_rate": 0.30, "m2_gold": 0.30,
            "price_position": 0.20, "return_10y": 0.20,
        }}

        result = compute_gold_composite(zscores, config)
        # 0.30*(-1) + 0.30*(0.5) + 0.20*(1.0) + 0.20*(-0.5)
        # = -0.30 + 0.15 + 0.20 - 0.10 = -0.05
        assert result == pytest.approx(-0.05, abs=0.01)


class TestSilverComposite:
    def test_basic_weighted_sum(self):
        zscores = {
            "real_rate": -1.0,
            "m2_gold": 0.5,
            "price_position": 1.0,
            "return_10y": -0.5,
            "gsr": 2.0,
        }
        config = {"weights_silver": {
            "real_rate": 0.25, "m2_gold": 0.25,
            "price_position": 0.15, "return_10y": 0.15, "gsr": 0.20,
        }}

        result = compute_silver_composite(zscores, config)
        # 0.25*(-1) + 0.25*(0.5) + 0.15*(1.0) + 0.15*(-0.5) + 0.20*(2.0)
        # = -0.25 + 0.125 + 0.15 - 0.075 + 0.40 = 0.35
        assert result == pytest.approx(0.35, abs=0.01)

    def test_missing_zscore_renormalization(self):
        zscores = {
            "real_rate": 1.0,
            "m2_gold": 1.0,
        }
        config = {"weights_silver": {
            "real_rate": 0.25, "m2_gold": 0.25,
            "price_position": 0.15, "return_10y": 0.15, "gsr": 0.20,
        }}

        result = compute_silver_composite(zscores, config)
        # Only real_rate and m2_gold active (0.25+0.25=0.50)
        # Score = (0.25*1 + 0.25*1) / 0.50 * 1.0 = 1.0
        assert result == pytest.approx(1.0, abs=0.01)

    def test_all_missing(self):
        result = compute_silver_composite({}, {"weights_silver": {"real_rate": 0.25}})
        assert result == 0.0


class TestEtfComposite:
    def test_basic(self):
        zscores = {
            "cape": 2.0,
            "buffett": 1.0,
            "yield_curve": -0.5,
            "return_10y": 1.5,
        }
        config = {"weights_sp500": {
            "cape": 0.35, "buffett": 0.25,
            "yield_curve": 0.15, "return_10y": 0.25,
        }}

        result = compute_etf_composite(zscores, config)
        # 0.35*2.0 + 0.25*1.0 + 0.15*(-0.5) + 0.25*1.5
        # = 0.70 + 0.25 - 0.075 + 0.375 = 1.25
        assert result == pytest.approx(1.25, abs=0.01)

    def test_no_gsr(self):
        """ETF composite should not use GSR even if provided."""
        zscores = {
            "cape": 2.0,
            "buffett": 1.0,
            "yield_curve": -0.5,
            "return_10y": 1.5,
            "gsr": 99.0,
        }
        config = {"weights_sp500": {
            "cape": 0.35, "buffett": 0.25,
            "yield_curve": 0.15, "return_10y": 0.25,
        }}

        result = compute_etf_composite(zscores, config)
        assert result == pytest.approx(1.25, abs=0.01)

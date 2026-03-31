from __future__ import annotations

import pytest

from portfolio_advisor.analysis.composite import (
    compute_etf_composite,
    compute_silver_composite,
)


class TestSilverComposite:
    def test_basic_weighted_sum(self):
        zscores = {
            "return_50y": -1.0,
            "return_10y": -0.5,
            "return_5y": 0.5,
            "price_position": 1.0,
            "gsr": 2.0,
        }
        weights = {
            "w1_50y": 0.20,
            "w2_10y": 0.25,
            "w3_5y": 0.25,
            "w4_valuation": 0.20,
            "w5_gsr": 0.10,
        }

        result = compute_silver_composite(zscores, weights)

        # Manual: 0.20*(-1) + 0.25*(-0.5) + 0.25*(0.5) + 0.20*(1.0) + 0.10*(2.0)
        # = -0.20 - 0.125 + 0.125 + 0.20 + 0.20 = 0.20
        assert result == pytest.approx(0.20, abs=0.01)

    def test_missing_zscore_renormalization(self):
        zscores = {
            "return_10y": 1.0,
            "return_5y": 1.0,
            # missing return_50y, price_position, gsr
        }
        weights = {
            "w1_50y": 0.20,
            "w2_10y": 0.25,
            "w3_5y": 0.25,
            "w4_valuation": 0.20,
            "w5_gsr": 0.10,
        }

        result = compute_silver_composite(zscores, weights)
        # Only w2 and w3 are active (0.25 + 0.25 = 0.50)
        # Score = (0.25*1 + 0.25*1) / 0.50 * 1.0 = 1.0
        assert result == pytest.approx(1.0, abs=0.01)

    def test_all_missing(self):
        result = compute_silver_composite({}, {"w1_50y": 0.20})
        assert result == 0.0


class TestEtfComposite:
    def test_basic(self):
        zscores = {
            "return_50y": 0.5,
            "return_10y": 1.0,
            "return_5y": 1.5,
            "cape": 2.0,
        }
        weights = {
            "w1_50y": 0.20,
            "w2_10y": 0.25,
            "w3_5y": 0.25,
            "w4_valuation": 0.20,
        }

        result = compute_etf_composite(zscores, weights)
        # 0.20*0.5 + 0.25*1.0 + 0.25*1.5 + 0.20*2.0
        # = 0.10 + 0.25 + 0.375 + 0.40 = 1.125
        assert result == pytest.approx(1.125, abs=0.01)

    def test_no_gsr(self):
        """ETF composite should not use GSR even if provided."""
        zscores = {
            "return_50y": 0.5,
            "return_10y": 1.0,
            "return_5y": 1.5,
            "cape": 2.0,
            "gsr": 99.0,  # should be ignored
        }
        weights = {
            "w1_50y": 0.20,
            "w2_10y": 0.25,
            "w3_5y": 0.25,
            "w4_valuation": 0.20,
            "w5_gsr": 0.10,
        }

        result = compute_etf_composite(zscores, weights)
        assert result == pytest.approx(1.125, abs=0.01)

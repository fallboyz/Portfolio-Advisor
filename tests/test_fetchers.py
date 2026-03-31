from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from portfolio_advisor.data.fetchers import (
    calculate_gold_silver_ratio,
    fetch_fred_series,
    fetch_shiller_excel,
    fetch_silver_historical_csv,
    fetch_yfinance_symbol,
)


@pytest.fixture
def macrotrends_csv(tmp_path):
    """Create a minimal Macrotrends-style CSV."""
    content = """date,value
1915-12-31,0.50
1920-12-31,0.65
1950-12-31,0.74
1980-01-18,49.45
2020-12-31,26.49
2024-12-31,29.30
"""
    path = tmp_path / "silver_historical.csv"
    path.write_text(content)
    return str(path)


@pytest.fixture
def macrotrends_csv_alt_format(tmp_path):
    """CSV with alternative column names (year-based)."""
    content = """year,year_open,year_high,year_low,year_close
2020,17.85,29.26,11.64,26.49
2021,26.49,30.13,21.41,23.35
2022,23.35,26.95,17.40,23.94
"""
    path = tmp_path / "silver_alt.csv"
    path.write_text(content)
    return str(path)


class TestSilverHistoricalCsv:
    def test_parse_standard_format(self, macrotrends_csv):
        df = fetch_silver_historical_csv(macrotrends_csv)
        assert len(df) == 6
        assert "date" in df.columns
        assert "symbol" in df.columns
        assert df.iloc[0]["symbol"] == "SILVER"
        assert df.iloc[0]["source"] == "macrotrends"
        assert df.iloc[3]["close"] == 49.45

    def test_parse_alt_format(self, macrotrends_csv_alt_format):
        df = fetch_silver_historical_csv(macrotrends_csv_alt_format)
        assert len(df) == 3
        assert df.iloc[0]["close"] == 26.49
        assert df.iloc[0]["open"] == 17.85

    def test_missing_file(self):
        df = fetch_silver_historical_csv("/nonexistent/path.csv")
        assert df.empty


class TestYfinance:
    @patch("yfinance.download")
    def test_fetch_success(self, mock_download):
        mock_data = pd.DataFrame(
            {
                "Open": [23.0, 23.5],
                "High": [24.0, 24.5],
                "Low": [22.5, 23.0],
                "Close": [23.5, 24.1],
            },
            index=pd.DatetimeIndex(["2024-01-31", "2024-02-29"]),
        )
        mock_download.return_value = mock_data

        df = fetch_yfinance_symbol("SI=F", "SILVER", start="2024-01-01")
        assert len(df) == 2
        assert df.iloc[0]["symbol"] == "SILVER"
        assert df.iloc[0]["source"] == "yfinance"
        assert df.iloc[1]["close"] == 24.1

    @patch("yfinance.download")
    def test_fetch_empty(self, mock_download):
        mock_download.return_value = pd.DataFrame()
        df = fetch_yfinance_symbol("INVALID", "TEST")
        assert df.empty

    @patch("yfinance.download")
    def test_retry_on_failure(self, mock_download):
        mock_download.side_effect = [
            Exception("rate limited"),
            pd.DataFrame(
                {"Close": [100.0]},
                index=pd.DatetimeIndex(["2024-01-31"]),
            ),
        ]
        df = fetch_yfinance_symbol("^GSPC", "SP500")
        assert len(df) == 1
        assert mock_download.call_count == 2


class TestShillerExcel:
    def test_missing_file(self):
        prices, indicators = fetch_shiller_excel("/nonexistent/ie_data.xls")
        assert prices.empty
        assert indicators.empty


class TestFredSeries:
    @patch("fredapi.Fred")
    def test_fetch_success(self, mock_fred_cls):
        mock_fred = MagicMock()
        mock_fred_cls.return_value = mock_fred
        mock_fred.get_series.return_value = pd.Series(
            [5.25, 5.33, 5.50],
            index=pd.DatetimeIndex(["2024-01-01", "2024-02-01", "2024-03-01"]),
        )

        df = fetch_fred_series("FEDFUNDS", "test_key")
        assert len(df) == 3
        assert df.iloc[0]["indicator"] == "FEDFUNDS"
        assert df.iloc[0]["source"] == "fred"

    @patch("fredapi.Fred")
    def test_fetch_failure(self, mock_fred_cls):
        mock_fred = MagicMock()
        mock_fred_cls.return_value = mock_fred
        mock_fred.get_series.side_effect = Exception("API error")

        df = fetch_fred_series("FEDFUNDS", "bad_key")
        assert df.empty


class TestGoldSilverRatio:
    def test_calculate(self):
        gold = pd.DataFrame(
            {
                "date": [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)],
                "close": [2000.0, 2050.0, 2100.0],
            }
        )
        silver = pd.DataFrame(
            {
                "date": [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)],
                "close": [25.0, 25.0, 30.0],
            }
        )

        df = calculate_gold_silver_ratio(gold, silver)
        assert len(df) == 3
        assert df.iloc[0]["value"] == 80.0  # 2000/25
        assert df.iloc[2]["value"] == 70.0  # 2100/30
        assert df.iloc[0]["indicator"] == "GSR"

    def test_empty_input(self):
        df = calculate_gold_silver_ratio(pd.DataFrame(), pd.DataFrame())
        assert df.empty

    def test_partial_date_match(self):
        gold = pd.DataFrame(
            {"date": [date(2024, 1, 31), date(2024, 3, 31)], "close": [2000.0, 2100.0]}
        )
        silver = pd.DataFrame(
            {
                "date": [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)],
                "close": [25.0, 26.0, 30.0],
            }
        )

        df = calculate_gold_silver_ratio(gold, silver)
        assert len(df) == 2  # only matching dates

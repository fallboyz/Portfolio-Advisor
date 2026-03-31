from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from portfolio_advisor.data.store import Store


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


class TestSchema:
    def test_tables_created(self, store: Store):
        tables = store.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchdf()
        expected = {
            "prices",
            "economic_indicators",
            "yoy_returns",
            "zscores",
            "composite_scores",
            "comments",
            "data_sync_log",
        }
        assert expected == set(tables["table_name"].tolist())

    def test_schema_idempotent(self, store: Store):
        store._ensure_schema()
        tables = store.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchdf()
        assert len(tables) == 7


class TestPrices:
    def test_upsert_and_read(self, store: Store):
        df = pd.DataFrame(
            [
                {
                    "date": date(2024, 1, 31),
                    "symbol": "SILVER",
                    "close": 23.5,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                },
                {
                    "date": date(2024, 2, 29),
                    "symbol": "SILVER",
                    "close": 24.1,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                },
            ]
        )
        count = store.upsert_prices(df)
        assert count == 2

        result = store.get_prices("SILVER")
        assert len(result) == 2
        assert result.iloc[0]["close"] == pytest.approx(23.5)

    def test_upsert_idempotent(self, store: Store):
        df = pd.DataFrame(
            [
                {
                    "date": date(2024, 1, 31),
                    "symbol": "SILVER",
                    "close": 23.5,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                }
            ]
        )
        store.upsert_prices(df)
        store.upsert_prices(df)

        result = store.get_prices("SILVER")
        assert len(result) == 1

    def test_upsert_updates_value(self, store: Store):
        df1 = pd.DataFrame(
            [
                {
                    "date": date(2024, 1, 31),
                    "symbol": "SILVER",
                    "close": 23.5,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                }
            ]
        )
        df2 = pd.DataFrame(
            [
                {
                    "date": date(2024, 1, 31),
                    "symbol": "SILVER",
                    "close": 25.0,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                }
            ]
        )
        store.upsert_prices(df1)
        store.upsert_prices(df2)

        result = store.get_prices("SILVER")
        assert len(result) == 1
        assert result.iloc[0]["close"] == pytest.approx(25.0)

    def test_date_range_filter(self, store: Store):
        df = pd.DataFrame(
            [
                {
                    "date": date(2024, 1, 31),
                    "symbol": "SILVER",
                    "close": 23.5,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                },
                {
                    "date": date(2024, 6, 30),
                    "symbol": "SILVER",
                    "close": 28.0,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                },
                {
                    "date": date(2024, 12, 31),
                    "symbol": "SILVER",
                    "close": 30.0,
                    "open": None,
                    "high": None,
                    "low": None,
                    "source": "test",
                    "is_real": False,
                },
            ]
        )
        store.upsert_prices(df)

        result = store.get_prices("SILVER", start=date(2024, 3, 1), end=date(2024, 9, 30))
        assert len(result) == 1
        assert result.iloc[0]["close"] == pytest.approx(28.0)

    def test_empty_upsert(self, store: Store):
        count = store.upsert_prices(pd.DataFrame())
        assert count == 0


class TestEconomicIndicators:
    def test_upsert_and_read(self, store: Store):
        df = pd.DataFrame(
            [
                {
                    "date": date(2024, 1, 1),
                    "indicator": "CAPE",
                    "value": 35.5,
                    "source": "shiller",
                },
                {
                    "date": date(2024, 2, 1),
                    "indicator": "CAPE",
                    "value": 36.1,
                    "source": "shiller",
                },
            ]
        )
        store.upsert_economic_indicators(df)

        result = store.get_indicator("CAPE")
        assert len(result) == 2
        assert result.iloc[1]["value"] == pytest.approx(36.1)


class TestYoyReturns:
    def test_upsert_and_read(self, store: Store):
        df = pd.DataFrame(
            [
                {
                    "date": date(2023, 12, 31),
                    "symbol": "SILVER",
                    "yoy_pct": 5.3,
                    "period": "annual",
                },
                {
                    "date": date(2024, 12, 31),
                    "symbol": "SILVER",
                    "yoy_pct": -2.1,
                    "period": "annual",
                },
            ]
        )
        store.upsert_yoy_returns(df)

        result = store.get_yoy_returns("SILVER")
        assert len(result) == 2


class TestCompositeScores:
    def _make_composite_row(self, calc_date, **overrides):
        row = {
            "calc_date": calc_date,
            "s_gold": 0.0, "s_silver": -0.5, "s_sp500": 0.3, "s_ndx": 0.1,
            "s_precious": -0.25, "s_etf": 0.24,
            "r_group": -0.49, "r_precious": 0.5, "r_etf_internal": 0.2,
            "signal_label": "neutral", "precious_pct": 50,
            "gold_pct": 50, "silver_pct": 50, "sp500_pct": 50, "ndx_pct": 50,
            "dd_silver": -10.0, "dd_etf": -5.0, "dd_correction": 0.0,
            "weights_hash": "abc123",
        }
        row.update(overrides)
        return row

    def test_upsert_and_latest(self, store: Store):
        df = pd.DataFrame([
            self._make_composite_row(date(2024, 1, 31), signal_label="neutral"),
            self._make_composite_row(date(2024, 2, 29), signal_label="strong_precious", r_group=-2.2),
        ])
        store.upsert_composite_scores(df)

        latest = store.get_latest_composite()
        assert latest is not None
        assert latest["signal_label"] == "strong_precious"
        assert latest["r_group"] == pytest.approx(-2.2)

    def test_composite_history(self, store: Store):
        df = pd.DataFrame([self._make_composite_row(date(2024, 1, 31))])
        store.upsert_composite_scores(df)

        history = store.get_composite_history()
        assert len(history) == 1


class TestComments:
    def test_add_and_read(self, store: Store):
        id1 = store.add_comment(date(2024, 3, 30), "Silver looks undervalued")
        id2 = store.add_comment(date(2024, 3, 31), "ETF overheating", author="user")

        assert id1 >= 1
        assert id2 > id1

        comments = store.get_comments()
        assert len(comments) == 2
        assert comments.iloc[0]["author"] == "user"  # newest first


class TestSyncLog:
    def test_log_and_read(self, store: Store):
        store.log_sync("yfinance_silver", 100)
        store.log_sync("fred_cpi", 50, status="error", error_msg="timeout")

        status = store.get_sync_status()
        assert len(status) == 2

    def test_log_upsert(self, store: Store):
        store.log_sync("yfinance_silver", 100)
        store.log_sync("yfinance_silver", 5)

        status = store.get_sync_status()
        assert len(status) == 1
        assert status.iloc[0]["rows_added"] == 5

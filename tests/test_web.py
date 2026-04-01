from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from portfolio_advisor.data.store import Store
from portfolio_advisor.web.app import app, _open_store


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


@pytest.fixture
def client(store):
    from contextlib import contextmanager

    @contextmanager
    def _mock_store():
        yield store

    with patch("portfolio_advisor.web.app._open_store", _mock_store):
        yield TestClient(app)


def _seed_composite(store, calc_date=date(2024, 3, 31), signal_label="neutral"):
    df = pd.DataFrame([{
        "calc_date": calc_date,
        "s_gold": 0.1, "s_silver": -0.5, "s_sp500": 0.3, "s_ndx": 0.2,
        "s_precious": -0.2, "s_etf": 0.25,
        "r_group": -0.45, "r_precious": 0.6, "r_etf_internal": 0.1,
        "signal_label": signal_label, "precious_pct": 50,
        "gold_pct": 50, "silver_pct": 50, "sp500_pct": 60, "ndx_pct": 40,
        "dd_silver": -8.0, "dd_etf": -3.0, "dd_correction": 0.0,
        "weights_hash": "test123",
    }])
    store.insert_composite_scores(df)


def _seed_prices(store, symbol="SILVER", n=10):
    rows = []
    for i in range(n):
        rows.append({
            "date": date(2024, 1, 1) + pd.Timedelta(days=i * 30),
            "symbol": symbol, "close": 20.0 + i,
            "open": None, "high": None, "low": None,
            "source": "test", "is_real": False,
        })
    store.upsert_prices(pd.DataFrame(rows))


def _seed_zscores(store, calc_date=date(2024, 3, 31)):
    df = pd.DataFrame([
        {"calc_date": calc_date, "symbol": "SILVER", "metric": "return_50y",
         "window_years": 50, "zscore": -1.2, "mean_val": 5.0, "stdev_val": 10.0, "current_val": -7.0},
        {"calc_date": calc_date, "symbol": "GOLD", "metric": "return_50y",
         "window_years": 50, "zscore": 0.3, "mean_val": 8.0, "stdev_val": 12.0, "current_val": 11.6},
    ])
    store.upsert_zscores(df)


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestIndex:
    def test_index_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestApiLatest:
    def test_no_data(self, client):
        resp = client.get("/api/latest")
        assert resp.json()["error"] == "no data"

    def test_with_data(self, client, store):
        _seed_composite(store)
        resp = client.get("/api/latest")
        data = resp.json()
        assert data["signal_label"] == "neutral"
        assert data["precious_pct"] == 50


class TestApiHistory:
    def test_empty(self, client):
        resp = client.get("/api/history")
        data = resp.json()
        assert data["dates"] == []
        assert data["history"] == []

    def test_with_data(self, client, store):
        _seed_composite(store, date(2024, 1, 31))
        _seed_composite(store, date(2024, 2, 29), "mild_precious")
        resp = client.get("/api/history")
        data = resp.json()
        assert len(data["dates"]) == 2
        assert len(data["history"]) == 2


class TestApiPrices:
    def test_empty(self, client):
        resp = client.get("/api/prices/SILVER")
        data = resp.json()
        assert data["dates"] == []

    def test_with_data(self, client, store):
        _seed_prices(store)
        resp = client.get("/api/prices/silver?years=0")
        data = resp.json()
        assert len(data["dates"]) == 10
        assert len(data["closes"]) == 10


class TestApiZscores:
    def test_empty(self, client):
        resp = client.get("/api/zscores")
        data = resp.json()
        assert data["symbols"] == []

    def test_with_data(self, client, store):
        _seed_zscores(store)
        resp = client.get("/api/zscores")
        data = resp.json()
        assert "SILVER" in data["symbols"]
        assert len(data["values"]) > 0


class TestApiIndicators:
    def test_empty(self, client):
        resp = client.get("/api/indicators/GSR")
        data = resp.json()
        assert data["dates"] == []

    def test_with_data(self, client, store):
        df = pd.DataFrame([
            {"date": date(2024, 1, 1), "indicator": "GSR", "value": 80.5, "source": "calc"},
            {"date": date(2024, 2, 1), "indicator": "GSR", "value": 82.1, "source": "calc"},
        ])
        store.upsert_economic_indicators(df)
        resp = client.get("/api/indicators/gsr")
        data = resp.json()
        assert len(data["dates"]) == 2


class TestApiAnalysis:
    def test_no_data(self, client):
        resp = client.get("/api/analysis/2024-03-31")
        assert resp.json()["error"] == "no data for this date"

    def test_invalid_date(self, client):
        resp = client.get("/api/analysis/not-a-date")
        assert resp.json()["error"] == "invalid date format"

    def test_with_data(self, client, store):
        _seed_composite(store)
        _seed_zscores(store)
        store.add_comment(datetime(2024, 3, 31, 10, 0), "Test comment", "system")

        resp = client.get("/api/analysis/2024-03-31")
        data = resp.json()
        assert data["composite"]["signal_label"] == "neutral"
        assert len(data["zscores"]) == 2
        assert len(data["comments"]) == 1

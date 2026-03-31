from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd


class Store:
    """DuckDB-backed data store for all portfolio advisor data."""

    def __init__(self, db_path: str = ":memory:", read_only: bool = False):
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(db_path, read_only=read_only)
        if not read_only:
            self._ensure_schema()

    def close(self):
        self.conn.close()

    # ── Schema ──────────────────────────────────────────────

    def _ensure_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                date        DATE NOT NULL,
                symbol      VARCHAR NOT NULL,
                close       DOUBLE,
                open        DOUBLE,
                high        DOUBLE,
                low         DOUBLE,
                source      VARCHAR,
                is_real     BOOLEAN DEFAULT FALSE,
                updated_at  TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (date, symbol, is_real)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS economic_indicators (
                date        DATE NOT NULL,
                indicator   VARCHAR NOT NULL,
                value       DOUBLE NOT NULL,
                source      VARCHAR,
                updated_at  TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (date, indicator)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS yoy_returns (
                date        DATE NOT NULL,
                symbol      VARCHAR NOT NULL,
                yoy_pct     DOUBLE NOT NULL,
                period      VARCHAR DEFAULT 'annual',
                updated_at  TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (date, symbol, period)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS zscores (
                calc_date   DATE NOT NULL,
                symbol      VARCHAR NOT NULL,
                metric      VARCHAR NOT NULL,
                window_years INTEGER,
                zscore      DOUBLE NOT NULL,
                mean_val    DOUBLE,
                stdev_val   DOUBLE,
                current_val DOUBLE,
                updated_at  TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (calc_date, symbol, metric)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS composite_scores (
                calc_date       DATE NOT NULL,
                s_gold          DOUBLE DEFAULT 0,
                s_silver        DOUBLE NOT NULL,
                s_sp500         DOUBLE DEFAULT 0,
                s_ndx           DOUBLE DEFAULT 0,
                s_precious      DOUBLE DEFAULT 0,
                s_etf           DOUBLE NOT NULL,
                r_group         DOUBLE DEFAULT 0,
                r_precious      DOUBLE DEFAULT 0,
                r_etf_internal  DOUBLE DEFAULT 0,
                signal_label    VARCHAR,
                precious_pct    INTEGER DEFAULT 50,
                gold_pct        INTEGER DEFAULT 50,
                silver_pct      INTEGER DEFAULT 50,
                sp500_pct       INTEGER DEFAULT 60,
                ndx_pct         INTEGER DEFAULT 40,
                dd_silver       DOUBLE,
                dd_etf          DOUBLE,
                dd_correction   DOUBLE DEFAULT 0,
                weights_hash    VARCHAR,
                updated_at      TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (calc_date)
            )
        """)
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS comments_seq START 1
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id          INTEGER PRIMARY KEY DEFAULT nextval('comments_seq'),
                date        TIMESTAMP NOT NULL,
                author      VARCHAR DEFAULT 'claude',
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT current_timestamp
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS data_sync_log (
                source      VARCHAR PRIMARY KEY,
                last_sync   TIMESTAMP NOT NULL,
                rows_added  INTEGER DEFAULT 0,
                status      VARCHAR DEFAULT 'ok',
                error_msg   TEXT
            )
        """)

    # ── Write methods ───────────────────────────────────────

    def upsert_prices(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        self.conn.register("_tmp_prices", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO prices (date, symbol, close, open, high, low, source, is_real)
            SELECT date, symbol, close, open, high, low, source, is_real
            FROM _tmp_prices
        """)
        self.conn.unregister("_tmp_prices")
        return len(df)

    def upsert_economic_indicators(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        self.conn.register("_tmp_indicators", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO economic_indicators (date, indicator, value, source)
            SELECT date, indicator, value, source
            FROM _tmp_indicators
        """)
        self.conn.unregister("_tmp_indicators")
        return len(df)

    def upsert_yoy_returns(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        self.conn.register("_tmp_yoy", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO yoy_returns (date, symbol, yoy_pct, period)
            SELECT date, symbol, yoy_pct, period
            FROM _tmp_yoy
        """)
        self.conn.unregister("_tmp_yoy")
        return len(df)

    def upsert_zscores(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        self.conn.register("_tmp_zscores", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO zscores
                (calc_date, symbol, metric, window_years, zscore, mean_val, stdev_val, current_val)
            SELECT calc_date, symbol, metric, window_years, zscore, mean_val, stdev_val, current_val
            FROM _tmp_zscores
        """)
        self.conn.unregister("_tmp_zscores")
        return len(df)

    def upsert_composite_scores(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        self.conn.register("_tmp_composite", df)
        self.conn.execute("""
            INSERT OR REPLACE INTO composite_scores
                (calc_date, s_gold, s_silver, s_sp500, s_ndx,
                 s_precious, s_etf, r_group, r_precious, r_etf_internal,
                 signal_label, precious_pct, gold_pct, silver_pct, sp500_pct, ndx_pct,
                 dd_silver, dd_etf, dd_correction, weights_hash)
            SELECT calc_date, s_gold, s_silver, s_sp500, s_ndx,
                   s_precious, s_etf, r_group, r_precious, r_etf_internal,
                   signal_label, precious_pct, gold_pct, silver_pct, sp500_pct, ndx_pct,
                   dd_silver, dd_etf, dd_correction, weights_hash
            FROM _tmp_composite
        """)
        self.conn.unregister("_tmp_composite")
        return len(df)

    def add_comment(self, comment_dt: datetime, content: str, author: str = "claude") -> int:
        result = self.conn.execute(
            "INSERT INTO comments (date, author, content) VALUES (?, ?, ?) RETURNING id",
            [comment_dt, author, content],
        ).fetchone()
        return result[0]

    def log_sync(
        self,
        source: str,
        rows_added: int,
        status: str = "ok",
        error_msg: str | None = None,
    ):
        self.conn.execute(
            """
            INSERT OR REPLACE INTO data_sync_log (source, last_sync, rows_added, status, error_msg)
            VALUES (?, current_timestamp, ?, ?, ?)
            """,
            [source, rows_added, status, error_msg],
        )

    # ── Read methods ────────────────────────────────────────

    def get_prices(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        is_real: bool = False,
    ) -> pd.DataFrame:
        query = "SELECT * FROM prices WHERE symbol = ? AND is_real = ?"
        params: list = [symbol, is_real]
        if start:
            query += " AND date >= ?"
            params.append(start)
        if end:
            query += " AND date <= ?"
            params.append(end)
        query += " ORDER BY date"
        return self.conn.execute(query, params).fetchdf()

    def get_indicator(
        self,
        indicator: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        query = "SELECT * FROM economic_indicators WHERE indicator = ?"
        params: list = [indicator]
        if start:
            query += " AND date >= ?"
            params.append(start)
        if end:
            query += " AND date <= ?"
            params.append(end)
        query += " ORDER BY date"
        return self.conn.execute(query, params).fetchdf()

    def get_yoy_returns(
        self, symbol: str, period: str = "annual"
    ) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM yoy_returns WHERE symbol = ? AND period = ? ORDER BY date",
            [symbol, period],
        ).fetchdf()

    def get_latest_zscores(self, symbol: str | None = None) -> pd.DataFrame:
        if symbol:
            return self.conn.execute(
                """
                SELECT * FROM zscores
                WHERE calc_date = (SELECT MAX(calc_date) FROM zscores)
                AND symbol = ?
                ORDER BY metric
                """,
                [symbol],
            ).fetchdf()
        return self.conn.execute(
            """
            SELECT * FROM zscores
            WHERE calc_date = (SELECT MAX(calc_date) FROM zscores)
            ORDER BY symbol, metric
            """,
        ).fetchdf()

    def get_latest_composite(self) -> dict | None:
        result = self.conn.execute(
            """
            SELECT * FROM composite_scores
            ORDER BY calc_date DESC LIMIT 1
            """
        ).fetchdf()
        if result.empty:
            return None
        return result.iloc[0].to_dict()

    def get_composite_history(
        self, start: date | None = None
    ) -> pd.DataFrame:
        query = "SELECT * FROM composite_scores"
        params: list = []
        if start:
            query += " WHERE calc_date >= ?"
            params.append(start)
        query += " ORDER BY calc_date"
        return self.conn.execute(query, params).fetchdf()

    def get_comments(
        self, start: date | None = None, limit: int = 50
    ) -> pd.DataFrame:
        query = "SELECT * FROM comments"
        params: list = []
        if start:
            query += " WHERE date >= ?"
            params.append(start)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchdf()

    def get_sync_status(self) -> pd.DataFrame:
        return self.conn.execute(
            "SELECT * FROM data_sync_log ORDER BY last_sync DESC"
        ).fetchdf()

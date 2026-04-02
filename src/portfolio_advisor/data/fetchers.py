from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# ── Macrotrends CSV ─────────────────────────────────────────


def fetch_silver_historical_csv(csv_path: str) -> pd.DataFrame:
    """Parse Macrotrends silver historical CSV from data/raw/.

    Macrotrends CSV typically has columns like:
    date, value (or year, average_closing_price, year_open, year_high, year_low, year_close)
    The parser auto-detects the format.
    """
    path = Path(csv_path)
    if not path.is_file():
        logger.warning("Macrotrends CSV not found at %s, skipping", csv_path)
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Auto-detect column names
    date_col = _find_column(df, ["date", "year"])
    close_col = _find_column(df, ["close", "value", "year_close", "average_closing_price"])

    if date_col is None or close_col is None:
        raise ValueError(
            f"Cannot detect date/close columns in CSV. Found: {list(df.columns)}"
        )

    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df[date_col]).dt.date
    result["symbol"] = "SILVER"
    result["close"] = pd.to_numeric(df[close_col], errors="coerce")

    open_col = _find_column(df, ["open", "year_open"])
    high_col = _find_column(df, ["high", "year_high"])
    low_col = _find_column(df, ["low", "year_low"])

    result["open"] = pd.to_numeric(df[open_col], errors="coerce") if open_col else None
    result["high"] = pd.to_numeric(df[high_col], errors="coerce") if high_col else None
    result["low"] = pd.to_numeric(df[low_col], errors="coerce") if low_col else None
    result["source"] = "macrotrends"
    result["is_real"] = False

    result = result.dropna(subset=["close"])
    return result


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find the first matching column name from candidates."""
    for name in candidates:
        if name in df.columns:
            return name
    return None


# ── yfinance ────────────────────────────────────────────────


def fetch_yfinance_symbol(
    symbol: str,
    display_name: str,
    start: str = "1970-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Fetch historical data from yfinance with retry logic.

    Returns standardized DataFrame: date, symbol, open, high, low, close, source, is_real.
    """
    import yfinance as yf

    for attempt in range(3):
        try:
            kwargs = {"start": start}
            if end:
                kwargs["end"] = end
            raw = yf.download(symbol, progress=False, **kwargs)
            if raw.empty:
                logger.warning("yfinance returned empty data for %s", symbol)
                return pd.DataFrame()
            break
        except Exception as e:
            if attempt < 2:
                wait = 2**attempt
                logger.warning(
                    "yfinance retry %d for %s: %s (waiting %ds)",
                    attempt + 1, symbol, e, wait,
                )
                time.sleep(wait)
            else:
                logger.error("yfinance failed after 3 attempts for %s: %s", symbol, e)
                return pd.DataFrame()

    # yfinance returns MultiIndex columns when downloading single ticker
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel("Ticker")

    result = pd.DataFrame()
    result["date"] = raw.index.date
    result["symbol"] = display_name
    result["close"] = raw["Close"].values
    result["open"] = raw["Open"].values if "Open" in raw.columns else None
    result["high"] = raw["High"].values if "High" in raw.columns else None
    result["low"] = raw["Low"].values if "Low" in raw.columns else None
    result["source"] = "yfinance"
    result["is_real"] = False

    return result


# ── Shiller Data ────────────────────────────────────────────


def download_shiller_excel(url: str, save_path: str) -> str:
    """Download Shiller ie_data.xls to data/raw/."""
    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    path.write_bytes(resp.content)
    logger.info("Downloaded Shiller data to %s", save_path)
    return str(path)


def fetch_shiller_excel(xls_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse Shiller ie_data.xls.

    Returns:
        (prices_df, indicators_df) where:
        - prices_df has S&P500 prices (date, symbol, close, source, is_real)
        - indicators_df has CAPE ratio (date, indicator, value, source)
    """
    path = Path(xls_path)
    if not path.is_file():
        logger.warning("Shiller Excel not found at %s, skipping", xls_path)
        return pd.DataFrame(), pd.DataFrame()

    # Shiller data starts at row 8 (0-indexed: skip first 7 rows)
    raw = pd.read_excel(xls_path, sheet_name="Data", header=None, skiprows=7)

    # Column mapping (based on Shiller's standard layout):
    # 0: Date (YYYY.MM), 1: S&P Comp. Price, 2: Dividend, 3: Earnings,
    # 4: CPI, 5: Date Fraction, 6: Long Interest Rate, 7: Real Price,
    # 8: Real Dividend, 9: Real Total Return Price, 10: Real Earnings,
    # 11: Real TR Scaled Earnings, 12: CAPE, ...

    # Filter rows with valid date
    df = raw[raw[0].notna()].copy()
    df = df[df[0].apply(lambda x: _is_shiller_date(x))].copy()

    # Parse dates: "2024.01" → 2024-01-01
    df["date"] = df[0].apply(_parse_shiller_date)
    df = df.dropna(subset=["date"])

    # S&P500 prices
    prices_df = pd.DataFrame()
    prices_df["date"] = df["date"]
    prices_df["symbol"] = "SP500"
    prices_df["close"] = pd.to_numeric(df[1], errors="coerce")
    prices_df["open"] = None
    prices_df["high"] = None
    prices_df["low"] = None
    prices_df["source"] = "shiller"
    prices_df["is_real"] = False
    prices_df = prices_df.dropna(subset=["close"])

    # CAPE Ratio
    cape_col = 12 if len(raw.columns) > 12 else None
    indicators_df = pd.DataFrame()
    if cape_col is not None:
        indicators_df["date"] = df["date"]
        indicators_df["indicator"] = "CAPE"
        indicators_df["value"] = pd.to_numeric(df[cape_col], errors="coerce")
        indicators_df["source"] = "shiller"
        indicators_df = indicators_df.dropna(subset=["value"])

    return prices_df, indicators_df


def _is_shiller_date(val) -> bool:
    """Check if value looks like a Shiller date (YYYY.MM or YYYY)."""
    try:
        s = str(val).strip()
        if "." in s:
            parts = s.split(".")
            year = int(parts[0])
            return 1800 <= year <= 2100
        year = int(float(s))
        return 1800 <= year <= 2100
    except (ValueError, TypeError):
        return False


def _parse_shiller_date(val):
    """Parse Shiller date format 'YYYY.MM' → date object."""
    from datetime import date

    try:
        s = str(val).strip()
        if "." in s:
            parts = s.split(".")
            year = int(parts[0])
            month_str = parts[1].ljust(2, "0")[:2]
            month = int(month_str)
            month = max(1, min(12, month))
            return date(year, month, 1)
        year = int(float(s))
        return date(year, 1, 1)
    except (ValueError, TypeError):
        return None


# ── FRED ────────────────────────────────────────────────────


def fetch_fred_series(
    series_id: str, api_key: str, start: str | None = None
) -> pd.DataFrame:
    """Fetch a FRED data series using fredapi."""
    from fredapi import Fred

    fred = Fred(api_key=api_key)
    kwargs = {}
    if start:
        kwargs["observation_start"] = start

    try:
        series = fred.get_series(series_id, **kwargs)
    except Exception as e:
        logger.error("FRED fetch failed for %s: %s", series_id, e)
        return pd.DataFrame()

    if series.empty:
        return pd.DataFrame()

    result = pd.DataFrame()
    result["date"] = series.index.date
    result["indicator"] = series_id
    result["value"] = series.values
    result["source"] = "fred"
    result = result.dropna(subset=["value"])

    return result


def fetch_real_rate(api_key: str, start: str | None = None) -> pd.DataFrame:
    return fetch_fred_series("REAINTRATREARAT10Y", api_key, start)


def fetch_m2(api_key: str, start: str | None = None) -> pd.DataFrame:
    return fetch_fred_series("M2SL", api_key, start)


def fetch_gdp(api_key: str, start: str | None = None) -> pd.DataFrame:
    return fetch_fred_series("GDP", api_key, start)


def fetch_treasury_10y(api_key: str, start: str | None = None) -> pd.DataFrame:
    return fetch_fred_series("DGS10", api_key, start)


def fetch_treasury_3m(api_key: str, start: str | None = None) -> pd.DataFrame:
    return fetch_fred_series("DGS3MO", api_key, start)


# ── Finnhub News ───────────────────────────────────────


ASSET_KEYWORDS = {
    "gold": ["gold", "bullion", "precious metal", "real rate", "real yield", "fed rate", "central bank gold"],
    "silver": ["silver", "precious metal", "gold silver ratio"],
    "equity": ["s&p", "nasdaq", "stock market", "earnings", "gdp", "employment", "wall street"],
    "macro": ["fed", "interest rate", "inflation", "cpi", "treasury", "yield curve", "trade war", "tariff"],
}


def fetch_finnhub_news(api_key: str, category: str = "general", days: int = 7) -> list[dict]:
    """Finnhub 시장 뉴스 수집. 센티먼트 스코어 포함."""
    from datetime import datetime, timedelta

    if not api_key:
        return []

    start = datetime.now() - timedelta(days=days)

    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/news",
            params={
                "category": category,
                "minId": 0,
                "token": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        articles = resp.json()
    except Exception as e:
        logger.error("Finnhub news fetch failed: %s", e)
        return []

    cutoff = start.timestamp()
    results = []
    for a in articles:
        if a.get("datetime", 0) < cutoff:
            continue
        results.append({
            "headline": a.get("headline", ""),
            "summary": a.get("summary", ""),
            "source": a.get("source", ""),
            "datetime": a.get("datetime", 0),
            "url": a.get("url", ""),
            "related": a.get("related", ""),
        })

    return results


def filter_news_by_asset(articles: list[dict], asset_type: str) -> list[dict]:
    """자산 유형에 맞는 뉴스만 필터링."""
    keywords = ASSET_KEYWORDS.get(asset_type, [])
    if not keywords:
        return articles

    filtered = []
    for a in articles:
        text = (a.get("headline", "") + " " + a.get("summary", "")).lower()
        if any(kw in text for kw in keywords):
            filtered.append(a)

    return filtered


# ── Derived ─────────────────────────────────────────────────


def calculate_gold_silver_ratio(
    gold_df: pd.DataFrame, silver_df: pd.DataFrame
) -> pd.DataFrame:
    """Calculate Gold/Silver Ratio from gold and silver price DataFrames."""
    if gold_df.empty or silver_df.empty:
        return pd.DataFrame()

    gold = gold_df[["date", "close"]].rename(columns={"close": "gold_close"})
    silver = silver_df[["date", "close"]].rename(columns={"close": "silver_close"})

    merged = pd.merge(gold, silver, on="date", how="inner")
    merged = merged[merged["silver_close"] > 0]

    result = pd.DataFrame()
    result["date"] = merged["date"]
    result["indicator"] = "GSR"
    result["value"] = merged["gold_close"] / merged["silver_close"]
    result["source"] = "calculated"

    return result


def calculate_m2_gold_ratio(
    m2_df: pd.DataFrame, gold_df: pd.DataFrame
) -> pd.DataFrame:
    """M2 통화량 / 금 가격 비율. 높을수록 금이 통화량 대비 저평가."""
    if m2_df.empty or gold_df.empty:
        return pd.DataFrame()

    m2 = m2_df[["date", "value"]].rename(columns={"value": "m2"})
    gold = gold_df[["date", "close"]].rename(columns={"close": "gold_close"})

    # M2는 월별, 금은 일별 -> M2를 월 기준으로 merge
    m2["date"] = pd.to_datetime(m2["date"])
    gold["date"] = pd.to_datetime(gold["date"])
    m2["month_key"] = m2["date"].dt.to_period("M")
    gold["month_key"] = gold["date"].dt.to_period("M")

    # 월별 금 평균가
    gold_monthly = gold.groupby("month_key")["gold_close"].mean().reset_index()
    merged = pd.merge(m2, gold_monthly, on="month_key", how="inner")
    merged = merged[merged["gold_close"] > 0]

    result = pd.DataFrame()
    result["date"] = merged["date"].dt.date
    result["indicator"] = "M2_GOLD"
    result["value"] = (merged["m2"] * 1_000_000_000) / merged["gold_close"]  # M2는 billions
    result["source"] = "calculated"

    return result


def calculate_buffett_indicator(
    gdp_df: pd.DataFrame, sp500_df: pd.DataFrame
) -> pd.DataFrame:
    """Buffett Indicator: 시가총액 / GDP. Wilshire 5000 대용으로 S&P500 사용."""
    if gdp_df.empty or sp500_df.empty:
        return pd.DataFrame()

    gdp = gdp_df[["date", "value"]].rename(columns={"value": "gdp"})
    sp500 = sp500_df[["date", "close"]].rename(columns={"close": "sp500"})

    gdp["date"] = pd.to_datetime(gdp["date"])
    sp500["date"] = pd.to_datetime(sp500["date"])

    # GDP는 분기별 -> forward fill해서 일별로 확장
    gdp = gdp.set_index("date").resample("D").ffill().reset_index()

    merged = pd.merge(sp500, gdp, on="date", how="inner")
    merged = merged[merged["gdp"] > 0]

    # S&P500 레벨을 시총 프록시로 사용 (비율의 추세만 중요)
    result = pd.DataFrame()
    result["date"] = merged["date"].dt.date
    result["indicator"] = "BUFFETT"
    result["value"] = (merged["sp500"] / merged["gdp"]) * 100  # 퍼센트 스케일
    result["source"] = "calculated"

    return result


def calculate_yield_curve(
    t10y_df: pd.DataFrame, t3m_df: pd.DataFrame
) -> pd.DataFrame:
    """Yield Curve 스프레드: 10년 - 3개월 국채 금리."""
    if t10y_df.empty or t3m_df.empty:
        return pd.DataFrame()

    t10y = t10y_df[["date", "value"]].rename(columns={"value": "t10y"})
    t3m = t3m_df[["date", "value"]].rename(columns={"value": "t3m"})

    merged = pd.merge(t10y, t3m, on="date", how="inner")

    result = pd.DataFrame()
    result["date"] = merged["date"]
    result["indicator"] = "YIELD_CURVE"
    result["value"] = merged["t10y"] - merged["t3m"]
    result["source"] = "calculated"

    return result

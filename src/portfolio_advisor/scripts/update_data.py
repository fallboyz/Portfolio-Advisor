from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from portfolio_advisor.analysis.signal import compute_full_signal
from portfolio_advisor.analysis.zscore import calculate_yoy_returns
from portfolio_advisor.config import load_config
from portfolio_advisor.data.fetchers import (
    calculate_buffett_indicator,
    calculate_gold_silver_ratio,
    calculate_m2_gold_ratio,
    calculate_yield_curve,
    download_shiller_excel,
    fetch_gdp,
    fetch_m2,
    fetch_real_rate,
    fetch_shiller_excel,
    fetch_silver_historical_csv,
    fetch_treasury_10y,
    fetch_treasury_3m,
    fetch_yfinance_symbol,
)
from portfolio_advisor.data.store import Store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    config = load_config()
    db_path = config["data"]["db_path"]
    store = Store(db_path)

    try:
        _run_pipeline(store, config)
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
    finally:
        store.close()

    logger.info("Pipeline completed successfully")


def _run_pipeline(store: Store, config: dict):
    sync_status = _get_sync_dict(store)

    # Phase 1: Fetch raw data
    logger.info("=== Phase 1: Fetching raw data ===")
    _fetch_macrotrends(store, config, sync_status)
    _fetch_yfinance_all(store, config, sync_status)
    _fetch_shiller(store, config, sync_status)
    _fetch_fred(store, config, sync_status)

    # Phase 2: Derived calculations
    logger.info("=== Phase 2: Derived calculations ===")
    _compute_gsr(store)
    _compute_m2_gold(store)
    _compute_buffett(store)
    _compute_yield_curve(store)
    _compute_yoy_returns(store)

    # Phase 3: Analysis
    logger.info("=== Phase 3: Analysis ===")
    result = compute_full_signal(store, config)
    if "error" in result:
        logger.warning("Signal computation returned error: %s", result["error"])
    else:
        logger.info(
            "Signal: %s (R=%.2f, Precious %d%%)",
            result["signal"]["label"],
            result["r_group"],
            result["signal"]["precious_pct"],
        )
        # Auto-generate comment
        store.add_comment(datetime.now(), result["comment"], author="system")


def _get_sync_dict(store: Store) -> dict:
    """Get sync status as a dict keyed by source name."""
    df = store.get_sync_status()
    if df.empty:
        return {}
    return {row["source"]: row for _, row in df.iterrows()}


def _start_date_for(sync_status: dict, source: str) -> str | None:
    """Determine start date for incremental fetch."""
    if source in sync_status:
        last = sync_status[source]["last_sync"]
        if isinstance(last, (datetime, pd.Timestamp)):
            return last.strftime("%Y-%m-%d")
    return None


# ── Macrotrends CSV ─────────────────────────────────────────


def _fetch_macrotrends(store: Store, config: dict, sync_status: dict):
    csv_path = config["data"]["macrotrends_csv"]
    source = "macrotrends_csv"

    if not Path(csv_path).is_file():
        logger.info("Macrotrends CSV not found at %s, skipping", csv_path)
        return

    # Check file modification time
    file_mtime = datetime.fromtimestamp(Path(csv_path).stat().st_mtime)
    if source in sync_status:
        last_sync = sync_status[source]["last_sync"]
        if isinstance(last_sync, (datetime, pd.Timestamp)) and file_mtime <= last_sync:
            logger.info("Macrotrends CSV unchanged since last sync, skipping")
            return

    try:
        df = fetch_silver_historical_csv(csv_path)
        count = store.upsert_prices(df)
        store.log_sync(source, count)
        logger.info("Macrotrends: loaded %d rows", count)
    except Exception as e:
        logger.error("Macrotrends fetch failed: %s", e)
        store.log_sync(source, 0, status="error", error_msg=str(e))


# ── yfinance ────────────────────────────────────────────────


def _fetch_yfinance_all(store: Store, config: dict, sync_status: dict):
    symbols = config["symbols"]
    yf_map = {
        "silver": ("SILVER", symbols["silver"]),
        "gold": ("GOLD", symbols["gold"]),
        "sp500": ("SP500", symbols["sp500"]),
        "ndx": ("NDX", symbols["ndx"]),
        "dxy": ("DXY", symbols["dxy"]),
        "vix": ("VIX", symbols["vix"]),
    }

    for key, (display_name, ticker) in yf_map.items():
        source = f"yfinance_{key}"
        start = _start_date_for(sync_status, source) or "1970-01-01"

        try:
            df = fetch_yfinance_symbol(ticker, display_name, start=start)
            count = store.upsert_prices(df)
            store.log_sync(source, count)
            logger.info("yfinance %s: loaded %d rows", display_name, count)
        except Exception as e:
            logger.error("yfinance %s failed: %s", display_name, e)
            store.log_sync(source, 0, status="error", error_msg=str(e))


# ── Shiller ─────────────────────────────────────────────────


def _fetch_shiller(store: Store, config: dict, sync_status: dict):
    source = "shiller"
    xls_path = config["data"]["shiller_excel"]
    xls_url = config["data"]["shiller_url"]

    # Re-download if older than 7 days or not present
    need_download = True
    if source in sync_status:
        last = sync_status[source]["last_sync"]
        if isinstance(last, (datetime, pd.Timestamp)):
            days_since = (datetime.now() - last).days if isinstance(last, datetime) else (datetime.now() - last.to_pydatetime()).days
            if days_since < 7 and Path(xls_path).is_file():
                need_download = False
                logger.info("Shiller data is fresh (%d days old), skipping download", days_since)

    if need_download:
        try:
            download_shiller_excel(xls_url, xls_path)
        except Exception as e:
            logger.error("Shiller download failed: %s", e)
            if not Path(xls_path).is_file():
                store.log_sync(source, 0, status="error", error_msg=str(e))
                return

    try:
        prices_df, indicators_df = fetch_shiller_excel(xls_path)
        count_prices = store.upsert_prices(prices_df)
        count_indicators = store.upsert_economic_indicators(indicators_df)
        total = count_prices + count_indicators
        store.log_sync(source, total)
        logger.info("Shiller: loaded %d price rows + %d indicator rows", count_prices, count_indicators)
    except Exception as e:
        logger.error("Shiller parse failed: %s", e)
        store.log_sync(source, 0, status="error", error_msg=str(e))


# ── FRED ────────────────────────────────────────────────────


def _fetch_fred(store: Store, config: dict, sync_status: dict):
    api_key = config["api_keys"]["fred"]
    if not api_key or api_key in ("your_fred_api_key", "your_fred_api_key_here", ""):
        logger.warning("FRED API key not configured, skipping FRED data")
        return

    for name, fetcher in [
        ("fred_real_rate", fetch_real_rate),
        ("fred_m2", fetch_m2),
        ("fred_gdp", fetch_gdp),
        ("fred_treasury_10y", fetch_treasury_10y),
        ("fred_treasury_3m", fetch_treasury_3m),
    ]:
        start = _start_date_for(sync_status, name)
        try:
            df = fetcher(api_key, start=start)
            count = store.upsert_economic_indicators(df)
            store.log_sync(name, count)
            logger.info("FRED %s: loaded %d rows", name, count)
        except Exception as e:
            logger.error("FRED %s failed: %s", name, e)
            store.log_sync(name, 0, status="error", error_msg=str(e))


# ── Derived ─────────────────────────────────────────────────


def _compute_gsr(store: Store):
    """Compute and store Gold/Silver Ratio from price data."""
    gold = store.get_prices("GOLD")
    silver = store.get_prices("SILVER")

    if gold.empty or silver.empty:
        logger.warning("Missing gold or silver prices, skipping GSR calculation")
        return

    gsr = calculate_gold_silver_ratio(gold, silver)
    count = store.upsert_economic_indicators(gsr)
    logger.info("GSR: computed %d rows", count)


def _compute_m2_gold(store: Store):
    m2 = store.get_indicator("M2SL")
    gold = store.get_prices("GOLD")
    if m2.empty or gold.empty:
        logger.warning("Missing M2 or gold prices, skipping M2/Gold calculation")
        return
    df = calculate_m2_gold_ratio(m2, gold)
    count = store.upsert_economic_indicators(df)
    logger.info("M2/Gold: computed %d rows", count)


def _compute_buffett(store: Store):
    gdp = store.get_indicator("GDP")
    sp500 = store.get_prices("SP500")
    if gdp.empty or sp500.empty:
        logger.warning("Missing GDP or SP500 prices, skipping Buffett Indicator")
        return
    df = calculate_buffett_indicator(gdp, sp500)
    count = store.upsert_economic_indicators(df)
    logger.info("Buffett Indicator: computed %d rows", count)


def _compute_yield_curve(store: Store):
    t10y = store.get_indicator("DGS10")
    t3m = store.get_indicator("DGS3MO")
    if t10y.empty or t3m.empty:
        logger.warning("Missing treasury data, skipping Yield Curve")
        return
    df = calculate_yield_curve(t10y, t3m)
    count = store.upsert_economic_indicators(df)
    logger.info("Yield Curve: computed %d rows", count)


def _compute_yoy_returns(store: Store):
    """Compute and store YoY returns for all symbols."""
    for symbol in ["SILVER", "GOLD", "SP500", "NDX"]:
        prices = store.get_prices(symbol)
        if prices.empty:
            continue

        yoy = calculate_yoy_returns(prices, freq="annual")
        if yoy.empty:
            continue

        yoy["symbol"] = symbol
        yoy["period"] = "annual"
        count = store.upsert_yoy_returns(yoy)
        logger.info("YoY %s: computed %d rows", symbol, count)


if __name__ == "__main__":
    main()

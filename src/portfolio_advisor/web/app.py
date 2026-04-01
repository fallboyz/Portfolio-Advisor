from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from portfolio_advisor.config import load_config
from portfolio_advisor.data.store import Store

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent


# ── Scheduler ──────────────────────────────────────────

def _parse_cron_hour_minute(cron_expr: str) -> tuple[int, int]:
    """'0 3 * * *' -> (3, 0)"""
    parts = cron_expr.strip().split()
    return int(parts[1]), int(parts[0])


def _seconds_until(hour: int, minute: int) -> float:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _run_scheduler(stop_event: threading.Event):
    config = load_config()
    cron_expr = config.get("schedule", {}).get("data_update", "0 3 * * *")
    hour, minute = _parse_cron_hour_minute(cron_expr)
    logger.info("Scheduler started: daily update at %02d:%02d", hour, minute)

    while not stop_event.is_set():
        wait_secs = _seconds_until(hour, minute)
        logger.info("Scheduler: next run in %.0f seconds", wait_secs)
        if stop_event.wait(wait_secs):
            break
        logger.info("Scheduler: running daily update")
        try:
            from portfolio_advisor.scripts.update_data import _run_pipeline

            store = Store(config["data"]["db_path"])
            try:
                _run_pipeline(store, config)
                logger.info("Scheduler: update completed")
            finally:
                store.close()
        except Exception:
            logger.exception("Scheduler: update failed")
        stop_event.wait(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = threading.Event()
    t = threading.Thread(target=_run_scheduler, args=(stop_event,), daemon=True)
    t.start()
    yield
    stop_event.set()


app = FastAPI(title="Portfolio Advisor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@contextmanager
def _open_store():
    config = load_config()
    store = Store(config["data"]["db_path"], read_only=True)
    try:
        yield store
    finally:
        store.close()


def _serialize(obj: dict) -> dict:
    return {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in obj.items()}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


# ── JSON API ───────────────────────────────────────────

@app.get("/api/latest")
def api_latest():
    with _open_store() as store:
        latest = store.get_latest_composite()
        if latest is None:
            return {"error": "no data"}
        return _serialize(latest)


@app.get("/api/history")
def api_history():
    with _open_store() as store:
        df = store.get_composite_history()
        rows = []
        dates = []
        for _, r in df.iterrows():
            rows.append(_serialize(r.to_dict()))
            cd = r["calc_date"]
            at = r["analyzed_at"]
            dates.append({
                "calc_date": cd.date().isoformat() if hasattr(cd, "date") else str(cd),
                "analyzed_at": at.isoformat() if hasattr(at, "isoformat") else str(at),
            })
        dates.reverse()
        return {
            "dates": dates,
            "history": rows,
        }


@app.get("/api/prices/{symbol}")
def api_prices(symbol: str, years: int = Query(default=1, ge=0, le=100)):
    symbol_upper = symbol.upper()
    with _open_store() as store:
        if years > 0:
            start = date.today() - timedelta(days=years * 365)
            df = store.get_prices(symbol_upper, start=start)
        else:
            df = store.get_prices(symbol_upper)
        if df.empty:
            return {"dates": [], "closes": []}
        return {
            "dates": [d.isoformat() if isinstance(d, date) else str(d) for d in df["date"]],
            "closes": [round(float(c), 2) for c in df["close"]],
        }


@app.get("/api/zscores")
def api_zscores():
    with _open_store() as store:
        df = store.get_latest_zscores()
        if df.empty:
            return {"symbols": [], "metrics": [], "values": []}
        pivot = df.pivot_table(index="metric", columns="symbol", values="zscore")
        values = []
        for row in pivot.values:
            values.append([round(float(v), 2) if not pd.isna(v) else None for v in row])
        return {
            "symbols": pivot.columns.tolist(),
            "metrics": pivot.index.tolist(),
            "values": values,
        }


@app.get("/api/indicators/{name}")
def api_indicators(name: str):
    with _open_store() as store:
        df = store.get_indicator(name.upper())
        if df.empty:
            return {"dates": [], "values": []}
        return {
            "dates": [d.isoformat() if isinstance(d, date) else str(d) for d in df["date"]],
            "values": [round(float(v), 2) for v in df["value"]],
        }


@app.get("/api/analysis/{analysis_date}")
def api_analysis(analysis_date: str, analyzed_at: str | None = None):
    try:
        target = date.fromisoformat(analysis_date)
    except ValueError:
        return {"error": "invalid date format"}
    analyzed_at_dt = None
    if analyzed_at:
        try:
            analyzed_at_dt = datetime.fromisoformat(analyzed_at)
        except ValueError:
            pass
    with _open_store() as store:
        composite = store.get_composite_by_date(target, analyzed_at=analyzed_at_dt)
        zscores = store.get_zscores_by_date(target)
        comments = store.get_comments_near(analyzed_at_dt) if analyzed_at_dt else store.get_comments_by_date(target)

        if composite is None:
            return {"error": "no data for this date"}

        comp_dict = _serialize(composite)

        zs_list = []
        for _, r in zscores.iterrows():
            zs_list.append({
                "symbol": r["symbol"],
                "metric": r["metric"],
                "zscore": round(float(r["zscore"]), 2),
                "mean_val": round(float(r["mean_val"]), 2) if not pd.isna(r["mean_val"]) else None,
                "stdev_val": round(float(r["stdev_val"]), 2) if not pd.isna(r["stdev_val"]) else None,
                "current_val": round(float(r["current_val"]), 2) if not pd.isna(r["current_val"]) else None,
            })

        comment_list = []
        for _, r in comments.iterrows():
            comment_list.append({
                "author": r["author"],
                "content": r["content"],
                "date": str(r["date"]),
            })

        return {
            "composite": comp_dict,
            "zscores": zs_list,
            "comments": comment_list,
        }


def main():
    config = load_config()
    port = config.get("server", {}).get("web_port", 8501)
    uvicorn.run(
        "portfolio_advisor.web.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()

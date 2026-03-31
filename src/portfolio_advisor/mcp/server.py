from __future__ import annotations

from datetime import date

from fastmcp import FastMCP

from portfolio_advisor.analysis.signal import SIGNAL_KO
from portfolio_advisor.config import load_config
from portfolio_advisor.data.store import Store

mcp = FastMCP("Portfolio Advisor")

_store: Store | None = None


def _get_store() -> Store:
    global _store
    if _store is None:
        config = load_config()
        _store = Store(config["data"]["db_path"])
    return _store


@mcp.tool()
def get_scores() -> dict:
    """현재 복합 점수 및 Z-Score 전체 조회."""
    store = _get_store()
    latest = store.get_latest_composite()
    zscores = store.get_latest_zscores()

    return {
        "composite": latest,
        "zscores": zscores.to_dict("records") if not zscores.empty else [],
    }


@mcp.tool()
def get_signals() -> dict:
    """현재 비율 조정 신호 및 해석."""
    store = _get_store()
    latest = store.get_latest_composite()

    if latest is None:
        return {"error": "분석 데이터 없음"}

    signal_info = SIGNAL_KO.get(latest["signal_label"], SIGNAL_KO["neutral"])

    return {
        "r_group": latest["r_group"],
        "signal_label": latest["signal_label"],
        "signal_desc": signal_info["label"],
        "interpretation": signal_info["desc"],
        "precious_pct": latest["precious_pct"],
        "gold_pct": latest["gold_pct"],
        "silver_pct": latest["silver_pct"],
        "sp500_pct": latest["sp500_pct"],
        "ndx_pct": latest["ndx_pct"],
        "s_gold": latest["s_gold"],
        "s_silver": latest["s_silver"],
        "s_precious": latest["s_precious"],
        "s_sp500": latest["s_sp500"],
        "s_ndx": latest["s_ndx"],
        "s_etf": latest["s_etf"],
        "dd_silver": latest["dd_silver"],
        "dd_etf": latest["dd_etf"],
        "calc_date": str(latest["calc_date"])[:10],
    }


@mcp.tool()
def get_history(symbol: str, start: str | None = None, end: str | None = None) -> dict:
    """특정 자산의 가격 이력 조회 (SILVER, GOLD, SP500, NDX, DXY, VIX).

    Args:
        symbol: 자산 심볼
        start: 시작일 (YYYY-MM-DD), 선택
        end: 종료일 (YYYY-MM-DD), 선택
    """
    store = _get_store()

    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None

    prices = store.get_prices(symbol, start=start_date, end=end_date)

    if len(prices) > 100:
        prices = prices.tail(100)

    return {
        "symbol": symbol,
        "total_rows": len(prices),
        "data": prices[["date", "close"]].to_dict("records") if not prices.empty else [],
    }


@mcp.tool()
def add_comment(date_str: str, content: str) -> dict:
    """분석 코멘트 기록.

    Args:
        date_str: 날짜 (YYYY-MM-DD)
        content: 코멘트 내용
    """
    store = _get_store()
    comment_date = date.fromisoformat(date_str)
    comment_id = store.add_comment(comment_date, content, author="claude")
    return {"id": comment_id, "status": "saved"}


@mcp.tool()
def get_report(period: str = "monthly") -> dict:
    """리포트 조회 (현재 신호, 최근 코멘트, 데이터 상태).

    Args:
        period: 리포트 기간 (monthly, semi_annual, annual)
    """
    store = _get_store()

    latest = store.get_latest_composite()
    comments = store.get_comments(limit=5)
    sync = store.get_sync_status()

    return {
        "period": period,
        "signal": latest if latest else {},
        "recent_comments": comments[["date", "author", "content"]].to_dict("records") if not comments.empty else [],
        "data_freshness": sync[["source", "last_sync", "status"]].to_dict("records") if not sync.empty else [],
    }


def main():
    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Mount, Route

    def health(_request):
        return PlainTextResponse("ok")

    config = load_config()
    host = config.get("server", {}).get("mcp_host", "0.0.0.0")
    port = config.get("server", {}).get("mcp_port", 8001)

    mcp_app = mcp.http_app()

    app = Starlette(
        routes=[
            Route("/health", health),
            Mount("/", app=mcp_app),
        ],
        lifespan=mcp_app.lifespan,
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

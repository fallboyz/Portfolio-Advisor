#!/bin/bash

# .env 환경 변수를 cron 환경에도 전달
env >> /etc/environment

# Start cron daemon
cron

# DB가 없으면 최초 데이터 적재 (실패해도 대시보드는 띄움)
if [ ! -f /app/data/portfolio.ddb ]; then
    echo "DB not found. Running initial data update..."
    uv run portfolio-update || echo "WARNING: Initial update failed. Dashboard will start without data."
fi

# Start MCP server in background
uv run portfolio-mcp &

# Start Streamlit (foreground, PID 1)
exec uv run streamlit run src/portfolio_advisor/ui/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true

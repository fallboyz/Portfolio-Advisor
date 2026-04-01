# Development Guide

## Quick Commands

```bash
uv sync                                          # 의존성 설치
uv run portfolio-update                          # 데이터 수집 + 분석 실행
uv run portfolio-web                             # 대시보드 실행 (FastAPI, http://localhost:8501)
uv run portfolio-mcp                             # MCP 서버 실행
uv run pytest -v                                 # 테스트
```

## Architecture

```
src/portfolio_advisor/
  config.py           - config.toml 로딩 (tomllib, @lru_cache)
  data/
    store.py          - DuckDB Store 클래스. 7개 테이블, upsert/read 메서드
    fetchers.py       - 데이터 수집 (yfinance, FRED, Shiller Excel, Macrotrends CSV, Finnhub 뉴스)
  analysis/
    zscore.py         - Z-Score 계산 (실질금리, M2/금, CAPE, Buffett, Yield Curve, GSR 등)
    composite.py      - 복합 점수 (검증된 지표 기반, 자산별 가중치)
    signal.py         - 2단계 비율 조정 신호 + Drawdown 보정
  backtest/
    engine.py         - Walk-forward 백테스트 (look-ahead bias 방지)
  mcp/
    server.py         - FastMCP Streamable HTTP (6개 도구, Finnhub 뉴스 포함)
  web/
    app.py            - FastAPI + Jinja2 대시보드 (단일 페이지)
    templates/
      index.html      - HTML 템플릿
    static/
      style.css       - 스타일시트
      app.js          - Plotly.js 차트 렌더링 + 인터랙션
  scripts/
    update_data.py    - 일일 파이프라인 (내장 스케줄러 + 수동 실행)
```

## Data Flow

```
fetchers → store (prices, indicators)
         → derived (GSR, M2/금, Buffett, Yield Curve, YoY returns)
         → zscore (Z-Score 계산)
         → composite (복합 점수)
         → signal (비율 조정 신호)
         → store (composite_scores, comments)
MCP 분석 시: finnhub → get_news (뉴스 동향 참조)
```

## Key Design Decisions

- 2단계 비율 조정: 실물 자산(금/은) vs ETF(S&P/나스닥) 그룹 + 내부 비율
- DuckDB 단일 파일: 모든 데이터 저장. 읽기/쓰기 분리 (update만 write)
- API 키는 .env 파일의 FRED_API_KEY, FINNHUB_API_KEY가 config.toml 값을 오버라이드
- FastAPI + Jinja2 + Plotly.js: 단일 페이지 대시보드, JSON API 제공
- Docker HTTP only: 인프라(HTTPS, 도메인)는 사용자 관리

## Testing

- 테스트는 in-memory DuckDB 사용 (`:memory:`)
- conftest.py에 공유 fixture (sample_prices, tmp_config)
- look-ahead bias 검증 테스트 필수 (backtest, zscore)

## Conventions

- 한국어 UI (대시보드, 코멘트, 신호 라벨)
- Pretendard 폰트
- 업비트 스타일 디자인 (단정, 깔끔, 모바일 반응형)
- Plotly.js 차트: 기본 1년 범위, modebar 세로 배치

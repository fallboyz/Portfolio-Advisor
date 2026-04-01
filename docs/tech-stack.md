# 기술 스택

| 항목 | 선택 | 근거 |
|------|------|------|
| 런타임 | Python 3.13 | tomllib 표준 내장 |
| 패키지 관리 | uv | pyproject.toml 기반, 빠름 |
| 데이터 수집 | yfinance, fredapi, openpyxl, xlrd | 무료 API |
| 데이터 저장 | DuckDB (단일 파일) | 컬럼형 분석 DB |
| 분석/계산 | pandas + numpy | 시계열 처리 표준 |
| 시각화 | Plotly.js (CDN) | 인터랙티브 차트 |
| UI | FastAPI + Jinja2 | JSON API + HTML 단일 페이지 대시보드 |
| AI 연동 | FastMCP (Streamable HTTP) | Claude 원격 데이터 조회 |
| 설정 | config.toml + .env | API 키는 .env, 나머지 설정은 config.toml |
| 스케줄러 | 컨테이너 내부 cron | 일 1회 자동 실행 |
| 배포 | Docker (HTTP only) | 리버스 프록시/HTTPS는 사용자 관리 |
| 테스트 | pytest | 분석 로직 단위 테스트 |

## MCP 서버

| 도구 | 기능 |
|------|------|
| `get_scores` | 현재 복합 점수, Z-Score 전체 조회 |
| `get_signals` | 현재 비율 조정 신호 + 해석 |
| `get_history` | 특정 기간/자산의 가격, 지표 이력 조회 |
| `add_comment` | 특정 날짜에 분석 코멘트 기록 |
| `get_report` | 리포트 조회 |

## DuckDB 테이블

| 테이블 | 용도 |
|--------|------|
| prices | 자산별 일간/월간 가격 |
| economic_indicators | CAPE, GSR, 금리, CPI 등 |
| yoy_returns | 연간 변동률(%) |
| zscores | 계산된 Z-Score |
| composite_scores | 복합 점수 + 신호 |
| comments | 분석 코멘트 |
| data_sync_log | 데이터 동기화 상태 |

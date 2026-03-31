# Portfolio Advisor

역사적 데이터 기반 투자 포트폴리오 비율 조정 어드바이저.

실물 자산(금/은)과 ETF(S&P500/나스닥100) 간 최적 비율을 다중 시간축 Z-Score 모델로 분석하는 개인용 시스템입니다.

## 개요

- 매일 자동으로 금, 은, S&P500, 나스닥100 가격 및 경제 지표를 수집합니다.
- 각 자산의 역사적 평균 대비 현재 위치를 Z-Score로 산출합니다.
- 실물 자산 vs ETF 그룹 간 비율, 그리고 각 그룹 내부 비율을 함께 제시합니다.
- 웹 대시보드에서 PC/모바일로 언제든 확인할 수 있습니다.
- Claude MCP 연동을 통해 AI 기반 추가 분석을 요청할 수 있습니다.

## 사용 방법

### 웹 대시보드

Docker로 서버에 배포하면, 매일 새벽 자동으로 데이터 수집과 분석이 실행됩니다. 별도 조작 없이 브라우저로 접속하여 현재 상태를 확인합니다.

대시보드 구성:
- 비율 추천 요약 (예: "균형 배분 - 실물 50% / ETF 50%")
- 자산별 가격 차트 (금, 은, S&P500, 나스닥100)
- Z-Score 히트맵 (자산별 저평가/고평가 현황)
- 금/은 비율 차트
- 복합 점수 추이
- 분석 근거 상세

### MCP를 통한 AI 분석

대시보드의 자동 분석 외에 추가적인 맥락 분석이 필요할 때, Claude에 MCP를 연동하여 시스템 데이터를 기반으로 한 분석을 요청할 수 있습니다.

Claude가 MCP를 통해 현재 점수, 신호, 가격 이력 등을 직접 조회한 뒤 종합적인 코멘트를 제공합니다.

## 설치

### 사전 준비

| 항목 | 설명 |
|------|------|
| Docker, Docker Compose | 컨테이너 실행 환경 |
| FRED API 키 | 무료 발급: https://fred.stlouisfed.org (가입 후 API Keys 메뉴) |

### 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고, FRED API 키를 입력합니다.

```bash
cp .env.example .env
```

```
FRED_API_KEY=발급받은_키
```

### 실행

```bash
docker compose up -d
```

최초 실행 시 자동으로 데이터를 수집하고 DB를 생성합니다.
이후 매일 새벽 3시에 cron이 자동으로 데이터를 갱신합니다.
은 100년 가격 데이터(CSV)는 프로젝트에 포함되어 있어 별도 다운로드가 필요 없습니다.

### 접속

Docker 컨테이너는 내부적으로 대시보드(8501)와 MCP 서버(8001) 두 개의 포트를 사용합니다.

**도메인을 연결한 경우 (운영 환경):**

리버스 프록시에서 경로 기반으로 라우팅하면 하나의 도메인으로 접속합니다.

| 서비스 | URL 예시 |
|--------|---------|
| 대시보드 | `https://portfolio.example.com` |
| MCP 서버 | `https://portfolio.example.com/mcp` |

HAProxy/Nginx 설정 예시는 [docs/deployment.md](docs/deployment.md#리버스-프록시-설정-haproxy-예시) 참조.

**도메인 없이 로컬에서 테스트하는 경우:**

| 서비스 | URL |
|--------|-----|
| 대시보드 | `http://localhost:8501` |
| MCP 서버 | `http://localhost:8001/mcp` |

## MCP 연동

Docker 실행 시 MCP 서버가 대시보드와 함께 자동으로 구동됩니다.
Claude Code 또는 Claude Desktop의 MCP 설정에 아래를 추가하면, Claude가 시스템 데이터를 직접 조회하여 분석할 수 있습니다.

**도메인을 연결한 경우:**
```json
{
  "mcpServers": {
    "portfolio-advisor": {
      "url": "https://portfolio.example.com/mcp"
    }
  }
}
```

**로컬 테스트:**
```json
{
  "mcpServers": {
    "portfolio-advisor": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

### MCP 도구

| 도구 | 기능 |
|------|------|
| `get_scores` | 현재 복합 점수 및 Z-Score 전체 조회 |
| `get_signals` | 현재 비율 조정 신호 및 해석 |
| `get_history` | 특정 자산의 가격 이력 조회 |
| `add_comment` | 분석 코멘트 기록 |
| `get_report` | 리포트 조회 |

## 로컬 개발

Docker 없이 직접 실행하는 경우:

```bash
uv sync                                                # 의존성 설치
uv run portfolio-update                                # 데이터 수집 및 분석
uv run streamlit run src/portfolio_advisor/ui/app.py   # 대시보드
uv run portfolio-mcp                                   # MCP 서버 (별도 터미널)
uv run pytest -v                                       # 테스트
```

## 문서

| 문서 | 내용 |
|------|------|
| [docs/overview.md](docs/overview.md) | 프로젝트 개요, 핵심 원칙, 2단계 비율 구조 |
| [docs/analysis-model.md](docs/analysis-model.md) | Z-Score 모델 수식, 복합 점수, 신호 생성 로직 |
| [docs/data-sources.md](docs/data-sources.md) | 데이터 소스, API, 출처 |
| [docs/tech-stack.md](docs/tech-stack.md) | 기술 스택, DB 스키마, MCP 도구 |
| [docs/deployment.md](docs/deployment.md) | Docker 배포 상세, config 설정 |

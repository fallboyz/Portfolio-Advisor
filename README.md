# Portfolio Advisor

역사적 데이터 기반 투자 포트폴리오 비율 조정 어드바이저.

실물 자산(금/은)과 ETF(S&P500/나스닥100) 간 최적 비율을 검증된 밸류에이션 지표 기반으로 분석하는 개인용 시스템입니다.

## 개요

- 매일 자동으로 금, 은, S&P500, 나스닥100 가격 및 경제 지표를 수집합니다.
- 검증된 밸류에이션 지표(CAPE, Buffett Indicator, 실질금리 등)로 각 자산의 저평가/고평가를 판단합니다.
- 실물 자산 vs ETF 그룹 간 비율, 그리고 각 그룹 내부 비율을 함께 제시합니다.
- 웹 대시보드에서 PC/모바일로 언제든 확인할 수 있습니다.
- MCP 연동을 통해 AI 기반 추가 분석(뉴스 동향 + 종합 판단)을 요청할 수 있습니다.

## 사용 방법

### 웹 대시보드

Docker로 서버에 배포하면, 매일 새벽 자동으로 데이터 수집과 분석이 실행됩니다. 별도 조작 없이 브라우저로 접속하여 현재 상태를 확인합니다.

대시보드 구성:
- 비율 추천 요약 (예: "실물 자산 비중 확대 - 실물 60% / ETF 40%")
- 분석 요약 (데이터 분석 / 시장 동향 / 종합 판단)
- 자산별 가격 차트 (금, 은, S&P500, 나스닥100)
- 금/은 비율 차트
- 밸류에이션 지표 차트 (실질금리, M2/금, Buffett Indicator, Yield Curve)
- Z-Score 히트맵 (자산별 저평가/고평가 현황)
- 복합 점수 추이
- 날짜별 분석 조회

### MCP를 통한 AI 분석

MCP(Model Context Protocol)는 개방형 표준 프로토콜로, Claude뿐 아니라 MCP를 지원하는 모든 AI 에이전트에서 사용할 수 있습니다. 서버 URL만 연동하면 소스코드나 개발환경 없이 어디서든 분석이 가능합니다.

시스템의 자동 분석은 숫자 계산(저평가/고평가 판단)까지만 수행합니다. MCP를 통해 AI가 데이터를 직접 조회하고, Finnhub 뉴스 API로 자산별 최근 동향을 참조하여 종합적인 판단 코멘트를 제공합니다.

분석 결과는 3섹션(데이터 분석 / 시장 동향 / 종합 판단)으로 구조화되어 대시보드에 표시됩니다.

## 분석 방법론

검증된 밸류에이션 지표를 기반으로 각 자산의 저평가/고평가를 판단하고, 이를 종합해서 실물 자산 vs ETF 비율을 결정합니다.

**귀금속 (금/은) 판단 지표:**
- 10년 실질금리 - 금리와 금 가격의 역상관 관계
- M2/금 비율 - 통화량 대비 금의 상대가치
- 금/은 비율(GSR) - 금과 은의 상대가치

**주식 (S&P500/나스닥) 판단 지표:**
- CAPE (Shiller P/E) - 경기조정 주가수익비율
- Buffett Indicator - 시가총액/GDP 비율
- Yield Curve - 장단기 금리차 (경기 방향 신호)

각 지표를 Z-Score로 변환하여 역사 평균 대비 현재 위치를 정량화하고, 자산별 가중 합산으로 복합 점수를 산출합니다. 실물 자산 점수와 ETF 점수의 차이(R 점수)에 따라 비율을 조정합니다.

**자동 분석 vs AI 분석:**
- 자동 분석 (매일 새벽): 위 지표 기반 숫자 계산만 수행. 비율과 점수를 산출
- AI 분석 (MCP): 숫자 데이터 + Finnhub 뉴스 API를 참조하여 시장 동향 해석과 종합 판단을 추가

상세 공식, 지표 선정 근거, 코멘트 작성 규칙은 [docs/analysis-model.md](docs/analysis-model.md)를 참조하세요.

## 설치

### 사전 준비

| 항목 | 설명 |
|------|------|
| Docker, Docker Compose | 컨테이너 실행 환경 |
| FRED API 키 | 무료 발급: https://fred.stlouisfed.org (가입 후 API Keys 메뉴) |
| Finnhub API 키 | 무료 발급: https://finnhub.io (가입 후 Dashboard에서 API Key 확인) |

### 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고, API 키를 입력합니다.

```bash
cp .env.example .env
```

```
FRED_API_KEY=발급받은_키
FINNHUB_API_KEY=발급받은_키
```

### 실행

```bash
docker compose up -d
```

최초 실행 시 자동으로 데이터를 수집하고 DB를 생성합니다.
이후 매일 새벽 3시에 내장 스케줄러가 자동으로 데이터를 갱신합니다.

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
MCP를 지원하는 AI 클라이언트(Claude Code, Claude Desktop 등)의 설정에 아래를 추가하면, AI가 시스템 데이터를 직접 조회하여 분석할 수 있습니다.

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
| `add_comment` | 분석 코멘트 기록 (현재 시각 자동 입력) |
| `delete_comment` | 잘못 저장된 코멘트 삭제 |
| `get_news` | 자산별 최근 뉴스 조회 (Finnhub) |
| `get_report` | 리포트 조회 |

## 로컬 개발

Docker 없이 직접 실행하는 경우:

```bash
uv sync                                                # 의존성 설치
uv run portfolio-update                                # 데이터 수집 및 분석
uv run portfolio-web                                   # 대시보드 (http://localhost:8501)
uv run portfolio-mcp                                   # MCP 서버 (별도 터미널)
uv run pytest -v                                       # 테스트
```

## 문서

| 문서 | 내용 |
|------|------|
| [docs/overview.md](docs/overview.md) | 프로젝트 개요, 핵심 원칙, 2단계 비율 구조 |
| [docs/analysis-model.md](docs/analysis-model.md) | 분석 모델, 지표 선정 근거, 가중치, 복합 점수 공식 |
| [docs/data-sources.md](docs/data-sources.md) | 데이터 소스, API, 출처 |
| [docs/tech-stack.md](docs/tech-stack.md) | 기술 스택, DB 스키마, MCP 도구 |
| [docs/deployment.md](docs/deployment.md) | Docker 배포 상세, config 설정 |

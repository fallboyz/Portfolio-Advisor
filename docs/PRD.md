# Portfolio Advisor - PRD

이 문서는 초기 기획 단계의 원본 명세서입니다.
상세 문서는 `docs/` 디렉토리에 분리되어 있습니다.

| 문서 | 내용 |
|------|------|
| [docs/overview.md](docs/overview.md) | 프로젝트 개요, 핵심 원칙, 2단계 비율 구조 |
| [docs/analysis-model.md](docs/analysis-model.md) | Z-Score 모델 수식, 복합 점수, 신호 생성 |
| [docs/data-sources.md](docs/data-sources.md) | 데이터 소스, API, 출처 |
| [docs/tech-stack.md](docs/tech-stack.md) | 기술 스택, DB 스키마, MCP 도구 |
| [docs/deployment.md](docs/deployment.md) | Docker 배포, config 설정, MCP 연결 |

## 참고 문헌

- **Meb Faber, "A Quantitative Approach to Tactical Asset Allocation"** - 10개월 SMA 기반 TAA 모델
- **Robert Shiller, CAPE Ratio** - S&P500 밸류에이션 평가 (1871년~)
- **Gold/Silver Ratio 80/50 Rule** - 80:1 이상이면 은 매수, 50:1 이하이면 금 매수
- **Vanguard (2024), "Time-varying Asset Allocation"** - Strategic과 Tactical 사이의 중간 접근법

## 데이터 스냅샷 (2026년 3월 30일 기준)

| 항목 | 값 |
|------|-----|
| 은(Silver) 국제 Spot | ~$68.5~$70/oz |
| 은 2026년 고점 | $121.67 (1~2월) |
| 은 고점 대비 하락률 | ~-42~43% |
| Gold/Silver Ratio | ~63~65:1 |
| S&P500 지수 | 6,368.85 |
| Shiller CAPE Ratio | ~36~39 (역사적 평균 ~16) |
| S&P500 2026년 고점 대비 | ~-9% |

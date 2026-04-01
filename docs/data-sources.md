# 데이터 소스

## 은(Silver) 데이터

### 가격 데이터 (USD/oz 기준)

| 데이터 | 구간 | 출처 |
|--------|------|------|
| 명목 가격 (100년+) | 1915~현재 | Macrotrends CSV (프로젝트에 포함) |
| 일간 가격 | ~2000~현재 | yfinance (SI=F) |

### Gold/Silver Ratio

| 데이터 | 구간 | 출처 |
|--------|------|------|
| 일간 비율 | ~2000~현재 | yfinance 금/은 가격에서 계산 (GC=F / SI=F) |

참고 경험칙:
- 80:1 이상: 은 상대적 저평가
- 50:1 이하: 은 상대적 고평가
- 장기 평균: 약 60~70:1

## 금(Gold) 데이터

| 데이터 | 구간 | 출처 |
|--------|------|------|
| 일간 가격 | ~2000~현재 | yfinance (GC=F) |

## ETF 데이터

### S&P500

| 데이터 | 구간 | 출처 |
|--------|------|------|
| 월간 가격 | 1871~현재 | Shiller Excel (자동 다운로드) |
| 일간 가격 | ~1970~현재 | yfinance (^GSPC) |
| CAPE Ratio | 1871~현재 | Shiller Excel |

CAPE 참고 수치:
- 역사적 평균: ~16
- 중간값: ~16
- 2026년 3월: ~36~39 (역사적 고평가 구간)

### 나스닥100

| 데이터 | 구간 | 출처 |
|--------|------|------|
| 일간 가격 | 1985~현재 | yfinance (^NDX) |

## 경제 지표

| 데이터 | 출처 | API | 용도 |
|--------|------|-----|------|
| 미국 기준금리 (Fed Funds Rate) | FRED | FEDFUNDS | 참조 |
| 미국 CPI (소비자물가지수) | FRED | CPIAUCSL | 참조 |
| 10년 실질금리 | FRED | REAINTRATREARAT10Y | 금/은 밸류에이션 (역상관) |
| M2 통화량 | FRED | M2SL | M2/금 비율 계산 |
| GDP | FRED | GDP | Buffett Indicator 계산 |
| 10년 국채 금리 | FRED | DGS10 | Yield Curve 계산 |
| 3개월 국채 금리 | FRED | DGS3MO | Yield Curve 계산 |
| 달러 인덱스 (DXY) | yfinance | DX-Y.NYB | 참조 |
| VIX (변동성 지수) | yfinance | ^VIX | 참조 |

## 파생 지표 (시스템 자동 계산)

| 지표 | 계산 방법 | 의미 |
|------|---------|------|
| GSR (금/은 비율) | 금 가격 / 은 가격 | 80 이상이면 은 저평가 |
| M2/금 비율 | M2 통화량 / 금 가격 | 높을수록 금이 통화량 대비 저평가 |
| Buffett Indicator | S&P500 / GDP | 높을수록 주식 과평가 (120% 이상 경고) |
| Yield Curve | 10년 금리 - 3개월 금리 | 음수(역전) = 경기 둔화 신호 |

## 뉴스 데이터 (MCP 분석용)

| 데이터 | 출처 | API | 용도 |
|--------|------|-----|------|
| 시장 뉴스 | Finnhub | finnhub.io/api/v1/news | AI 분석 시 시장 동향 참조 |

MCP를 통한 AI 분석 시에만 사용. 자동 분석(스케줄러)에서는 사용하지 않음.
자산별 키워드 필터링으로 관련 뉴스만 추출 (gold, silver, equity, macro).

## 데이터 출처 URL

| 출처 | URL |
|------|-----|
| Macrotrends | macrotrends.net |
| Shiller Data | shillerdata.com |
| FRED | fred.stlouisfed.org |
| Yahoo Finance | finance.yahoo.com |
| Finnhub | finnhub.io |

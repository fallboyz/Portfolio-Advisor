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

| 데이터 | 출처 | API |
|--------|------|-----|
| 미국 기준금리 (Fed Funds Rate) | FRED | FEDFUNDS |
| 미국 CPI (소비자물가지수) | FRED | CPIAUCSL |
| 달러 인덱스 (DXY) | yfinance | DX-Y.NYB |
| VIX (변동성 지수) | yfinance | ^VIX |

## 데이터 출처 URL

| 출처 | URL |
|------|-----|
| Macrotrends | macrotrends.net |
| Shiller Data | shillerdata.com |
| FRED | fred.stlouisfed.org |
| Yahoo Finance | finance.yahoo.com |

# 분석 모델: 다중 시간축 Z-Score 합성

## Z-Score 개요

Z-Score = "현재 값이 평균에서 표준편차 몇 개만큼 떨어져 있는지"
- +2: 평균보다 표준편차 2개 위 (과열)
- -2: 평균보다 표준편차 2개 아래 (저평가)
- 0: 평균 수준

## Step 1: 연간 변동률 Z-Score (시간축별)

```
Z_return_Ny = (R_current - mean_Ny) / stdev_Ny
```

- R_current: 최근 1년간 변동률(%)
- mean_Ny: N년 구간 연간 변동률 평균
- stdev_Ny: N년 구간 연간 변동률 표준편차

시간축: 50년, 10년, 5년

## Step 2: 가격 위치 Z-Score

```
Z_price = (P_current - MA_N) / stdev_price_N
```

은/금: 10년 이동평균 대비 현재 위치

## Step 3: CAPE Z-Score (ETF 전용)

```
Z_cape = (CAPE_current - CAPE_mean) / CAPE_stdev
```

S&P500의 Shiller CAPE Ratio를 전체 역사(1871~) 대비 평가.

## Step 4: Gold/Silver Ratio Z-Score

```
Z_gsr = (GSR_current - GSR_mean_N) / GSR_stdev_N
```

- Z_gsr 양수: 비율 높음 → 은 저평가 → 은 비중 올릴 신호
- Z_gsr 음수: 비율 낮음 → 은 고평가 → 은 비중 줄일 신호

## Step 5: 복합 점수 산출

각 자산별 Z-Score에 가중치를 곱해서 합산.

**은 복합 점수:**
```
S_silver = w1*Z_return_50y + w2*Z_return_10y + w3*Z_return_5y + w4*Z_price + w5*Z_gsr
```

**금 복합 점수:**
```
S_gold = w1*Z_return_50y + w2*Z_return_10y + w3*Z_return_5y + w4*Z_price
```

**S&P500 복합 점수:**
```
S_sp500 = w1*Z_return_50y + w2*Z_return_10y + w3*Z_return_5y + w4*Z_cape
```

**나스닥100 복합 점수:**
```
S_ndx = w2*Z_return_10y + w3*Z_return_5y
```
(1985년 이후 데이터만 있어서 50년 Z-Score 불가)

> 참고: 일부 Z-Score가 데이터 부족으로 계산 불가한 경우, 사용 가능한 항목만으로 자동 renormalization됩니다. 예를 들어 금은 GSR(w5)이 없으므로 w1~w4로만 계산하며, 합이 1.0이 되도록 자동 보정됩니다.

**가중치 (config.toml에서 조정 가능):**

| 가중치 | 설명 | 기본값 |
|--------|------|--------|
| w1 (50년) | 장기 평균 대비 | 0.20 |
| w2 (10년) | 중기 평균 대비 | 0.25 |
| w3 (5년) | 단기 평균 대비 | 0.25 |
| w4 (가격/CAPE) | 밸류에이션 | 0.20 |
| w5 (GSR, 은만) | 상대 가치 | 0.10 |

## Step 6: 2단계 비율 조정 신호

### Level 1: 실물 자산 vs ETF

**그룹 점수:**
```
S_precious = (S_gold + S_silver) / 2
S_etf = S_sp500 * 0.7 + S_ndx * 0.3
R_group = S_precious - S_etf
```

| R_group 구간 | 신호 | 실물 자산 비중 |
|-------------|------|-------------|
| R < -2.0 | 실물 대폭 확대 | 75% |
| -2.0 ~ -1.0 | 실물 확대 | 60% |
| -1.0 ~ +1.0 | 균형 | 50% |
| +1.0 ~ +2.0 | ETF 확대 | 35% |
| R > +2.0 | ETF 대폭 확대 | 20% |

### Level 2a: 금 vs 은

Gold/Silver Ratio Z-Score 기반:

| GSR Z-Score | 금:은 비율 |
|------------|-----------|
| Z > 1.0 | 30:70 (은 크게 저평가) |
| 0 ~ 1.0 | 40:60 |
| -1.0 ~ 0 | 50:50 |
| Z < -1.0 | 60:40 (금이 더 매력적) |

### Level 2b: S&P 500 vs 나스닥 100

상대 복합 점수 차이 기반:

| S_sp500 - S_ndx | S&P:나스닥 비율 |
|-----------------|---------------|
| 차이 > 0.5 | 40:60 (나스닥 저평가) |
| -0.5 ~ 0.5 | 50:50 |
| 차이 < -0.5 | 60:40 (S&P 저평가) |

## Step 7: 폭락/폭등 보정 (Drawdown/Rally Overlay)

| 조건 | 보정 |
|------|------|
| 은 고점 대비 -40% 이하 | 실물 점수에 -0.5 (더 매력적) |
| ETF 고점 대비 -30% 이하 | ETF 점수에 -0.5 (더 매력적) |
| 은 6개월 +100% 이상 | 실물 점수에 +0.5 (과열 경고) |

## Z-Score 부호 방향 해석

- 점수가 높은(양수) 자산 = 최근 많이 오름 = 과열 가능성
- 점수가 낮은(음수) 자산 = 최근 많이 빠짐 = 저평가 가능성
- R이 음수: 실물이 저평가, ETF가 고평가 → 실물 비중 올림
- R이 양수: 실물이 고평가, ETF가 저평가 → ETF 비중 올림

from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from portfolio_advisor.analysis.composite import (
    compute_etf_composite,
    compute_gold_composite,
    compute_group_scores,
    compute_ndx_composite,
    compute_silver_composite,
)
from portfolio_advisor.analysis.signal import (
    apply_drawdown_overlay,
    compute_drawdown,
    compute_rally,
    generate_group_signal,
)
from portfolio_advisor.analysis.zscore import compute_all_zscores
from portfolio_advisor.data.store import Store

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    portfolio_values: pd.DataFrame  # date, value
    trades: pd.DataFrame  # date, signal_label, precious_pct, etf_pct, precious_return, etf_return
    metrics: dict = field(default_factory=dict)


class BacktestEngine:
    def __init__(self, store: Store, config: dict):
        self.store = store
        self.config = config
        self.thresholds = config.get("signals", {})
        self.overlay_config = config.get("drawdown_overlay", {})

    def run(
        self,
        start_year: int = 1975,
        end_year: int = 2025,
        rebalance_freq: str = "annual",
        initial_capital: float = 10000,
    ) -> BacktestResult:
        """Walk-forward backtest simulation."""
        rebalance_dates = self._get_rebalance_dates(start_year, end_year, rebalance_freq)

        if len(rebalance_dates) < 2:
            return BacktestResult(
                portfolio_values=pd.DataFrame(columns=["date", "value"]),
                trades=pd.DataFrame(),
                metrics={"error": "Not enough rebalance dates"},
            )

        portfolio_value = initial_capital
        values = []
        trades = []

        for i in range(len(rebalance_dates) - 1):
            current_date = rebalance_dates[i]
            next_date = rebalance_dates[i + 1]

            allocation = self._compute_allocation(current_date)
            precious_pct = allocation["precious_pct"] / 100.0
            etf_pct = 1.0 - precious_pct

            precious_return = self._get_precious_return(current_date, next_date)
            etf_return = self._get_etf_return(current_date, next_date)

            period_return = precious_pct * precious_return + etf_pct * etf_return
            portfolio_value *= (1 + period_return)

            values.append({"date": next_date, "value": round(portfolio_value, 2)})
            trades.append({
                "date": current_date,
                "signal_label": allocation["label"],
                "precious_pct": allocation["precious_pct"],
                "etf_pct": 100 - allocation["precious_pct"],
                "precious_return": round(precious_return * 100, 2),
                "etf_return": round(etf_return * 100, 2),
            })

        values_df = pd.DataFrame(values)
        trades_df = pd.DataFrame(trades)
        metrics = self._compute_metrics(values_df, initial_capital, len(trades))

        return BacktestResult(
            portfolio_values=values_df,
            trades=trades_df,
            metrics=metrics,
        )

    def compare_with_fixed(
        self,
        fixed_ratios: list[tuple[int, int]],
        **kwargs,
    ) -> pd.DataFrame:
        """Run model backtest + fixed-ratio benchmarks.

        Args:
            fixed_ratios: List of (precious_pct, etf_pct) tuples, e.g. [(50,50), (30,70)]
        """
        model_result = self.run(**kwargs)
        if model_result.portfolio_values.empty:
            return pd.DataFrame()

        comparison = model_result.portfolio_values.rename(columns={"value": "model"})

        start_year = kwargs.get("start_year", 1975)
        end_year = kwargs.get("end_year", 2025)
        rebalance_freq = kwargs.get("rebalance_freq", "annual")
        initial_capital = kwargs.get("initial_capital", 10000)

        rebalance_dates = self._get_rebalance_dates(start_year, end_year, rebalance_freq)

        for p_pct, e_pct in fixed_ratios:
            portfolio_value = initial_capital
            values = []

            for i in range(len(rebalance_dates) - 1):
                current_date = rebalance_dates[i]
                next_date = rebalance_dates[i + 1]

                precious_return = self._get_precious_return(current_date, next_date)
                etf_return = self._get_etf_return(current_date, next_date)

                period_return = (p_pct / 100) * precious_return + (e_pct / 100) * etf_return
                portfolio_value *= (1 + period_return)
                values.append({"date": next_date, "value": round(portfolio_value, 2)})

            label = f"fixed_{p_pct}_{e_pct}"
            fixed_df = pd.DataFrame(values)
            if not fixed_df.empty:
                comparison = comparison.merge(
                    fixed_df.rename(columns={"value": label}),
                    on="date",
                    how="left",
                )

        return comparison

    def _get_rebalance_dates(
        self, start_year: int, end_year: int, freq: str
    ) -> list[date]:
        dates = []
        for year in range(start_year, end_year + 1):
            if freq == "annual":
                dates.append(date(year, 12, 31))
            elif freq == "semi_annual":
                dates.append(date(year, 6, 30))
                dates.append(date(year, 12, 31))
            elif freq == "monthly":
                for month in range(1, 13):
                    last_day = calendar.monthrange(year, month)[1]
                    dates.append(date(year, month, last_day))
        return sorted(dates)

    def _compute_allocation(self, as_of_date: date) -> dict:
        """Compute allocation signal using only data up to as_of_date."""
        zscores_df = compute_all_zscores(self.store, as_of_date=as_of_date)

        if zscores_df.empty:
            return {"label": "neutral", "precious_pct": 50}

        asset_zscores: dict[str, dict] = {}
        for _, row in zscores_df.iterrows():
            symbol = row["symbol"]
            if symbol not in asset_zscores:
                asset_zscores[symbol] = {}
            asset_zscores[symbol][row["metric"]] = row["zscore"]

        s_gold = compute_gold_composite(asset_zscores.get("GOLD", {}), self.config)
        s_silver = compute_silver_composite(asset_zscores.get("SILVER", {}), self.config)
        s_sp500 = compute_etf_composite(asset_zscores.get("SP500", {}), self.config)
        s_ndx = compute_ndx_composite(asset_zscores.get("NDX", {}), self.config)

        s_precious, s_etf = compute_group_scores(s_gold, s_silver, s_sp500, s_ndx)

        silver_prices = self.store.get_prices("SILVER", end=as_of_date)
        sp500_prices = self.store.get_prices("SP500", end=as_of_date)
        dd_silver = compute_drawdown(silver_prices["close"]) if not silver_prices.empty else 0.0
        dd_etf = compute_drawdown(sp500_prices["close"]) if not sp500_prices.empty else 0.0
        rally_silver = compute_rally(silver_prices["close"]) if not silver_prices.empty else 0.0

        s_precious, s_etf, _ = apply_drawdown_overlay(
            s_precious, s_etf, dd_silver, dd_etf, rally_silver, self.overlay_config
        )

        r_group = s_precious - s_etf
        return generate_group_signal(r_group, self.thresholds)

    def _get_precious_return(self, start: date, end: date) -> float:
        """실물 자산 수익률. 데이터 있는 자산만 가중 평균."""
        gold_ret = self._get_period_return("GOLD", start, end)
        silver_ret = self._get_period_return("SILVER", start, end)
        gold_has_data = len(self.store.get_prices("GOLD", start=start, end=end)) >= 2
        silver_has_data = len(self.store.get_prices("SILVER", start=start, end=end)) >= 2

        if gold_has_data and silver_has_data:
            return gold_ret * 0.5 + silver_ret * 0.5
        if silver_has_data:
            return silver_ret
        if gold_has_data:
            return gold_ret
        return 0.0

    def _get_etf_return(self, start: date, end: date) -> float:
        """ETF 수익률. 데이터 있는 자산만 가중 평균."""
        sp500_ret = self._get_period_return("SP500", start, end)
        ndx_ret = self._get_period_return("NDX", start, end)
        sp500_has_data = len(self.store.get_prices("SP500", start=start, end=end)) >= 2
        ndx_has_data = len(self.store.get_prices("NDX", start=start, end=end)) >= 2

        if sp500_has_data and ndx_has_data:
            return sp500_ret * 0.7 + ndx_ret * 0.3
        if sp500_has_data:
            return sp500_ret
        if ndx_has_data:
            return ndx_ret
        return 0.0

    def _get_period_return(self, symbol: str, start: date, end: date) -> float:
        prices = self.store.get_prices(symbol, start=start, end=end)
        if len(prices) < 2:
            return 0.0
        start_price = float(prices.iloc[0]["close"])
        end_price = float(prices.iloc[-1]["close"])
        if start_price == 0:
            return 0.0
        return (end_price - start_price) / start_price

    def _compute_metrics(
        self, values_df: pd.DataFrame, initial_capital: float, num_trades: int
    ) -> dict:
        if values_df.empty:
            return {}

        final_value = float(values_df.iloc[-1]["value"])
        total_return = (final_value / initial_capital - 1) * 100

        first_date = pd.to_datetime(values_df.iloc[0]["date"])
        last_date = pd.to_datetime(values_df.iloc[-1]["date"])
        n_years = max((last_date - first_date).days / 365.25, 1)
        cagr = ((final_value / initial_capital) ** (1 / n_years) - 1) * 100

        values = values_df["value"].values
        peak = np.maximum.accumulate(values)
        drawdowns = (values - peak) / peak * 100
        max_dd = float(np.min(drawdowns))

        return {
            "initial_capital": initial_capital,
            "final_value": round(final_value, 2),
            "total_return_pct": round(total_return, 2),
            "cagr_pct": round(cagr, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "num_rebalances": num_trades,
        }

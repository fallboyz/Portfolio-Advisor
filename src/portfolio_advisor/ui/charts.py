from __future__ import annotations

import plotly.graph_objects as go
import pandas as pd

FONT_FAMILY = "Pretendard, sans-serif"


def score_gauge(value: float, min_val: float = -4, max_val: float = 4) -> go.Figure:
    """R 점수 게이지. 음수=실물 자산 유리, 양수=ETF 유리."""
    if value < -1:
        color = "#0d9488"
    elif value > 1:
        color = "#dc2626"
    else:
        color = "#6b7280"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"font": {"size": 40, "family": FONT_FAMILY}},
            gauge={
                "axis": {"range": [min_val, max_val], "tickfont": {"size": 11}},
                "bar": {"color": color, "thickness": 0.6},
                "steps": [
                    {"range": [min_val, -2], "color": "#d1fae5"},
                    {"range": [-2, -1], "color": "#ecfdf5"},
                    {"range": [-1, 1], "color": "#f3f4f6"},
                    {"range": [1, 2], "color": "#fef2f2"},
                    {"range": [2, max_val], "color": "#fee2e2"},
                ],
            },
        )
    )
    fig.add_annotation(
        x=0.13, y=-0.12, text="실물 자산 유리", showarrow=False,
        font={"size": 11, "color": "#0d9488", "family": "Pretendard"}, xref="paper", yref="paper",
    )
    fig.add_annotation(
        x=0.87, y=-0.12, text="ETF 유리", showarrow=False,
        font={"size": 11, "color": "#dc2626", "family": "Pretendard"}, xref="paper", yref="paper",
    )
    fig.update_layout(
        height=200,
        margin={"t": 15, "b": 35, "l": 25, "r": 25},
        paper_bgcolor="white",
    )
    return fig


ZSCORE_LABELS = {
    "return_50y": "50년 수익률",
    "return_10y": "10년 수익률",
    "return_5y": "5년 수익률",
    "price_position": "가격 위치",
    "cape": "CAPE",
    "gsr": "금은비",
}


def zscore_heatmap(zscores_df: pd.DataFrame) -> go.Figure:
    """Z-Score 히트맵."""
    if zscores_df.empty:
        return _empty_figure("Z-Score 데이터 없음")

    df = zscores_df.copy()
    df["metric_ko"] = df["metric"].map(ZSCORE_LABELS).fillna(df["metric"])

    pivot = df.pivot_table(index="metric_ko", columns="symbol", values="zscore")

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0, "#0d9488"], [0.5, "#f3f4f6"], [1, "#dc2626"]],
            zmid=0,
            text=pivot.values.round(2),
            texttemplate="%{text}",
            textfont={"size": 12},
            colorbar={"title": "Z", "thickness": 12},
        )
    )
    fig.update_layout(
        title={"text": "Z-Score 현황", "font": {"size": 14}},
        height=320,
        margin={"t": 50, "b": 30, "l": 110, "r": 20},
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"family": FONT_FAMILY},
    )
    return fig


def price_chart(prices_df: pd.DataFrame, title: str, years: int = 1) -> go.Figure:
    """가격 차트. years=0이면 전체 표시."""
    if prices_df.empty:
        return _empty_figure(f"데이터 없음: {title}")

    dates = pd.to_datetime(prices_df["date"])
    x_end = dates.max()

    if years > 0:
        x_start = x_end - pd.DateOffset(years=years)
        x_range = [x_start, x_end]
    else:
        x_range = None

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=prices_df["date"],
            y=prices_df["close"],
            mode="lines",
            name=title,
            line={"width": 1.5, "color": "#093687"},
        )
    )
    layout_args = {
        "yaxis_title": "가격 ($)",
        "height": 380,
        "margin": {"t": 15, "b": 30, "l": 55, "r": 15},
        "plot_bgcolor": "white",
        "paper_bgcolor": "white",
        "font": {"family": FONT_FAMILY},
        "modebar": {"orientation": "v"},
    }
    if x_range:
        layout_args["xaxis"] = {"range": x_range}

    fig.update_layout(**layout_args)
    fig.update_xaxes(gridcolor="#f0f0f0", zeroline=False)
    fig.update_yaxes(gridcolor="#f0f0f0", zeroline=False)
    return fig


def gsr_chart(gsr_df: pd.DataFrame) -> go.Figure:
    """금/은 비율 차트."""
    if gsr_df.empty:
        return _empty_figure("금/은 비율 데이터 없음")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=gsr_df["date"],
            y=gsr_df["value"],
            mode="lines",
            name="금/은 비율",
            line={"width": 1.5, "color": "#d97706"},
            fill="tozeroy",
            fillcolor="rgba(217, 119, 6, 0.05)",
        )
    )
    fig.add_hline(y=80, line_dash="dot", line_color="#0d9488", line_width=1,
                  annotation_text="80: 은 저평가", annotation_font_size=10)
    fig.add_hline(y=50, line_dash="dot", line_color="#dc2626", line_width=1,
                  annotation_text="50: 은 고평가", annotation_font_size=10)

    fig.update_layout(
        title={"text": "금/은 비율", "font": {"size": 14}},
        yaxis_title="비율",
        height=350,
        margin={"t": 50, "b": 30, "l": 55, "r": 15},
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"family": FONT_FAMILY},
    )
    fig.update_xaxes(gridcolor="#f0f0f0", zeroline=False)
    fig.update_yaxes(gridcolor="#f0f0f0", zeroline=False)
    return fig


def composite_history_chart(composite_df: pd.DataFrame) -> go.Figure:
    """복합 점수 이력."""
    if composite_df.empty:
        return _empty_figure("복합 점수 이력 없음")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(x=composite_df["calc_date"], y=composite_df["s_precious"],
                   mode="lines", name="실물 자산 점수", line={"color": "#d97706", "width": 1.5})
    )
    fig.add_trace(
        go.Scatter(x=composite_df["calc_date"], y=composite_df["s_etf"],
                   mode="lines", name="ETF 점수", line={"color": "blue", "width": 1.5})
    )
    fig.add_trace(
        go.Scatter(x=composite_df["calc_date"], y=composite_df["r_group"],
                   mode="lines", name="R 점수 (실물 자산-ETF)", line={"color": "black", "width": 2})
    )

    fig.add_hrect(y0=-4, y1=-2, fillcolor="green", opacity=0.05, line_width=0)
    fig.add_hrect(y0=-2, y1=-1, fillcolor="green", opacity=0.03, line_width=0)
    fig.add_hrect(y0=1, y1=2, fillcolor="red", opacity=0.03, line_width=0)
    fig.add_hrect(y0=2, y1=4, fillcolor="red", opacity=0.05, line_width=0)

    fig.update_layout(
        title={"text": "복합 점수 추이", "font": {"size": 14}},
        yaxis_title="점수",
        height=400,
        margin={"t": 50, "b": 30, "l": 55, "r": 15},
        plot_bgcolor="white",
        paper_bgcolor="white",
        font={"family": FONT_FAMILY},
    )
    fig.update_xaxes(gridcolor="#f0f0f0", zeroline=False)
    fig.update_yaxes(gridcolor="#f0f0f0", zeroline=False)
    return fig


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font_size=16)
    fig.update_layout(height=300)
    return fig

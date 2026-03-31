from __future__ import annotations

from datetime import datetime

import streamlit as st

from portfolio_advisor.analysis.signal import SIGNAL_KO
from portfolio_advisor.config import load_config
from portfolio_advisor.data.store import Store
from portfolio_advisor.ui.charts import (
    composite_history_chart,
    gsr_chart,
    price_chart,
    score_gauge,
    zscore_heatmap,
)

_CSS = """
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
    .block-container { padding-top: 3rem; max-width: 1400px; }
    html, body, [class*="css"] { font-family: 'Pretendard', -apple-system, sans-serif; }
    .signal-card {
        background: #093687; border-radius: 12px;
        padding: 1.8rem 2rem; color: white; margin-bottom: 1.2rem;
    }
    .signal-card h1 {
        font-size: 1.8rem; margin: 0 0 0.4rem 0;
        font-weight: 700; letter-spacing: -0.5px;
    }
    .signal-card .desc { font-size: 0.95rem; opacity: 0.85; margin-bottom: 1rem; line-height: 1.5; }
    .signal-card .allocation {
        display: inline-flex; gap: 0.6rem; align-items: center;
        background: rgba(255,255,255,0.12); border-radius: 8px;
        padding: 0.5rem 1rem; font-size: 1.05rem; font-weight: 600;
    }
    .signal-card .allocation .precious { color: #ddd; }
    .signal-card .allocation .etf { color: #7eb8ff; }
    .signal-card .allocation .divider { opacity: 0.4; }
    .metric-row { display: flex; gap: 0.8rem; margin: 0.8rem 0 1.2rem 0; }
    .metric-box {
        flex: 1; background: #fff; border: 1px solid #e8e8e8;
        border-radius: 10px; padding: 1.2rem 1rem; text-align: center;
    }
    .metric-box .label { font-size: 0.8rem; color: #888; margin-bottom: 0.3rem; font-weight: 500; }
    .metric-box .value { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.5px; }
    .metric-box .hint { font-size: 0.7rem; color: #aaa; margin-top: 0.2rem; }
    .section-header {
        font-size: 1.15rem; font-weight: 700; color: #222;
        margin: 2rem 0 0.3rem 0; padding: 0.5rem 0;
        display: flex; align-items: center; gap: 0.4rem; letter-spacing: -0.3px;
    }
    .section-header::before {
        content: ''; width: 3px; height: 1.1rem;
        background: #093687; border-radius: 2px;
    }
    .guide-box {
        background: #f7f8fa; border-radius: 8px;
        padding: 0.8rem 1rem; margin: 0.3rem 0 1rem 0;
        font-size: 0.82rem; color: #666; line-height: 1.65; border: 1px solid #eee;
    }
    .guide-box b { color: #333; }
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.8rem; }
        .signal-card { padding: 1.3rem 1.2rem; }
        .signal-card h1 { font-size: 1.4rem; }
        .signal-card .desc { font-size: 0.85rem; }
        .signal-card .allocation { font-size: 0.9rem; padding: 0.4rem 0.8rem; }
        .metric-row { flex-direction: column; gap: 0.5rem; }
        .metric-box { padding: 0.9rem 0.8rem; }
        .metric-box .value { font-size: 1.3rem; }
        .section-header { font-size: 1.05rem; margin-top: 1.5rem; }
        .guide-box { font-size: 0.78rem; padding: 0.7rem 0.8rem; }
    }
    section[data-testid="stSidebar"] {
        background: #f7f8fa; border-right: 1px solid #e8e8e8;
        width: 200px !important; min-width: 200px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stText"] { font-size: 0.72rem !important; }
    section[data-testid="stSidebar"] h2 { font-size: 0.9rem !important; }
    section[data-testid="stSidebar"] .stCaption { font-size: 0.65rem !important; }

    /* Streamlit 기본 헤더/푸터 숨기기 (사이드바 토글은 유지) */
    footer { display: none; }
    .stDeployButton { display: none; }
</style>
"""

ZSCORE_LABELS = {
    "return_50y": "50년 수익률",
    "return_10y": "10년 수익률",
    "return_5y": "5년 수익률",
    "price_position": "가격 위치",
    "cape": "CAPE (주가수익비율)",
    "gsr": "금/은 비율",
}

WEIGHT_LABELS = {
    "w1_50y": "50년 수익률 가중치",
    "w2_10y": "10년 수익률 가중치",
    "w3_5y": "5년 수익률 가중치",
    "w4_valuation": "밸류에이션 (CAPE/가격위치) 가중치",
    "w5_gsr": "금/은 비율 가중치 (은에만 적용)",
}

PERIOD_OPTIONS = {"1년": 1, "5년": 5, "10년": 10, "전체": 0}


def _color_by_sign(value: float) -> str:
    return "#2E7D32" if value < 0 else "#C62828"


def _color_by_threshold(value: float) -> str:
    if value < -1:
        return "#2E7D32"
    if value > 1:
        return "#C62828"
    return "#616161"


def get_store() -> Store:
    config = load_config()
    return Store(config["data"]["db_path"])


def main():
    st.set_page_config(
        page_title="Portfolio Advisor",
        layout="wide",
        initial_sidebar_state="auto",
    )
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
<div style="border-bottom:2px solid #093687; padding-bottom:0.8rem; margin-bottom:1.2rem;">
    <div style="font-size:1.6rem; font-weight:800; color:#093687; letter-spacing:-0.5px;">
        Portfolio Advisor
    </div>
    <div style="font-size:0.85rem; color:#dc2626; margin-top:0.3rem; line-height:1.5;">
        실물 자산(금/은)과 ETF(S&amp;P500/나스닥100)의 역사적 데이터를 분석하여,
        현재 기준으로 어느 쪽에 투자 비중을 더 둘지 어드바이스하는 시스템입니다.
    </div>
</div>
""", unsafe_allow_html=True)

    store = get_store()
    config = load_config()
    latest = store.get_latest_composite()

    if latest is None:
        st.warning("분석 데이터가 없습니다. 먼저 업데이트를 실행해주세요:")
        st.code("uv run portfolio-update")
        return

    _render_signal_card(latest)
    _render_basis(latest)
    _render_metrics(latest)
    _render_comment(store)
    _render_price_charts(store)
    _render_gsr(store)
    _render_zscore(store)
    _render_composite_history(store)
    _render_details(store, config)
    _render_comments_section(store)
    _render_footer()
    _render_sidebar(store, latest)


def _render_signal_card(latest: dict):
    signal_info = SIGNAL_KO.get(latest["signal_label"], SIGNAL_KO["neutral"])
    precious_pct = latest.get("precious_pct", 50)
    etf_pct = 100 - precious_pct
    gold_pct = latest.get("gold_pct", 50)
    silver_pct = latest.get("silver_pct", 50)
    sp500_pct = latest.get("sp500_pct", 60)
    ndx_pct = latest.get("ndx_pct", 40)

    st.markdown(f"""
<div class="signal-card">
    <h1>{signal_info["label"]}</h1>
    <div class="desc">{signal_info["desc"]}</div>
    <div class="allocation">
        <span class="precious">실물 자산 {precious_pct}%</span>
        <span class="divider">(금 {gold_pct} : 은 {silver_pct})</span>
        <span class="divider">|</span>
        <span class="etf">ETF {etf_pct}%</span>
        <span class="divider">(S&P {sp500_pct} : 나스닥 {ndx_pct})</span>
    </div>
</div>""", unsafe_allow_html=True)


def _render_basis(latest: dict):
    r_group = latest.get("r_group", 0)
    with st.expander("분석 근거"):
        st.markdown(f"""
**그룹 상대 점수 (R) = {r_group:.2f}**

| R 점수 구간 | 의미 | 권장 실물 자산 비중 |
|------------|------|--------------|
| R < -2.0 | 실물 자산 크게 저평가 | **75%** |
| -2.0 ~ -1.0 | 실물 자산 다소 저평가 | **60%** |
| **-1.0 ~ +1.0** | **중립** | **50%** |
| +1.0 ~ +2.0 | ETF 다소 저평가 | **35%** |
| R > +2.0 | ETF 크게 저평가 | **20%** |

**Level 1 (실물 자산 vs ETF):** 실물 자산 점수({latest.get("s_precious", 0):.2f})와 ETF 점수({latest["s_etf"]:.2f})를 비교. R = 실물 자산 - ETF.

**Level 2a (금 vs 은):** 금/은 비율(GSR) Z-Score 기반. GSR이 높으면 은이 금 대비 저평가.

**Level 2b (S&P vs 나스닥):** 두 지수의 복합 점수 비교. 점수가 낮은 쪽이 저평가.
""")


def _render_metrics(latest: dict):
    r_val = latest.get("r_group", 0)
    st.markdown(f"""
<div class="metric-row">
    <div class="metric-box">
        <div class="label">그룹 R 점수</div>
        <div class="value" style="color:{_color_by_threshold(r_val)}">{r_val:.2f}</div>
        <div class="hint">음수 = 실물 자산 유리 / 양수 = ETF 유리</div>
    </div>
    <div class="metric-box">
        <div class="label">실물 자산 점수</div>
        <div class="value" style="color:{_color_by_sign(latest.get('s_precious', 0))}">{latest.get("s_precious", 0):.2f}</div>
        <div class="hint">금 {latest.get("s_gold", 0):.2f} / 은 {latest["s_silver"]:.2f}</div>
    </div>
    <div class="metric-box">
        <div class="label">ETF 점수</div>
        <div class="value" style="color:{_color_by_sign(latest['s_etf'])}">{latest["s_etf"]:.2f}</div>
        <div class="hint">S&P {latest.get("s_sp500", 0):.2f} / 나스닥 {latest.get("s_ndx", 0):.2f}</div>
    </div>
</div>""", unsafe_allow_html=True)

    st.plotly_chart(
        score_gauge(latest.get("r_group", 0)),
        width="stretch",
    )


def _render_comment(store: Store):
    comments = store.get_comments(limit=1)
    if not comments.empty:
        st.info(comments.iloc[0]["content"])


def _render_price_charts(store: Store):
    st.markdown('<div class="section-header">가격 현황</div>', unsafe_allow_html=True)
    st.markdown("""<div class="guide-box">
가격 추이. 기간 버튼으로 범위 변경. 마우스 올리면 해당 시점 가격 확인.
</div>""", unsafe_allow_html=True)

    period = st.radio(
        "기간", list(PERIOD_OPTIONS.keys()),
        horizontal=True, index=0, label_visibility="collapsed",
    )
    selected_years = PERIOD_OPTIONS[period]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**은 (Silver)**")
        st.plotly_chart(price_chart(store.get_prices("SILVER"), "은", selected_years), width="stretch")
    with col2:
        st.markdown("**금 (Gold)** *(참고)*")
        st.plotly_chart(price_chart(store.get_prices("GOLD"), "금", selected_years), width="stretch")

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**S&P 500**")
        st.plotly_chart(price_chart(store.get_prices("SP500"), "S&P 500", selected_years), width="stretch")
    with col4:
        st.markdown("**나스닥 100** *(참고)*")
        st.plotly_chart(price_chart(store.get_prices("NDX"), "나스닥 100", selected_years), width="stretch")


def _render_gsr(store: Store):
    st.markdown('<div class="section-header">금/은 비율</div>', unsafe_allow_html=True)
    st.markdown("""<div class="guide-box">
금 1온스 / 은 1온스 가격 비율. <b>80 이상</b>(녹색 점선) = 은이 금 대비 저평가.
<b>50 이하</b>(빨간 점선) = 은이 금 대비 고평가. 장기 평균 약 60~70.
</div>""", unsafe_allow_html=True)
    st.plotly_chart(gsr_chart(store.get_indicator("GSR")), width="stretch")


def _render_zscore(store: Store):
    st.markdown('<div class="section-header">Z-Score 분석</div>', unsafe_allow_html=True)
    st.markdown("""<div class="guide-box">
각 지표가 역사적 평균 대비 어디에 있는지 한눈에 보는 표.
<b>파란색</b> = 저평가. <b>빨간색</b> = 고평가.
<b>-2 이하</b>면 역사적으로 매우 낮은 수준, <b>+2 이상</b>이면 매우 높은 수준.
</div>""", unsafe_allow_html=True)
    st.plotly_chart(zscore_heatmap(store.get_latest_zscores()), width="stretch")


def _render_composite_history(store: Store):
    st.markdown('<div class="section-header">복합 점수 추이</div>', unsafe_allow_html=True)
    st.markdown("""<div class="guide-box">
<b>검은 굵은선 (R 점수)</b>이 핵심. 녹색 배경(R &lt; -1) = 실물 자산 유리, 빨간 배경(R &gt; +1) = ETF 유리.
</div>""", unsafe_allow_html=True)
    st.plotly_chart(composite_history_chart(store.get_composite_history()), width="stretch")


def _render_details(store: Store, config: dict):
    st.divider()
    zscores = store.get_latest_zscores()
    with st.expander("Z-Score 상세 수치"):
        if not zscores.empty:
            for symbol in zscores["symbol"].unique():
                symbol_zs = zscores[zscores["symbol"] == symbol]
                st.markdown(f"**{symbol}**")
                for _, row in symbol_zs.iterrows():
                    label = ZSCORE_LABELS.get(row["metric"], row["metric"])
                    mean_str = f"{row['mean_val']:.2f}" if row["mean_val"] is not None else "-"
                    stdev_str = f"{row['stdev_val']:.2f}" if row["stdev_val"] is not None else "-"
                    st.text(
                        f"  {label}: Z={row['zscore']:.2f}"
                        f" (평균={mean_str}, 표준편차={stdev_str}, 현재값={row['current_val']:.2f})"
                    )

    with st.expander("현재 적용 중인 가중치"):
        weights = config.get("weights", {})
        st.markdown("각 Z-Score에 아래 가중치를 곱해서 복합 점수를 만듭니다. `config.toml`에서 수정 가능.")
        for k, v in weights.items():
            st.text(f"  {WEIGHT_LABELS.get(k, k)}: {v}")


def _render_comments_section(store: Store):
    st.divider()
    with st.expander("코멘트 기록"):
        comment_text = st.text_area("코멘트 작성", height=80)
        if st.button("저장") and comment_text.strip():
            store.add_comment(datetime.now(), comment_text.strip(), author="user")
            st.success("저장됨.")
            st.rerun()

        all_comments = store.get_comments(limit=20)
        if not all_comments.empty:
            for _, row in all_comments.iterrows():
                st.markdown(f"**{str(row['date'])[:16]}** ({row['author']})")
                st.text(row["content"])
                st.divider()


def _render_footer():
    st.markdown("""
<div style="margin-top:3rem; padding:1.5rem 0; border-top:1px solid #e0e0e0; text-align:center;">
    <div style="font-size:0.75rem; color:#999;">
&copy; 2026 Portfolio Advisor. Built by Coulson.
    </div>
</div>
""", unsafe_allow_html=True)


def _render_sidebar(store: Store, latest: dict):
    with st.sidebar:
        st.header("데이터 상태")
        sync = store.get_sync_status()
        if not sync.empty:
            for _, row in sync.iterrows():
                status = "OK" if row["status"] == "ok" else "ERR"
                st.text(f"[{status}] {row['source']}")
        calc_date = str(latest["calc_date"])[:16]
        st.caption(f"마지막 분석: {calc_date}")


main()

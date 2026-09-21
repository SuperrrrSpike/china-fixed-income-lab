from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
from dateutil.relativedelta import relativedelta

from .bond import BondAnalytics, BondSpec
from .data import DataSourceError, fetch_china_yield_curve, sample_dataset
from .report import excel_bytes, generate_morning_brief
from .yield_curve import apply_curve_scenario, latest_curve, term_spread, to_long_curve


def _curve_chart(curve_long: pd.DataFrame):
    latest = latest_curve(curve_long)
    figure = px.line(
        latest,
        x="tenor_years",
        y="yield_pct",
        markers=True,
        labels={"tenor_years": "期限（年）", "yield_pct": "收益率（%）"},
        title=f"收益率曲线 {latest['date'].max():%Y-%m-%d}",
    )
    figure.update_layout(height=420, margin=dict(l=20, r=20, t=60, b=20))
    return figure


def run_dashboard() -> None:
    st.set_page_config(page_title="中国固定收益分析实验室", layout="wide")
    st.title("中国固定收益分析实验室")
    st.caption("债券市场晨报、一级发行跟踪与利率风险分析")

    dataset = sample_dataset()
    with st.sidebar:
        st.header("数据源")
        online = st.toggle("使用 AKShare 在线收益率曲线", value=False)
        start_date = st.date_input("开始日期", value=date(2026, 9, 1))
        end_date = st.date_input("结束日期", value=date.today())
        curve_keyword = st.text_input("曲线关键词", value="国债收益率曲线")

    curve = dataset.curve
    source_message = "当前使用合成示例数据。"
    if online:
        try:
            curve = fetch_china_yield_curve(
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d"),
                curve_keyword,
            )
            source_message = "当前使用 AKShare/ChinaBond 在线数据。"
        except DataSourceError as exc:
            st.error(str(exc))
            st.info("已回退到离线示例数据。")
    st.info(source_message)
    curve_long = to_long_curve(curve)

    tab_market, tab_risk, tab_brief = st.tabs(["市场看板", "债券风险", "晨报导出"])

    with tab_market:
        metric_1, metric_2, metric_3 = st.columns(3)
        latest = latest_curve(curve_long).set_index("tenor_years")["yield_pct"]
        metric_1.metric("10Y 收益率", f"{latest.get(10.0, float('nan')):.3f}%")
        try:
            metric_2.metric("2Y-10Y 利差", f"{term_spread(curve_long, 2, 10):.1f}BP")
            metric_3.metric("5Y-10Y 利差", f"{term_spread(curve_long, 5, 10):.1f}BP")
        except ValueError:
            metric_2.metric("2Y-10Y 利差", "N/A")
            metric_3.metric("5Y-10Y 利差", "N/A")
        st.plotly_chart(_curve_chart(curve_long), width="stretch")

        scenario = st.selectbox("曲线情景", ["parallel", "steepener", "flattener"])
        magnitude = st.slider("冲击幅度（BP）", min_value=-50, max_value=50, value=10)
        scenario_frame = apply_curve_scenario(curve_long, scenario, magnitude)
        st.dataframe(
            scenario_frame[
                ["tenor_years", "yield_pct", "shock_bp", "shocked_yield_pct"]
            ],
            width="stretch",
            hide_index=True,
        )

    with tab_risk:
        col_1, col_2, col_3 = st.columns(3)
        settlement = col_1.date_input("结算日", value=date.today(), key="bond_settlement")
        maturity = col_2.date_input(
            "到期日", value=date.today() + relativedelta(years=5)
        )
        frequency = col_3.selectbox("付息频率", [1, 2, 4], index=1)
        coupon = col_1.number_input("票面利率（%）", value=2.20, step=0.01) / 100
        ytm = col_2.number_input("到期收益率（%）", value=1.90, step=0.01) / 100
        face = col_3.number_input("面值", value=100.0, step=10.0)
        try:
            analytics = BondAnalytics(
                BondSpec(settlement, maturity, coupon, frequency, face)
            )
            metrics = analytics.risk_metrics(ytm)
            st.dataframe(
                pd.DataFrame(
                    [{"指标": key, "数值": value} for key, value in metrics.items()]
                ),
                width="stretch",
                hide_index=True,
            )
            st.dataframe(
                analytics.scenario_table(ytm, [-50, -25, -10, 0, 10, 25, 50]),
                width="stretch",
                hide_index=True,
            )
        except ValueError as exc:
            st.error(str(exc))

    with tab_brief:
        brief = generate_morning_brief(
            curve,
            dataset.issuance,
            dataset.news,
        )
        st.markdown(brief)
        st.download_button(
            "下载晨报 Markdown",
            data=brief.encode("utf-8"),
            file_name="fixed_income_brief.md",
            mime="text/markdown",
        )
        st.download_button(
            "下载 Excel 数据包",
            data=excel_bytes(curve, dataset.issuance, dataset.news),
            file_name="fixed_income_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

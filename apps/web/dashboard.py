from __future__ import annotations

import os
from datetime import date
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = 30


def safe_get(path: str, params: dict | None = None):
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return True, resp.json()
    except Exception as exc:
        return False, str(exc)


def safe_post(path: str, params: dict | None = None):
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return True, resp.json()
    except Exception as exc:
        return False, str(exc)


def action_cn(action: str) -> str:
    return {"buy": "买入", "sell": "卖出", "watch": "观望"}.get(action, action)


def action_color(action: str) -> str:
    return {"buy": "#0e9f6e", "sell": "#dc2626", "watch": "#ca8a04"}.get(action, "#374151")


st.set_page_config(page_title="基金舆情决策看板", layout="wide")
st.title("基金舆情决策看板")
st.caption("面向中文用户的多源舆情辅助决策界面")

ok, health = safe_get("/health")
if not ok:
    st.error(f"API 不可用：{health}")
    st.info("请先启动 API：uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000")
    st.stop()

st.success("API 状态正常")

with st.sidebar:
    st.subheader("任务操作")
    if st.button("执行全流程（采集+决策+日报）", use_container_width=True):
        ok, data = safe_post("/pipeline/run")
        if ok:
            st.success("全流程执行成功")
            st.write(data)
        else:
            st.error(data)

    if st.button("仅执行采集", use_container_width=True):
        ok, data = safe_post("/ingest/run")
        st.success("采集完成") if ok else st.error(data)
        if ok:
            st.write(data)

    if st.button("仅执行决策", use_container_width=True):
        ok, data = safe_post("/decision/run")
        st.success("决策完成") if ok else st.error(data)
        if ok:
            st.write(data)

st.divider()

ok, rec_data = safe_get("/portfolio/recommendations")
if not ok:
    st.warning(f"无法加载建议数据：{rec_data}")
    rec_data = []

ok, pos_data = safe_get("/portfolio/positions")
if not ok:
    st.warning(f"无法加载持仓数据：{pos_data}")
    pos_data = []

ok, fund_master = safe_get("/funds/master")
if not ok:
    st.warning(f"无法加载基金主数据：{fund_master}")
    fund_master = []

recs_df = pd.DataFrame(rec_data)
pos_df = pd.DataFrame(pos_data)
fund_df = pd.DataFrame(fund_master)

pending_count = int(pos_df["pending_code_binding"].sum()) if not pos_df.empty and "pending_code_binding" in pos_df else 0
avg_conf = float(recs_df["confidence"].mean()) if not recs_df.empty and "confidence" in recs_df else 0.0
buy_cnt = int((recs_df["action"] == "buy").sum()) if not recs_df.empty and "action" in recs_df else 0
sell_cnt = int((recs_df["action"] == "sell").sum()) if not recs_df.empty and "action" in recs_df else 0
watch_cnt = int((recs_df["action"] == "watch").sum()) if not recs_df.empty and "action" in recs_df else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("持仓基金数", len(pos_df) if not pos_df.empty else 0)
m2.metric("平均置信度", f"{avg_conf:.2f}")
m3.metric("买入/卖出/观望", f"{buy_cnt}/{sell_cnt}/{watch_cnt}")
m4.metric("待绑定基金代码", pending_count)

st.subheader("建议摘要")
if recs_df.empty:
    st.info("暂无建议数据，请先点击左侧“执行全流程”或“仅执行决策”。")
else:
    for _, row in recs_df.iterrows():
        color = action_color(row.get("action", "watch"))
        st.markdown(
            f"""
<div style=\"border-left: 6px solid {color}; padding: 10px 12px; margin: 8px 0; background: #f8fafc;\">
  <div style=\"font-size: 18px; font-weight: 600;\">{row.get('fund_name', '')}（{row.get('fund_code') or '代码待绑定'}）</div>
  <div style=\"margin-top: 6px;\">建议：<b>{action_cn(row.get('action', 'watch'))}</b> | 置信度：<b>{float(row.get('confidence', 0)):.2f}</b> | 建议仓位：<b>{row.get('target_position', '-')}</b></div>
  <div style=\"margin-top: 6px;\">止盈：{row.get('stop_profit', '-')} | 止损：{row.get('stop_loss', '-')}</div>
  <div style=\"margin-top: 6px;\">冲突摘要：{row.get('conflict_summary', '-')}</div>
</div>
""",
            unsafe_allow_html=True,
        )

st.subheader("信号来源分布")
if fund_df.empty:
    st.info("暂无基金主数据")
else:
    selected_fund = st.selectbox("选择基金", options=fund_df["fund_name"].tolist())
    ok, signals = safe_get(f"/funds/{quote(selected_fund, safe='')}/signals")
    if not ok:
        st.warning(f"无法加载信号：{signals}")
    else:
        sig_df = pd.DataFrame(signals)
        if sig_df.empty:
            st.info("暂无该基金信号，请先执行采集。")
        else:
            if "source" in sig_df:
                by_source = sig_df.groupby("source", as_index=False).size().rename(columns={"size": "信号条数", "source": "来源"})
                st.bar_chart(by_source.set_index("来源"))
            show_cols = [c for c in ["source", "publish_time", "polarity", "intensity", "credibility", "relevance", "content"] if c in sig_df.columns]
            st.dataframe(sig_df[show_cols], use_container_width=True)

st.subheader("持仓与基金信息")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**当前持仓**")
    if pos_df.empty:
        st.info("暂无持仓数据")
    else:
        view = pos_df.copy()
        if "pending_code_binding" in view:
            view["代码状态"] = view["pending_code_binding"].map(lambda x: "待绑定" if x else "已绑定")
        show_cols = [c for c in ["fund_name", "fund_code", "amount", "cost", "代码状态", "updated_at"] if c in view.columns]
        st.dataframe(view[show_cols], use_container_width=True)

with c2:
    st.markdown("**基金代码绑定**")
    if fund_df.empty:
        st.info("暂无基金主数据")
    else:
        bind_fund = st.selectbox("基金名称", options=fund_df["fund_name"].tolist(), key="bind_name")
        bind_code = st.text_input("基金代码", placeholder="例如：162411")
        if st.button("绑定代码", use_container_width=True):
            if not bind_code.strip():
                st.warning("请先输入基金代码")
            else:
                ok, data = safe_post("/portfolio/bind-code", params={"fund_name": bind_fund, "fund_code": bind_code.strip()})
                if ok:
                    st.success("绑定成功，请刷新页面查看最新状态")
                else:
                    st.error(data)

st.subheader("每日日报")
selected_date = st.date_input("日期", value=date.today())
ok, report = safe_get("/reports/daily", params={"date": selected_date.isoformat()})
if ok:
    st.markdown(report.get("markdown", ""))
else:
    st.warning(f"无法加载日报：{report}")

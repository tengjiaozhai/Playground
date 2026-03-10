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


def safe_post_json(path: str, payload: dict):
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return True, resp.json()
    except Exception as exc:
        return False, str(exc)


def safe_patch_json(path: str, payload: dict):
    try:
        resp = requests.patch(f"{API_BASE_URL}{path}", json=payload, timeout=TIMEOUT)
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
st.caption("简化版：先运行流程，再看建议与回测")

ok, health = safe_get("/health")
if not ok:
    st.error(f"API 不可用：{health}")
    st.info("请先启动 API：uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000")
    st.stop()

with st.container(border=True):
    a1, a2, a3, a4 = st.columns([2, 1.2, 1.2, 1.4])
    with a1:
        st.markdown("**一步执行**")
        if st.button("一键刷新（采集+决策+日报）", use_container_width=True):
            ok, data = safe_post("/pipeline/run")
            if ok:
                st.success("刷新完成")
                st.caption(f"采集任务：{data.get('ingest_run_id')} | 决策任务：{data.get('decision_run_id')}")
            else:
                st.error(data)
    with a2:
        if st.button("仅采集", use_container_width=True):
            ok, data = safe_post("/ingest/run")
            st.success("采集完成") if ok else st.error(data)
    with a3:
        if st.button("仅决策", use_container_width=True):
            ok, data = safe_post("/decision/run")
            st.success("决策完成") if ok else st.error(data)
    with a4:
        if st.button("运行回测(12个月)", use_container_width=True):
            ok, data = safe_post("/backtest/run", params={"window_days": 365})
            st.success("回测完成") if ok else st.error(data)

ok, rec_data = safe_get("/portfolio/recommendations")
ok_pos, pos_data = safe_get("/portfolio/positions")
ok_fund, fund_master = safe_get("/funds/master")
ok_ingest, ingest_status = safe_get("/ingest/status")
ok_health, source_health = safe_get("/sources/health")
ok_back, back = safe_get("/backtest/metrics")

recs_df = pd.DataFrame(rec_data if ok else [])
pos_df = pd.DataFrame(pos_data if ok_pos else [])
fund_df = pd.DataFrame(fund_master if ok_fund else [])

pending_count = int(pos_df["pending_code_binding"].sum()) if not pos_df.empty and "pending_code_binding" in pos_df else 0
avg_conf = float(recs_df["confidence"].mean()) if not recs_df.empty and "confidence" in recs_df else 0.0
buy_cnt = int((recs_df["action"] == "buy").sum()) if not recs_df.empty and "action" in recs_df else 0
sell_cnt = int((recs_df["action"] == "sell").sum()) if not recs_df.empty and "action" in recs_df else 0
watch_cnt = int((recs_df["action"] == "watch").sum()) if not recs_df.empty and "action" in recs_df else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("当前基金数量", len(pos_df) if not pos_df.empty else 0)
m2.metric("平均置信度", f"{avg_conf:.2f}")
m3.metric("买/卖/观望", f"{buy_cnt}/{sell_cnt}/{watch_cnt}")
m4.metric("待补基金代码", pending_count)

if ok_ingest and ingest_status.get("status") != "not_started":
    st.caption(
        f"最近采集：{ingest_status.get('run_id')} | 模式={ingest_status.get('mode')} | 新增信号={ingest_status.get('created_count')}"
    )


tab1, tab2, tab3 = st.tabs(["投资建议", "数据源与信号", "回测结果"])

with tab1:
    st.subheader("基金建议")
    if recs_df.empty:
        st.info("暂无建议，请先点击“一键刷新”。")
    else:
        for _, row in recs_df.iterrows():
            color = action_color(row.get("action", "watch"))
            up = float(row.get("up_probability", 0.5))
            down = float(row.get("down_probability", 0.5))
            vol = float(row.get("volatility_strength", 0.0))
            st.markdown(
                f"""
<div style=\"border-left: 6px solid {color}; padding: 10px 12px; margin: 8px 0; background: #f8fafc;\">
  <div style=\"font-size: 18px; font-weight: 600;\">{row.get('fund_name', '')}（{row.get('fund_code') or '代码待绑定'}）</div>
  <div style=\"margin-top: 6px;\">建议：<b>{action_cn(row.get('action', 'watch'))}</b> | 置信度：<b>{float(row.get('confidence', 0)):.2f}</b> | 仓位：<b>{row.get('target_position', '-')}</b></div>
  <div style=\"margin-top: 6px;\">上涨概率：{up:.2f} | 下跌概率：{down:.2f} | 波动强度：{vol:.2f}</div>
  <div style=\"margin-top: 6px;\">止盈：{row.get('stop_profit', '-')} | 止损：{row.get('stop_loss', '-')}</div>
  <div style=\"margin-top: 6px;\">冲突摘要：{row.get('conflict_summary', '-')}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("**基金代码绑定**")
    if fund_df.empty:
        st.info("暂无基金主数据")
    else:
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            bind_fund = st.selectbox("基金名称", options=fund_df["fund_name"].tolist(), key="bind_name_v3")
        with c2:
            bind_code = st.text_input("基金代码", placeholder="例如：162411")
        with c3:
            st.write("")
            if st.button("绑定", use_container_width=True):
                if not bind_code.strip():
                    st.warning("请先输入基金代码")
                else:
                    ok_bind, data = safe_post("/portfolio/bind-code", params={"fund_name": bind_fund, "fund_code": bind_code.strip()})
                    st.success("绑定成功，请点击“一键刷新”") if ok_bind else st.error(data)

    st.markdown("**基金管理（手动增删改）**")
    with st.expander("新增或修改基金", expanded=False):
        u1, u2, u3 = st.columns(3)
        with u1:
            old_name = st.text_input("原基金名称（修改时填写）", key="fund_old_name")
            fund_name_new = st.text_input("基金名称", key="fund_new_name", placeholder="例如：华夏中证人工智能")
        with u2:
            fund_code_new = st.text_input("基金代码", key="fund_new_code", placeholder="例如：123456")
            aliases_new = st.text_input("别名（逗号分隔）", key="fund_aliases", placeholder="例如：华夏AI,人工智能ETF联接")
        with u3:
            amount_new = st.number_input("持仓份额", min_value=0.0, value=0.0, step=100.0, key="fund_amount")
            cost_new = st.number_input("持仓成本", min_value=0.0, value=0.0, step=100.0, key="fund_cost")
        if st.button("保存基金", use_container_width=True):
            if not fund_name_new.strip():
                st.warning("基金名称不能为空")
            else:
                payload = {
                    "fund_name": fund_name_new.strip(),
                    "fund_code": fund_code_new.strip(),
                    "aliases": [x.strip() for x in aliases_new.split(",") if x.strip()],
                    "amount": amount_new,
                    "cost": cost_new,
                    "old_fund_name": old_name.strip() or None,
                }
                ok_save, data = safe_post_json("/funds/upsert", payload)
                st.success("基金保存成功，请点击“一键刷新”") if ok_save else st.error(f"保存失败：{data}")

    with st.expander("修改持仓或删除基金", expanded=False):
        if fund_df.empty:
            st.info("暂无基金可操作")
        else:
            f1, f2, f3, f4 = st.columns([2, 1.2, 1.2, 1.2])
            with f1:
                target_fund = st.selectbox("选择基金", options=fund_df["fund_name"].tolist(), key="manage_target_fund")
            with f2:
                amount_edit = st.number_input("新持仓份额", min_value=0.0, value=0.0, step=100.0, key="edit_amount")
            with f3:
                cost_edit = st.number_input("新持仓成本", min_value=0.0, value=0.0, step=100.0, key="edit_cost")
            with f4:
                st.write("")
                if st.button("更新持仓", use_container_width=True):
                    ok_update, data = safe_patch_json(
                        "/funds/position",
                        {"fund_name": target_fund, "amount": amount_edit, "cost": cost_edit},
                    )
                    st.success("持仓更新成功，请点击“一键刷新”") if ok_update else st.error(f"更新失败：{data}")

            if st.button("删除该基金", use_container_width=True, type="secondary"):
                try:
                    resp = requests.delete(f"{API_BASE_URL}/funds", params={"fund_name": target_fund}, timeout=TIMEOUT)
                    resp.raise_for_status()
                    st.success("删除成功，请点击“一键刷新”")
                except Exception as exc:
                    st.error(f"删除失败：{exc}")

with tab2:
    st.subheader("数据源健康")
    if ok_health and source_health:
        health_df = pd.DataFrame(source_health)
        health_df["状态"] = health_df["healthy"].map(lambda x: "正常" if x else "异常")
        cols = [c for c in ["source", "状态", "latency_ms", "message", "checked_at"] if c in health_df.columns]
        st.dataframe(health_df[cols], use_container_width=True)
    else:
        st.info("暂无数据源健康数据")

    st.subheader("基金信号")
    if fund_df.empty:
        st.info("暂无基金主数据")
    else:
        selected_fund = st.selectbox("选择基金", options=fund_df["fund_name"].tolist(), key="sig_fund")
        ok_sig, signals = safe_get(f"/funds/{quote(selected_fund, safe='')}/signals")
        ok_daily, signal_daily = safe_get(f"/funds/{quote(selected_fund, safe='')}/signal-daily", params={"days": 120})
        ok_mkt, market = safe_get(f"/funds/{quote(selected_fund, safe='')}/market-history", params={"days": 180})
        if not ok_sig:
            st.warning(f"无法加载信号：{signals}")
        else:
            sig_df = pd.DataFrame(signals)
            if sig_df.empty:
                st.info("暂无该基金信号")
            else:
                by_source = sig_df.groupby("source", as_index=False).size().rename(columns={"size": "信号条数", "source": "来源"})
                st.bar_chart(by_source.set_index("来源"))

        st.markdown("**净值趋势与信号强度（近180天）**")
        if ok_mkt and ok_daily:
            mdf = pd.DataFrame(market.get("points", []))
            sdf = pd.DataFrame(signal_daily)
            if not mdf.empty:
                mdf["date"] = pd.to_datetime(mdf["date"])
                mdf = mdf.sort_values("date")
                st.line_chart(mdf.set_index("date")["nav"])
                st.caption(f"净值数据来源：{market.get('source', 'unknown')}")
            if not sdf.empty:
                sdf["date"] = pd.to_datetime(sdf["date"])
                sdf = sdf.sort_values("date")
                st.bar_chart(sdf.set_index("date")["avg_score"])
        else:
            st.info("暂无趋势数据")

with tab3:
    st.subheader("12个月回测")
    if ok_back and isinstance(back, dict) and back.get("status") != "not_started":
        metrics = back.get("metrics", [])
        mdf = pd.DataFrame(metrics)
        if mdf.empty:
            st.info("暂无回测指标")
        else:
            rename_map = {
                "fund_name": "基金名称",
                "samples": "样本数",
                "hit_rate": "命中率",
                "max_drawdown": "最大回撤",
                "recommendation_stability": "建议稳定性",
                "signal_latency_hours": "信号延迟(小时)",
                "label_source": "标签来源",
            }
            show_cols = [c for c in ["fund_name", "samples", "hit_rate", "max_drawdown", "recommendation_stability", "signal_latency_hours", "label_source"] if c in mdf.columns]
            view = mdf[show_cols].rename(columns={k: v for k, v in rename_map.items() if k in show_cols})
            st.dataframe(view, use_container_width=True)
    else:
        st.info("尚未运行回测，请点击顶部“运行回测(12个月)”。")

st.subheader("每日日报")
selected_date = st.date_input("日报日期", value=date.today())
ok_report, report = safe_get("/reports/daily", params={"date": selected_date.isoformat()})
if ok_report:
    st.markdown(report.get("markdown", ""))
else:
    st.warning(f"无法加载日报：{report}")

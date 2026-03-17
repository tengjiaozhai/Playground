from __future__ import annotations

import html
import os
from datetime import date, datetime
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = 30

SOURCE_CN = {
    "news": "财经新闻",
    "blog": "专业博客",
    "tiantianfund": "天天基金",
    "tonghuashun-aifund": "同花顺爱基金",
    "eastmoney": "东方财富",
    "social-media": "社交平台",
}

MARKET_SOURCE_CN = {
    "eastmoney_pingzhongdata": "东方财富基金历史净值",
    "eastmoney_lsjz": "东方财富净值接口",
    "proxy": "代理数据（演示）",
    "live_failed": "实时抓取失败",
}

MODE_CN = {
    "hybrid": "自动混合",
    "live": "实时",
    "mock": "演示",
}

ACTION_LABEL = {
    "buy": "买入（可加仓）",
    "sell": "卖出（建议减仓）",
    "watch": "观望（先不动）",
}

ACTION_CLASS = {
    "buy": "card-buy",
    "sell": "card-sell",
    "watch": "card-watch",
}


# ---------- API helpers ----------
def _parse_response(resp: requests.Response):
    try:
        data = resp.json()
    except Exception:
        data = {"message": resp.text[:500]}
    if resp.status_code < 400:
        return True, data
    detail = data.get("detail", data)
    return False, detail


def safe_get(path: str, params: dict | None = None, timeout: int = TIMEOUT):
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=timeout)
        return _parse_response(resp)
    except Exception as exc:
        return False, str(exc)


def safe_post(path: str, params: dict | None = None, timeout: int = TIMEOUT):
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", params=params, timeout=timeout)
        return _parse_response(resp)
    except Exception as exc:
        return False, str(exc)


def safe_post_json(path: str, payload: dict):
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=TIMEOUT)
        return _parse_response(resp)
    except Exception as exc:
        return False, str(exc)


def safe_patch_json(path: str, payload: dict):
    try:
        resp = requests.patch(f"{API_BASE_URL}{path}", json=payload, timeout=TIMEOUT)
        return _parse_response(resp)
    except Exception as exc:
        return False, str(exc)


def safe_delete(path: str, params: dict | None = None):
    try:
        resp = requests.delete(f"{API_BASE_URL}{path}", params=params, timeout=TIMEOUT)
        return _parse_response(resp)
    except Exception as exc:
        return False, str(exc)


# ---------- UI helpers ----------
def fmt_time(value: str | None) -> str:
    if not value:
        return "尚未更新"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def mode_cn(mode: str | None) -> str:
    return MODE_CN.get((mode or "").lower(), mode or "未知")


def source_cn(source: str | None) -> str:
    if not source:
        return "未知来源"
    return SOURCE_CN.get(source, source)


def market_source_cn(source: str | None) -> str:
    if not source:
        return "未知来源"
    return MARKET_SOURCE_CN.get(source, source)


def confidence_level(confidence: float) -> tuple[str, str]:
    # Fixed threshold per product decision.
    if confidence >= 0.8:
        return "高", "信号较一致，可执行性较高"
    if confidence >= 0.6:
        return "中", "方向较明确，建议分批操作"
    return "低", "分歧较大，建议先观望"


def volatility_level(volatility: float) -> tuple[str, str]:
    # Fixed threshold per product decision.
    if volatility >= 0.75:
        return "高", "近期波动偏大，注意回撤"
    if volatility >= 0.4:
        return "中", "波动中等，建议控制仓位"
    return "低", "波动较小，节奏相对平稳"


def tendency_level(probability: float) -> str:
    if probability >= 0.67:
        return "强"
    if probability >= 0.45:
        return "中"
    return "弱"


def backtest_overview(hit_rate: float, max_drawdown: float, stability: float) -> str:
    score = 0
    if hit_rate >= 0.65:
        score += 1
    if max_drawdown <= 0.2:
        score += 1
    if stability >= 0.65:
        score += 1
    if score == 3:
        return "较稳"
    if score == 2:
        return "一般"
    return "偏波动"


def reliability_level(source_health: list[dict]) -> str:
    if not source_health:
        return "未知"
    healthy_count = sum(1 for row in source_health if row.get("healthy"))
    ratio = healthy_count / max(1, len(source_health))
    if ratio >= 0.85:
        return "高（大多数来源可用）"
    if ratio >= 0.6:
        return "中（部分来源不稳定）"
    return "低（建议谨慎解读）"


def first_reason(row: dict) -> str:
    reasons = row.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        return str(reasons[0])
    return "当前没有足够信息给出明确理由"


def risk_hint(row: dict, volatility_text: str) -> str:
    counters = row.get("counter_evidence", [])
    action = row.get("action", "watch")
    if isinstance(counters, list) and counters:
        return "存在反向信号，建议控制仓位并观察 1-2 个交易日。"
    if volatility_text == "高":
        return "波动较大，建议轻仓并严格执行止损。"
    if action == "watch":
        return "建议先不操作，等待更明确的方向。"
    return "风险可控，建议分批而不是一次性操作。"


def is_realtime_market(source: str | None) -> bool:
    return str(source or "").startswith("eastmoney_")


def market_change_text(points: list[dict]) -> str:
    if len(points) < 2:
        return "最近表现：暂无足够净值数据"
    mdf = pd.DataFrame(points)
    mdf["date"] = pd.to_datetime(mdf["date"])
    mdf = mdf.sort_values("date")
    last_nav = float(mdf["nav"].iloc[-1])
    prev_nav = float(mdf["nav"].iloc[-2])
    day_change = ((last_nav - prev_nav) / prev_nav) if prev_nav > 0 else 0.0

    three_month_cut = mdf["date"].iloc[-1] - pd.Timedelta(days=90)
    base_df = mdf[mdf["date"] >= three_month_cut]
    base_nav = float(base_df["nav"].iloc[0]) if not base_df.empty else float(mdf["nav"].iloc[0])
    three_month_change = ((last_nav - base_nav) / base_nav) if base_nav > 0 else 0.0
    return f"最近表现：今日 {day_change * 100:+.2f}% ｜ 近三个月 {three_month_change * 100:+.2f}%"


def executable_status(fund_code: str, confidence: float, market_source: str) -> tuple[str, str]:
    if not fund_code:
        return "先补数据", "缺少基金代码，系统不会落地交易建议"
    if confidence < 0.6:
        return "先观望", "把握度不足，建议继续观察"
    if not is_realtime_market(market_source):
        return "先补数据", "当前不是实时净值，建议先等待数据恢复"
    return "可执行", "满足执行条件，可按仓位建议分批操作"


def llm_stage_cn(stage: str | None) -> str:
    return {
        "decision_review": "决策复核阶段",
    }.get(stage or "", "决策阶段")


def llm_used_count(recs_df: pd.DataFrame) -> int:
    if recs_df.empty or "llm_used" not in recs_df:
        return 0
    return int(recs_df["llm_used"].fillna(False).astype(bool).sum())


def inject_theme() -> None:
    st.markdown(
        """
<style>
:root {
  --bg-main: #f6f3ea;
  --card-bg: #fffdf7;
  --ink-900: #1f2a24;
  --ink-700: #4f5b55;
  --brand: #1d6b57;
  --buy: #1f8f6a;
  --sell: #bf3a30;
  --watch: #c17a22;
  --warn: #c96c1a;
  --border: #e6dfcf;
  --shadow: rgba(31, 42, 36, 0.08);
}

.stApp {
  background: radial-gradient(circle at top right, #fcfaf4 0%, var(--bg-main) 60%);
}

html, body, [class*="css"]  {
  font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", sans-serif;
}

[data-testid="stMetricValue"] {
  color: var(--ink-900);
}

.user-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left-width: 6px;
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 10px;
  box-shadow: 0 4px 14px var(--shadow);
  transition: transform .15s ease, box-shadow .2s ease;
}

.user-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 18px var(--shadow);
}

.card-buy { border-left-color: var(--buy); }
.card-sell { border-left-color: var(--sell); }
.card-watch { border-left-color: var(--watch); }

.card-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink-900);
}

.card-line {
  color: var(--ink-700);
  margin-top: 4px;
  font-size: 14px;
}

.badge {
  display: inline-block;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 700;
}

.badge-ok { background: #d9f0e7; color: #155d48; }
.badge-warn { background: #fce9cf; color: #7d4a14; }
.badge-risk { background: #f7d8d3; color: #7f221b; }

.top-note {
  border: 1px dashed #d6cab2;
  border-radius: 10px;
  background: #fffaf0;
  padding: 8px 10px;
  color: #6a5c45;
  font-size: 13px;
  margin-bottom: 8px;
}

.llm-banner {
  border-radius: 16px;
  padding: 16px 18px;
  margin: 12px 0 18px 0;
  border: 1px solid var(--border);
  box-shadow: 0 8px 24px var(--shadow);
}

.llm-banner-on {
  background: linear-gradient(135deg, #f0fbf6 0%, #fff9ee 100%);
  border-color: #b8ddcf;
}

.llm-banner-off {
  background: linear-gradient(135deg, #f7f4ee 0%, #fffaf3 100%);
}

.llm-banner-warn {
  background: linear-gradient(135deg, #fff3e5 0%, #fff9f2 100%);
  border-color: #efc692;
}

.llm-title {
  font-size: 20px;
  font-weight: 800;
  color: var(--ink-900);
}

.llm-subtitle {
  margin-top: 6px;
  color: var(--ink-700);
  font-size: 14px;
}

.llm-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.llm-step {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(29, 107, 87, 0.08);
  color: #185646;
  font-size: 12px;
  font-weight: 700;
}

.llm-step-active {
  background: #1d6b57;
  color: #fff;
}

.llm-chip {
  display: inline-block;
  margin-top: 8px;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 800;
}

.llm-chip-on {
  background: #d8efe6;
  color: #155845;
}

.llm-chip-off {
  background: #efe7d6;
  color: #6e5d3d;
}
</style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="基金助手看板", layout="wide")
inject_theme()

st.title("基金助手看板")
st.caption("给新手看的版本：先看“今天怎么做”，再看细节。")

if "backtest_error" not in st.session_state:
    st.session_state["backtest_error"] = None

ok_health_api, health = safe_get("/health")
if not ok_health_api:
    st.error("页面暂时连不上后台服务，请先启动 API。")
    with st.expander("查看技术详情", expanded=False):
        st.code(str(health))
        st.code("uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000")
    st.stop()

with st.container(border=True):
    st.markdown("### 今日先做这一步")
    c1, c2 = st.columns([2.2, 1])
    with c1:
        if st.button("更新数据并刷新建议（推荐）", use_container_width=True):
            with st.spinner("正在汇总舆情，并用大模型复核基金建议，请稍等..."):
                # Pipeline may take longer when LLM reviews multiple funds.
                ok_pipeline, data = safe_post("/pipeline/run", timeout=180)
            if ok_pipeline:
                st.success("更新完成，页面已使用最新数据。")
            else:
                st.error("更新失败，请稍后重试。")
                with st.expander("查看技术详情", expanded=False):
                    st.code(str(data))
    with c2:
        st.markdown(
            "<div class='top-note'>系统会自动完成：采集信息 -> 规则初判 -> DeepSeek复核 -> 更新日报（新增基金时可能需要 30-90 秒）</div>",
            unsafe_allow_html=True,
        )

    with st.expander("高级操作（可选）", expanded=False):
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("仅更新信息来源", use_container_width=True):
                ok_run, data = safe_post("/ingest/run")
                st.success("信息来源更新完成") if ok_run else st.warning("操作失败，请重试")
                if not ok_run:
                    with st.expander("查看技术详情", expanded=False):
                        st.code(str(data))
        with a2:
            if st.button("仅重算建议", use_container_width=True):
                with st.spinner("正在进入决策阶段，并尝试调用 DeepSeek 进行复核..."):
                    ok_run, data = safe_post("/decision/run", timeout=120)
                st.success("建议重算完成") if ok_run else st.warning("操作失败，请重试")
                if not ok_run:
                    with st.expander("查看技术详情", expanded=False):
                        st.code(str(data))
        with a3:
            if st.button("运行历史参考测试(12个月)", use_container_width=True):
                ok_run, data = safe_post("/backtest/run", params={"window_days": 365})
                if ok_run:
                    st.session_state["backtest_error"] = None
                    st.success("历史参考测试完成")
                else:
                    st.session_state["backtest_error"] = data
                    st.warning("历史参考测试失败，请查看详情")

ok_rec, rec_data = safe_get("/portfolio/recommendations")
ok_pos, pos_data = safe_get("/portfolio/positions")
ok_fund, fund_master = safe_get("/funds/master")
ok_ingest, ingest_status = safe_get("/ingest/status")
ok_source_health, source_health = safe_get("/sources/health")
ok_back, back_data = safe_get("/backtest/metrics")
ok_llm, llm_status = safe_get("/system/llm-status")

recs_df = pd.DataFrame(rec_data if ok_rec else [])
pos_df = pd.DataFrame(pos_data if ok_pos else [])
fund_df = pd.DataFrame(fund_master if ok_fund else [])
source_health_rows = source_health if ok_source_health and isinstance(source_health, list) else []
llm_status = llm_status if ok_llm and isinstance(llm_status, dict) else {}

last_update = fmt_time(ingest_status.get("finished_at")) if ok_ingest and isinstance(ingest_status, dict) else "尚未更新"
new_signal_count = int(ingest_status.get("created_count", 0)) if ok_ingest and isinstance(ingest_status, dict) else 0
health_text = reliability_level(source_health_rows)

market_cache: dict[str, dict] = {}


def load_market_for_fund(fund_name: str) -> dict:
    if fund_name in market_cache:
        return market_cache[fund_name]
    ok_mkt, market = safe_get(f"/funds/{quote(fund_name, safe='')}/market-history", params={"days": 180})
    market_cache[fund_name] = market if ok_mkt and isinstance(market, dict) else {}
    return market_cache[fund_name]


executable_count = 0
if not recs_df.empty:
    for _, row in recs_df.iterrows():
        market = load_market_for_fund(str(row.get("fund_name", "")))
        status_text, _ = executable_status(
            str(row.get("fund_code", "")),
            float(row.get("confidence", 0.0)),
            str(market.get("source", "")),
        )
        if status_text == "可执行":
            executable_count += 1

summary_exec = f"{executable_count}/{len(recs_df)} 只基金可执行" if not recs_df.empty else "暂无建议"
llm_count = llm_used_count(recs_df)

m1, m2, m3, m4 = st.columns(4)
m1.metric("上次更新时间", last_update)
m2.metric("本次新增信息", f"{new_signal_count} 条")
m3.metric("数据可靠度", health_text)
m4.metric("可直接执行", summary_exec)

if llm_status.get("ready"):
    st.markdown(
        f"""
<div class="llm-banner llm-banner-on">
  <div class="llm-title">DeepSeek 辅助推理已开启</div>
  <div class="llm-subtitle">当前模型：{html.escape(str(llm_status.get("model", "deepseek-chat")))} ｜ 执行位置：{html.escape(llm_stage_cn(str(llm_status.get("stage", ""))))} ｜ 本轮已复核 {llm_count}/{len(recs_df) if not recs_df.empty else 0} 只基金</div>
  <div class="llm-flow">
    <span class="llm-step">舆情汇总</span>
    <span class="llm-step">规则初判</span>
    <span class="llm-step llm-step-active">DeepSeek 复核</span>
    <span class="llm-step">最终建议</span>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
elif llm_status.get("enabled"):
    st.markdown(
        f"""
<div class="llm-banner llm-banner-warn">
  <div class="llm-title">大模型开关已打开，但这轮还没真正跑起来</div>
  <div class="llm-subtitle">{html.escape(str(llm_status.get("reason", "当前大模型不可用")))}</div>
</div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
<div class="llm-banner llm-banner-off">
  <div class="llm-title">当前仅使用规则引擎</div>
  <div class="llm-subtitle">还没有启用 DeepSeek 辅助推理，所以建议完全来自规则和统计信号。</div>
</div>
        """,
        unsafe_allow_html=True,
    )

tab1, tab2, tab3 = st.tabs(["今天怎么做", "基金走势与数据", "历史参考表现"])

with tab1:
    st.subheader("今日操作建议")
    if recs_df.empty:
        st.info("当前还没有建议，点击上方“更新数据并刷新建议（推荐）”即可生成。")
    else:
        for _, row in recs_df.iterrows():
            fund_name = str(row.get("fund_name", ""))
            fund_code = str(row.get("fund_code", ""))
            action = str(row.get("action", "watch"))
            action_text = ACTION_LABEL.get(action, "观望（先不动）")
            conf = float(row.get("confidence", 0.0))
            conf_text, conf_hint = confidence_level(conf)
            vol_text, vol_hint = volatility_level(float(row.get("volatility_strength", 0.0)))

            market = load_market_for_fund(fund_name)
            mkt_source = str(market.get("source", ""))
            run_state, run_hint = executable_status(fund_code, conf, mkt_source)
            market_points = market.get("points", []) if isinstance(market, dict) else []
            perf_text = market_change_text(market_points if isinstance(market_points, list) else [])

            up_t = tendency_level(float(row.get("up_probability", 0.5)))
            down_t = tendency_level(float(row.get("down_probability", 0.5)))
            reason_text = html.escape(first_reason(row))
            risk_text = html.escape(risk_hint(row, vol_text))
            cls = ACTION_CLASS.get(action, "card-watch")
            llm_used = bool(row.get("llm_used", False))
            llm_provider = str(row.get("llm_provider", "DeepSeek"))
            llm_model = str(row.get("llm_model", ""))
            llm_explanation = str(row.get("llm_explanation", "")).strip()
            llm_risk_note = str(row.get("llm_risk_note", "")).strip()
            llm_chip_class = "llm-chip-on" if llm_used else "llm-chip-off"
            llm_chip_text = (
                f"{llm_provider} 已参与复核"
                if llm_used
                else "本轮未启用大模型复核"
            )

            badge_class = "badge-ok" if run_state == "可执行" else "badge-warn"
            if run_state == "先观望":
                badge_class = "badge-risk"

            st.markdown(
                f"""
<div class="user-card {cls}">
  <div class="card-title">{html.escape(fund_name)}（{html.escape(fund_code or '代码待补全')}）</div>
  <div class="card-line"><span class="llm-chip {llm_chip_class}">{html.escape(llm_chip_text)}</span></div>
  <div class="card-line">今日建议：<b>{html.escape(action_text)}</b></div>
  <div class="card-line">把握等级：<b>{conf_text}</b>（{html.escape(conf_hint)}）</div>
  <div class="card-line">建议仓位：<b>{html.escape(str(row.get('target_position', '-')))}</b></div>
  <div class="card-line">方向倾向：上涨{up_t} ｜ 下跌{down_t}</div>
  <div class="card-line">波动风险：<b>{vol_text}</b>（{html.escape(vol_hint)}）</div>
  <div class="card-line">一句话原因：{reason_text}</div>
  <div class="card-line">大模型复核：{html.escape(llm_explanation or '当前没有额外的大模型复核意见')}</div>
  <div class="card-line">大模型提醒：{html.escape(llm_risk_note or '暂无额外风险提示')}</div>
  <div class="card-line">风险提醒：{risk_text}</div>
  <div class="card-line">{html.escape(perf_text)}</div>
  <div class="card-line">执行状态：<span class="badge {badge_class}">{run_state}</span>（{html.escape(run_hint)}）</div>
</div>
                """,
                unsafe_allow_html=True,
            )

            with st.expander(f"{fund_name} 的高级信息", expanded=False):
                st.write(
                    {
                        "本次更新编号": ingest_status.get("run_id", "") if isinstance(ingest_status, dict) else "",
                        "净值来源": market_source_cn(mkt_source),
                        "来源代码": mkt_source,
                        "来源URL": market.get("source_url", ""),
                        "抓取时间(UTC)": market.get("fetched_at", ""),
                        "大模型提供方": llm_provider if llm_used else "",
                        "大模型模型名": llm_model if llm_used else "",
                        "大模型执行位置": llm_stage_cn(str(row.get("llm_stage", ""))) if llm_used else "",
                        "止盈阈值": row.get("stop_profit", ""),
                        "止损阈值": row.get("stop_loss", ""),
                        "冲突摘要": row.get("conflict_summary", ""),
                    }
                )

    st.markdown("### 持仓与基金管理")
    with st.expander("基金代码绑定（建议先完成）", expanded=False):
        if fund_df.empty:
            st.info("暂无基金数据")
        else:
            b1, b2, b3 = st.columns([2, 2, 1])
            with b1:
                bind_fund = st.selectbox("基金名称", options=fund_df["fund_name"].tolist(), key="bind_name_v4")
            with b2:
                bind_code = st.text_input("基金代码", placeholder="例如：007844")
            with b3:
                st.write("")
                if st.button("保存代码", use_container_width=True):
                    if not bind_code.strip():
                        st.warning("请先输入基金代码")
                    else:
                        ok_bind, data = safe_post(
                            "/portfolio/bind-code",
                            params={"fund_name": bind_fund, "fund_code": bind_code.strip()},
                        )
                        if ok_bind:
                            st.success("基金代码已保存，建议点击上方“一键更新”。")
                        else:
                            st.warning("保存失败，请重试")
                            with st.expander("查看技术详情", expanded=False):
                                st.code(str(data))

    with st.expander("新增/修改/删除基金", expanded=False):
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

        if st.button("保存基金信息", use_container_width=True):
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
                if ok_save:
                    st.success("基金信息已保存，建议点击上方“一键更新”。")
                else:
                    st.warning("保存失败，请重试")
                    with st.expander("查看技术详情", expanded=False):
                        st.code(str(data))

        if not fund_df.empty:
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
                    if ok_update:
                        st.success("持仓已更新，建议点击上方“一键更新”。")
                    else:
                        st.warning("更新失败，请重试")
                        with st.expander("查看技术详情", expanded=False):
                            st.code(str(data))

            if st.button("删除该基金", use_container_width=True, type="secondary"):
                ok_del, data = safe_delete("/funds", params={"fund_name": target_fund})
                if ok_del:
                    st.success("基金已删除，建议点击上方“一键更新”。")
                else:
                    st.warning("删除失败，请重试")
                    with st.expander("查看技术详情", expanded=False):
                        st.code(str(data))

with tab2:
    st.subheader("数据是否可靠")
    if source_health_rows:
        health_df = pd.DataFrame(source_health_rows)
        health_df["来源"] = health_df["source"].map(source_cn)
        health_df["可用状态"] = health_df["healthy"].map(lambda x: "可用" if x else "暂不可用")
        health_df["响应耗时(毫秒)"] = health_df["latency_ms"]
        health_df["检查时间"] = health_df["checked_at"].map(fmt_time)
        show_cols = ["来源", "可用状态", "响应耗时(毫秒)", "message", "检查时间"]
        view = health_df[show_cols].rename(columns={"message": "说明"})
        st.dataframe(view, use_container_width=True)
    else:
        st.info("暂无来源健康数据")

    st.subheader("基金走势与情绪热度")
    if fund_df.empty:
        st.info("暂无基金主数据")
    else:
        selected_fund = st.selectbox("选择基金", options=fund_df["fund_name"].tolist(), key="sig_fund")
        ok_sig, signals = safe_get(f"/funds/{quote(selected_fund, safe='')}/signals")
        ok_daily, signal_daily = safe_get(
            f"/funds/{quote(selected_fund, safe='')}/signal-daily",
            params={"days": 120},
        )
        market = load_market_for_fund(selected_fund)

        if ok_sig:
            sig_df = pd.DataFrame(signals)
            if sig_df.empty:
                st.info("该基金暂无舆情记录")
            else:
                by_source = sig_df.groupby("source", as_index=False).size().rename(columns={"size": "条数", "source": "来源"})
                by_source["来源"] = by_source["来源"].map(source_cn)
                st.markdown("**最近信息来自哪里**")
                st.bar_chart(by_source.set_index("来源")["条数"])
        else:
            st.warning("舆情数据加载失败，请稍后重试")
            with st.expander("查看技术详情", expanded=False):
                st.code(str(signals))

        mdf = pd.DataFrame(market.get("points", []) if isinstance(market, dict) else [])
        if not mdf.empty:
            mdf["date"] = pd.to_datetime(mdf["date"])
            mdf = mdf.sort_values("date")

            last_nav = float(mdf["nav"].iloc[-1])
            prev_nav = float(mdf["nav"].iloc[-2]) if len(mdf) >= 2 else last_nav
            day_change_pct = ((last_nav - prev_nav) / prev_nav) if prev_nav > 0 else 0.0
            three_month_cut = mdf["date"].iloc[-1] - pd.Timedelta(days=90)
            base_df = mdf[mdf["date"] >= three_month_cut]
            base_nav = float(base_df["nav"].iloc[0]) if not base_df.empty else float(mdf["nav"].iloc[0])
            three_month_change_pct = ((last_nav - base_nav) / base_nav) if base_nav > 0 else 0.0

            c1, c2 = st.columns(2)
            c1.metric("今日涨跌", f"{day_change_pct * 100:+.2f}%")
            c2.metric("近三个月涨跌", f"{three_month_change_pct * 100:+.2f}%")

            st.markdown("**近180天净值走势**")
            st.line_chart(mdf.set_index("date")["nav"])

            src = str(market.get("source", ""))
            if is_realtime_market(src):
                st.success("当前显示的是实时来源净值。")
            elif src == "proxy":
                st.warning("当前显示的是演示代理净值，不能用于真实交易。")
            else:
                st.warning("净值来源暂不稳定，建议谨慎解读。")

            with st.expander("高级信息（来源追溯）", expanded=False):
                st.write(
                    {
                        "基金代码": market.get("fund_code", ""),
                        "基金名称": market.get("fund_name", ""),
                        "净值来源": market_source_cn(src),
                        "来源代码": src,
                        "来源URL": market.get("source_url", ""),
                        "抓取时间(UTC)": market.get("fetched_at", ""),
                    }
                )
        else:
            st.info("暂无该基金净值走势数据")

        sdf = pd.DataFrame(signal_daily if ok_daily else [])
        if not sdf.empty:
            sdf["date"] = pd.to_datetime(sdf["date"])
            sdf = sdf.sort_values("date")
            st.markdown("**近120天情绪热度变化**")
            st.bar_chart(sdf.set_index("date")["avg_score"])

with tab3:
    st.subheader("历史参考表现（12个月）")
    bt_err = st.session_state.get("backtest_error")
    if bt_err:
        st.warning("历史参考测试暂时失败，建议先看当前建议并稍后重试。")
        with st.expander("查看技术详情", expanded=False):
            st.code(str(bt_err))

    if ok_back and isinstance(back_data, dict) and back_data.get("status") != "not_started":
        metrics = back_data.get("metrics", [])
        mdf = pd.DataFrame(metrics)
        if mdf.empty:
            st.info("暂无历史参考结果")
        else:
            mdf["历史参考结论"] = mdf.apply(
                lambda r: backtest_overview(
                    float(r.get("hit_rate", 0.0)),
                    float(r.get("max_drawdown", 0.0)),
                    float(r.get("recommendation_stability", 0.0)),
                ),
                axis=1,
            )
            mdf["基金"] = mdf["fund_name"]
            mdf["参考建议"] = mdf["历史参考结论"].map(
                {
                    "较稳": "历史表现较稳，可作为参考",
                    "一般": "表现中等，建议谨慎参考",
                    "偏波动": "波动较大，建议降低信任权重",
                }
            )
            view = mdf[["基金", "历史参考结论", "参考建议"]]
            st.dataframe(view, use_container_width=True)

            with st.expander("高级信息（回测明细）", expanded=False):
                raw_cols = [
                    "fund_name",
                    "samples",
                    "hit_rate",
                    "max_drawdown",
                    "recommendation_stability",
                    "signal_latency_hours",
                    "label_source",
                ]
                show_cols = [c for c in raw_cols if c in mdf.columns]
                detail = mdf[show_cols].rename(
                    columns={
                        "fund_name": "基金名称",
                        "samples": "样本数",
                        "hit_rate": "命中率",
                        "max_drawdown": "最大回撤",
                        "recommendation_stability": "建议稳定性",
                        "signal_latency_hours": "信号延迟(小时)",
                        "label_source": "标签来源",
                    }
                )
                st.dataframe(detail, use_container_width=True)
                st.write(
                    {
                        "本次更新编号": back_data.get("run_id", ""),
                        "测试窗口": f"{back_data.get('window_days', 365)} 天",
                        "生成时间": fmt_time(back_data.get("generated_at", "")),
                    }
                )
    else:
        st.info("还没有历史参考结果。可在“高级操作”里运行 12 个月测试。")

st.subheader("每日日报")
selected_date = st.date_input("选择日期", value=date.today())
ok_report, report = safe_get("/reports/daily", params={"date": selected_date.isoformat()})
if ok_report:
    st.markdown(report.get("markdown", ""))
else:
    st.warning("日报加载失败，请稍后重试")
    with st.expander("查看技术详情", expanded=False):
        st.code(str(report))

with st.expander("全局高级信息（追溯与排障）", expanded=False):
    st.write(
        {
            "本次更新编号": ingest_status.get("run_id", "") if isinstance(ingest_status, dict) else "",
            "采集模式": mode_cn(ingest_status.get("mode", "") if isinstance(ingest_status, dict) else ""),
            "采集模式代码": ingest_status.get("mode", "") if isinstance(ingest_status, dict) else "",
            "新增信息条数": ingest_status.get("created_count", 0) if isinstance(ingest_status, dict) else 0,
            "大模型已开启": bool(llm_status.get("enabled", False)),
            "大模型可调用": bool(llm_status.get("ready", False)),
            "大模型提供方": llm_status.get("provider", ""),
            "大模型模型名": llm_status.get("model", ""),
            "大模型执行阶段": llm_stage_cn(str(llm_status.get("stage", ""))),
            "大模型状态说明": llm_status.get("reason", ""),
            "来源健康详情": source_health_rows,
        }
    )

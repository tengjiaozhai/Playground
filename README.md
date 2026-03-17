# 基金舆情决策系统（Fund Sentiment Trading）

一个可直接运行的 Python 全栈项目：采集多源舆情 -> 生成基金建议 -> 输出看板与日报。支持规则决策，也支持 DeepSeek 在“决策复核阶段”参与辅助推理。

## 给其他大模型的快速上下文（可直接复制）

```text
你在维护一个 Python 项目：/Users/shenmingjie/Documents/Playground
目标：多源舆情驱动的基金决策辅助（研究用途，不构成投资建议）

关键入口：
- API: apps/api/main.py (FastAPI, 8000)
- Web: apps/web/dashboard.py (Streamlit, 8501)
- 核心逻辑: packages/common/*

核心流程：
1) POST /ingest/run 采集舆情
2) POST /decision/run 规则初判 + (可选) DeepSeek复核
3) GET /portfolio/recommendations 查看建议
4) GET /reports/daily?date=YYYY-MM-DD 查看日报
5) POST /pipeline/run 一键跑全链路

重要规则：
- 基金必须 name+code 双主键
- pending_code_binding=true 时禁止落地交易动作
- 推荐结果必须带证据来源、冲突摘要、时间戳

大模型状态：
- GET /system/llm-status
- 若 ENABLE_LLM_ASSIST=true 且 key 可用，则在 decision_review 阶段执行
```

## 1. 一次启动（Conda）

```bash
cd /Users/shenmingjie/Documents/Playground
conda env create -f environment.yml
conda activate fund-sentiment-trading
cp .env.example .env
```

依赖变化后可更新：

```bash
conda env update -f environment.yml --prune
```

## 2. 启动服务

终端 A（API）：

```bash
cd /Users/shenmingjie/Documents/Playground
conda activate fund-sentiment-trading
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

终端 B（看板）：

```bash
cd /Users/shenmingjie/Documents/Playground
conda activate fund-sentiment-trading
streamlit run apps/web/dashboard.py --server.address 0.0.0.0 --server.port 8501
```

访问地址：
- API 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 看板：[http://127.0.0.1:8501](http://127.0.0.1:8501)

## 3. 3 分钟验收（最小可用）

```bash
curl -X POST http://127.0.0.1:8000/pipeline/run
curl http://127.0.0.1:8000/portfolio/recommendations
curl "http://127.0.0.1:8000/reports/daily?date=$(date +%F)"
```

如果你在看板点击“一键更新”，新增基金后可能需要 `30-90 秒`，这是正常现象（包含 DeepSeek 复核耗时）。

## 4. 环境变量（.env）

基础：

```env
INGEST_ADAPTER_MODE=hybrid
MARKET_DATA_MODE=auto
```

LLM 辅助（可选）：

```env
ENABLE_LLM_ASSIST=true
DEEPSEEK_API_KEY=你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_MAX_TOKENS=400
```

说明：
- `INGEST_ADAPTER_MODE`: `mock|live|hybrid`
- `MARKET_DATA_MODE`: `proxy|live|auto`
- `ENABLE_LLM_ASSIST=false` 时，系统只用规则引擎
- LLM 开启后执行位置是 `decision_review`（规则初判后复核）

## 5. API 速查

全链路：
- `POST /pipeline/run`

采集与信号：
- `POST /ingest/run`
- `GET /ingest/status`
- `GET /sources/health`
- `GET /funds/{code_or_name}/signals`
- `GET /funds/{code_or_name}/signal-daily`
- `GET /funds/{code_or_name}/market-history`

决策与持仓：
- `POST /decision/run`
- `GET /portfolio/recommendations`
- `GET /portfolio/positions`
- `GET /funds/master`
- `POST /funds/upsert`
- `PATCH /funds/position`
- `DELETE /funds?fund_name=xxx`
- `POST /portfolio/bind-code`

回测与报告：
- `POST /backtest/run`
- `GET /backtest/metrics`
- `GET /reports/daily?date=YYYY-MM-DD`

系统状态：
- `GET /health`
- `GET /system/llm-status`

## 6. 常见问题

Q: 看板提示“一键更新失败”，但 API 其实成功了？  
A: 通常是前端请求超时。当前已把长流程超时放宽；若仍偶发，先看 `POST /pipeline/run` 是否返回 200，再看日志。

Q: 为什么净值有时显示到昨天？  
A: 不同上游更新时间不同。系统会优先选择“最近交易日更晚”的来源；如仍异常，检查 `market-history` 返回的 `source/source_url/fetched_at`。

Q: 如何判断大模型是否真的参与？  
A: 先看 `GET /system/llm-status` 的 `ready`，再看建议字段里的 `llm_used/llm_model/llm_explanation`。

## 7. 目录速览

```text
apps/
  api/        # FastAPI 接口
  web/        # Streamlit 看板
  worker/     # 任务与调度
packages/
  common/     # 决策、采集、回测、模型定义
docs/
  计划版本.md
  实现说明.md
skills/
  fund-sentiment-trading-planner/
```

## 8. 开发规范与文档

- 每次功能实现后都要追加 [实现说明.md](/Users/shenmingjie/Documents/Playground/docs/实现说明.md)
- 版本阶段与里程碑维护在 [计划版本.md](/Users/shenmingjie/Documents/Playground/docs/计划版本.md)
- 如修改决策/回测口径，先同步 skill 参考文档再改代码

## 9. 测试

```bash
cd /Users/shenmingjie/Documents/Playground
conda activate fund-sentiment-trading
pytest -q
```

## 10. 风险提示

本项目输出仅用于研究与辅助决策，不构成投资建议。实盘请自行做风险评估并保留人工确认环节。

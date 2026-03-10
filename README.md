# 基金舆情决策系统（Fund Sentiment Trading）

一个基于 Python 的全栈项目，用于多源舆情驱动的基金涨跌推测与交易辅助决策。

## 1. 使用 Conda 创建与管理环境

```bash
cd /Users/shenmingjie/Documents/Playground
conda env create -f environment.yml
conda activate fund-sentiment-trading
cp .env.example .env
```

如果后续依赖有变化：

```bash
conda env update -f environment.yml --prune
```

## 2. 启动 API 服务

```bash
conda activate fund-sentiment-trading
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 3. 启动 Web 看板（可选）

新开一个终端：

```bash
cd /Users/shenmingjie/Documents/Playground
conda activate fund-sentiment-trading
streamlit run apps/web/dashboard.py
```

默认访问：
- [http://127.0.0.1:8501](http://127.0.0.1:8501)

## 4. 运行测试

```bash
cd /Users/shenmingjie/Documents/Playground
conda activate fund-sentiment-trading
python -m pytest -q
```

## 5. 当前已实现接口

- `POST /ingest/run`
- `GET /ingest/status`
- `GET /sources/health`
- `GET /funds/{code_or_name}/signals`
- `GET /funds/{code_or_name}/signal-daily`
- `GET /funds/{code_or_name}/market-history`
- `POST /decision/run`
- `GET /portfolio/recommendations`
- `GET /portfolio/positions`
- `GET /funds/master`
- `POST /funds/upsert`（新增或修改基金）
- `PATCH /funds/position`（更新持仓份额与成本）
- `DELETE /funds?fund_name=xxx`（删除基金）
- `GET /reports/daily?date=YYYY-MM-DD`
- `POST /pipeline/run`
- `POST /backtest/run`
- `GET /backtest/metrics`

## 6. V2 实现说明（当前）

- 已实现六类数据源适配器：新闻、博客、天天基金、同花顺爱基金、东方财富、社媒。
- 已实现统一采集协议字段：`source_id`、`publish_time`、`content`、`symbol_candidates`、`credibility_score`。
- 已实现双重去重：`(source, source_id)` + `content_hash`。
- 已实现特征层：`polarity`、`intensity`、`heat`、`spread_speed`、`credibility`、`relevance`、`conflict`。
- 已实现采集状态与数据源健康查询接口。
- 当前适配器为可替换的 V2 基线实现（Mock 适配器），便于后续接入真实站点抓取。
- 已支持采集模式切换：`INGEST_ADAPTER_MODE=mock|live|hybrid`（默认 `hybrid`）。
  - `mock`：稳定测试模式，不依赖外网。
  - `live`：仅真实抓取，来源不可达时可能无数据。
  - `hybrid`：优先真实抓取，失败自动回退到 mock。
- 已在 live 模式接入站点专用解析器（标题/描述/关键词上下文）与抓取稳定性机制（重试、限流、熔断）。
- 已支持市场标签模式：`MARKET_DATA_MODE=auto|proxy|live`（默认 `auto`）。
  - `auto`：优先真实净值，失败回退代理序列。
  - `proxy`：仅使用代理序列（适合测试）。
  - `live`：只用真实净值，失败不回退。

## 7. 说明

- 系统输出仅用于研究与辅助决策，不构成投资建议。
- 若基金处于 `pending_code_binding=true`，系统会阻断交易动作并降级为观望。
- 每次功能实现完成后，需同步更新 `docs/实现说明.md`。

## 8. V3 当前能力

- 决策结果已包含：上涨概率、下跌概率、波动强度、置信度。
- 回测接口可输出：命中率、最大回撤、建议稳定性、信号延迟（按基金维度）。
- 仪表盘已简化为三页签：投资建议、数据源与信号、回测结果。

## 9. DeepSeek + LangChain 辅助分析（可选）

在 `.env` 中配置：

```env
ENABLE_LLM_ASSIST=true
DEEPSEEK_API_KEY=你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_MAX_TOKENS=400
INGEST_ADAPTER_MODE=hybrid
MARKET_DATA_MODE=auto
```

说明：
- 默认关闭，不影响原有规则决策。
- 开启后会在规则决策基础上追加 LLM 解释，并在高置信度场景允许微调动作。
- 不要把真实 API Key 提交到 git；建议仅保存在本地 `.env`。
- 仪表盘支持基金手动增删改，适合小规模人工维护持仓池。

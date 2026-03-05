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
- `GET /funds/{code_or_name}/signals`
- `POST /decision/run`
- `GET /portfolio/recommendations`
- `GET /reports/daily?date=YYYY-MM-DD`
- `POST /pipeline/run`

## 6. 说明

- 系统输出仅用于研究与辅助决策，不构成投资建议。
- 若基金处于 `pending_code_binding=true`，系统会阻断交易动作并降级为观望。
- 每次功能实现完成后，需同步更新 `docs/实现说明.md`。

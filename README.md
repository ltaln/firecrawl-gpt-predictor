# Firecrawl GPT Predictor

自动抓取指定网页，保留尽可能完整的页面内容，并交给 GPT 做结构化分析/预测。

## 工作流

1. Firecrawl v2 抓取 URL，同时保存 `markdown`、`html`、`rawHtml`。
2. 将抓取结果保存到 `data/raw/`。
3. 使用 OpenAI Responses API 对抓取内容进行分析。
4. 输出结果到 `data/predictions/`。
5. GitHub Actions 支持手动运行，并可将结果自动提交回仓库。

## 必需的 GitHub Secrets

- `FIRECRAWL_API_KEY`
- `OPENAI_API_KEY`

可选变量：

- `FIRECRAWL_ENDPOINT`：Firecrawl v2 scrape 完整 HTTPS 地址。未设置时继续使用 Cloud。
- `FIRECRAWL_SELFHOST_API_KEY`：自建服务的访问令牌。设置自建入口后工作流使用此令牌；原 `FIRECRAWL_API_KEY` 保留用于 Cloud 回退。删除 `FIRECRAWL_ENDPOINT` 即恢复 Cloud。
- `OPENAI_MODEL`：默认 `gpt-5.6-sol`。

## 本地运行

```bash
pip install -r requirements.txt
export FIRECRAWL_API_KEY=...
export FIRECRAWL_ENDPOINT=http://127.0.0.1:3002/v2/scrape
export OPENAI_API_KEY=...
python run_pipeline.py --date 2026-09-01
```

默认 URL 在 `urls.txt`。也可以通过 `--urls` 临时传入多个地址。

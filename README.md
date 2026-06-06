# investment-learning-radar

`investment-learning-radar` 是一个投资学习和观察项目。默认输出是静态网页：

```text
docs/index.html
docs/dashboard.html
```

`docs/index.html` 可以直接用 GitHub Pages 展示，`docs/dashboard.html` 是同内容副本。项目不做自动交易，不连接 IBKR 下单接口，不提供买卖建议。

## 目标

每天收集真实国际财经新闻，分析它们可能影响的板块、ETF 和个股，并记录后续市场表现，帮助学习：

```text
新闻 -> 板块 -> ETF/个股 -> 市场反应
```

页面会明确提示：

```text
本页面仅用于投资学习，不构成投资建议。
```

## 当前功能

- 从 RSS/free API 抓取真实新闻。
- 抓取阶段不调用 AI。
- SQLite 保存新闻原始信息、AI 分析和行情追踪。
- 根据来源和关键词评分。
- 只对高分新闻调用 AI，控制成本。
- 每次运行后生成 `docs/index.html` 和 `docs/dashboard.html`。
- 页面包含：
  - 今日晨报
  - 美股盘前观察
  - 本周复盘
  - 来源、发布时间、原始链接
  - 已确认事实
  - AI 分析
  - 不确定部分
  - 可能影响板块
  - 观察 ETF
  - 观察个股
  - 1天、5天、20天后涨跌追踪
- GitHub Actions 可自动更新网页。
- 邮件功能保留，但默认不使用。

## 安装依赖

需要 Python 3.11+。

```bash
cd investment-learning-radar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell：

```powershell
cd investment-learning-radar
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 配置 .env

复制模板：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

推荐配置：

```env
OPENAI_API_KEY=你的 OpenAI API key
OPENAI_MODEL=gpt-4.1-mini
DATABASE_URL=sqlite:///data/investment_radar.sqlite3
TIMEZONE=Europe/Helsinki
EMAIL_DRY_RUN=true
MAX_REPORT_ITEMS=10
MIN_AI_SCORE=8
REPORT_LOOKBACK_HOURS=24
```

如果没有 `OPENAI_API_KEY`，系统仍会抓取新闻和生成网页，但不会编造 AI 分析，会标记为未进行 AI 分析。

## 本地运行一次网页更新

```bash
python main.py dashboard
```

也可以按报告场景运行，都会更新 `docs/index.html` 和 `docs/dashboard.html`：

```bash
python main.py morning
python main.py premarket
python main.py weekly
```

只抓取新闻并刷新页面：

```bash
python main.py fetch
```

只更新行情追踪并刷新页面：

```bash
python main.py track
```

生成后打开：

```text
docs/index.html
docs/dashboard.html
```

## GitHub Actions 自动更新

工作流文件：

```text
.github/workflows/report.yml
```

它会：

1. 安装 Python 依赖。
2. 运行 `python main.py morning`、`premarket` 或 `weekly`。
3. 生成或更新 `docs/index.html` 和 `docs/dashboard.html`。
4. 强制加入 `data/investment_radar.sqlite3`，用于保留历史追踪数据。
5. 把变化提交回仓库。

如果提交步骤提示权限不足，请在仓库中打开：

```text
Settings -> Actions -> General -> Workflow permissions
```

选择 `Read and write permissions`。

GitHub Actions 的 cron 使用 UTC。工作流同时配置了芬兰夏令时和冬令时对应的 UTC 时间，并在程序内用 `TIMEZONE=Europe/Helsinki` 二次判断本地时间，避免重复更新。

芬兰时间对应关系：

- 08:30 Helsinki：
  - 夏令时 UTC+3 -> 05:30 UTC
  - 冬令时 UTC+2 -> 06:30 UTC
- 15:30 Helsinki：
  - 夏令时 UTC+3 -> 12:30 UTC
  - 冬令时 UTC+2 -> 13:30 UTC
- 周日 09:00 Helsinki：
  - 夏令时 UTC+3 -> 06:00 UTC
  - 冬令时 UTC+2 -> 07:00 UTC

## 如何启用 GitHub Pages

1. 把项目推送到 GitHub 仓库。
2. 打开仓库页面。
3. 进入 `Settings -> Pages`。
4. 在 `Build and deployment` 里选择：
   - `Source`: `Deploy from a branch`
   - `Branch`: `main`
   - Folder: `/docs`
5. 保存。

之后网页地址通常是：

```text
https://你的GitHub用户名.github.io/仓库名/
```

如果仓库是用户主页仓库，地址可能是：

```text
https://你的GitHub用户名.github.io/
```

## 如何设置 GitHub Secrets

进入：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

建议设置：

- `OPENAI_API_KEY`

可选邮件相关 Secrets，默认不需要：

- `RESEND_API_KEY`
- `REPORT_EMAILS`
- `SENDER_EMAIL`

静态网页模式不依赖 Resend 或 SMTP。

## 如何手动运行一次更新

在 GitHub 仓库中：

1. 打开 `Actions`。
2. 选择 `Investment Learning Radar Dashboard`。
3. 点击 `Run workflow`。
4. command 填 `dashboard`。
5. 等工作流完成。

完成后查看：

```text
docs/index.html
docs/dashboard.html
```

或打开 GitHub Pages 地址。

## 如何查看网页

本地：

```text
docs/index.html
docs/dashboard.html
```

GitHub Pages：

```text
https://你的GitHub用户名.github.io/仓库名/
```

如果页面没有立即更新，等待 GitHub Pages 重新部署，一般需要几十秒到几分钟。

## 如何确认新闻没有被 AI 编造

本项目通过流程限制降低幻觉风险：

1. `fetch_news.py` 只从配置的 RSS 源读取新闻，不调用 AI。
2. SQLite `news` 表保存 `title`、`source`、`url`、`published_at`、`raw_summary`、`raw_content`。
3. `ai_analyze.py` 只把这些已保存字段发给 AI。
4. AI 提示词明确禁止添加原文没有的信息。
5. `docs/index.html` 和 `docs/dashboard.html` 每条新闻都显示原始链接。
6. 如果新闻没有可靠来源，不会进入数据库和页面。
7. 如果缺少 `OPENAI_API_KEY` 或 AI 返回格式不合法，系统不会补编内容，只会标记为未进行 AI 分析。

人工核查：

```bash
sqlite3 data/investment_radar.sqlite3
```

```sql
.headers on
.mode column
SELECT id, title, source, published_at, url
FROM news
ORDER BY published_at DESC
LIMIT 20;
```

打开 `url`，对照网页里的“已确认事实”。如果原文没有对应内容，应把该条 AI 分析视为不可靠，并调整提示词或提高 `MIN_AI_SCORE`。

## 查看 SQLite 历史记录

最近新闻：

```sql
SELECT id, title, source, score, published_at, url
FROM news
ORDER BY published_at DESC
LIMIT 20;
```

AI 分析：

```sql
SELECT id, title, impact_direction, affected_sectors, observed_etfs, observed_stocks
FROM news
WHERE analyzed_at IS NOT NULL
ORDER BY analyzed_at DESC
LIMIT 20;
```

市场追踪：

```sql
SELECT news_id, symbol, asset_type, event_price, pct_1d, pct_5d, pct_20d
FROM market_snapshots
ORDER BY updated_at DESC
LIMIT 50;
```

## 可选邮件功能

邮件功能保留，但默认关闭。普通命令不会发邮件。

如果确实要测试旧邮件输出，可以配置：

```env
RESEND_API_KEY=你的 Resend API key
REPORT_EMAILS=收件人1,收件人2
SENDER_EMAIL=已验证发件地址
EMAIL_DRY_RUN=false
```

然后显式运行：

```bash
python main.py email-morning
python main.py email-premarket
python main.py email-weekly
```

## 当前新闻源

第一版优先使用 RSS/free feeds：

- Federal Reserve
- European Central Bank
- SEC
- White House
- US Treasury
- IMF
- NATO
- Associated Press
- CNBC
- Financial Times
- Yahoo Finance
- MarketWatch
- CoinDesk
- Cointelegraph

Reuters、World Bank 等来源可在确认可用 RSS 或官方 API 后继续加入。不要用不可靠页面抓取来冒充官方新闻源。

## 测试

```bash
pytest
```

## 结构

```text
investment-learning-radar/
  docs/
    index.html
  src/
    config.py
    fetch_news.py
    score_news.py
    deduplicate.py
    ai_analyze.py
    market_data.py
    web_dashboard.py
    email_sender.py
    database.py
    reports.py
    main.py
  tests/
  .env.example
  requirements.txt
  README.md
  .github/workflows/report.yml
```

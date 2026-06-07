# 中文投资学习雷达（免费版）

这是一个给投资新手使用的学习项目，不做自动交易，不连接 IBKR 下单接口，不提供买卖建议。

目标是每天用中文学习：

```text
新闻 -> 板块 -> ETF -> 个股 -> 市场反应
```

默认输出静态网页：

```text
docs/index.html
docs/dashboard.html
docs/news/news_YYYYMMDD_ID.html
```

## 核心原则

- 禁止编造新闻。
- 禁止生成不存在的事实。
- 每条新闻必须有真实来源和原文链接。
- 新闻内容必须基于 RSS/API 原始来源。
- 如果无法确认内容真实性，不展示。
- 默认不依赖 OpenAI API。
- OpenAI 不存在、无额度、429、API Error 时，自动使用免费规则分析。
- GitHub Actions 不应因为 OpenAI 问题失败。
- 本项目仅用于投资学习。

## 免费规则分析

系统默认使用关键词规则库分析新闻：

- 美联储、FOMC、CPI、通胀、利率、就业报告
- Nvidia、AMD、TSM、ASML、半导体、芯片
- 原油、OPEC、能源
- Bitcoin、Ethereum、crypto、stablecoin
- 关税、制裁、中国、台湾
- 战争、俄罗斯、乌克兰、NATO、中东
- ECB、Europe、eurozone
- AI算力、GPU、数据中心、云计算
- SpaceX、卫星、火箭、商业航天
- 核电、电网、AI电力需求、数据中心供电

首页会变成新闻门户式列表，帮助 3 分钟内看完重点：

- 今日市场概览
- 今日重点观察 ETF/资产和个股
- Top 3 今日最重要新闻
- 全部新闻列表

每条新闻在首页只显示：

- 中文新闻标题
- 中文新闻摘要
- 重要性：高 / 中 / 低
- 可能影响板块
- 观察 ETF/资产
- 观察个股
- 查看全文入口

每条新闻会生成独立详情页：

```text
docs/news/news_YYYYMMDD_ID.html
```

详情页包含：

- 中文标题
- 来源、发布时间、原文链接
- 中文全文翻译区域
- 规则分析
- 重要性、影响方向、板块、ETF、个股
- 折叠的 1天、5天、20天真实涨跌追踪

网页不直接展示英文新闻标题或英文摘要。系统会优先翻译真实原始标题，不再用分类名替代新闻标题。翻译失败时，会明确显示“暂时无法生成中文翻译，请点击原文查看”，并保留原文链接，不编造内容。

## 新闻源覆盖

项目优先使用 RSS/free feeds。当前覆盖：

- Federal Reserve
- European Central Bank
- SEC
- US Treasury
- IMF
- World Bank
- NATO
- Associated Press
- CNBC / CNBC Markets / CNBC Economy
- Financial Times / Financial Times Europe
- Yahoo Finance
- MarketWatch
- Investing.com
- Eurostat
- European Commission
- NASA
- ESA
- SpaceNews
- Space.com
- US Space Force
- CoinDesk
- Cointelegraph

Reuters 公开 RSS 可用性不稳定，因此不会用不可靠第三方源冒充 Reuters 官方源。

## 中文翻译与正文抓取

标题翻译：

- 优先把原始新闻标题翻译成中文。
- 翻译失败时不显示英文标题，显示“暂时无法生成中文标题，请点击原文查看”。

正文获取优先级：

1. RSS content
2. RSS summary
3. 原文页面正文抓取

正文抓取使用 `trafilatura`。免费翻译使用 `deep-translator`。所有抓取和翻译失败都会 graceful fallback，不应导致 GitHub Actions 失败。

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

推荐免费配置：

```env
DATABASE_URL=sqlite:///data/investment_radar.sqlite3
TIMEZONE=Europe/Helsinki
EMAIL_DRY_RUN=true
MAX_REPORT_ITEMS=10
MIN_AI_SCORE=8
REPORT_LOOKBACK_HOURS=24
FETCH_TIMEOUT_SECONDS=20
ENABLE_OPENAI_ANALYSIS=false
```

OpenAI 是可选增强，不配置也能正常运行。

## 本地运行

生成或更新网页：

```bash
python main.py dashboard
```

按场景更新：

```bash
python main.py morning
python main.py premarket
python main.py weekly
```

只抓新闻并刷新网页：

```bash
python main.py fetch
```

只更新行情追踪并刷新网页：

```bash
python main.py track
```

生成后打开：

```text
docs/index.html
```

## GitHub Actions

工作流文件：

```text
.github/workflows/report.yml
```

它会自动：

1. 安装依赖。
2. 抓取真实新闻。
3. 使用免费规则库生成中文分析。
4. 用 yfinance 更新真实行情追踪。
5. 生成 `docs/index.html` 和 `docs/dashboard.html`。
6. 生成每条新闻的 `docs/news/*.html` 详情页。
7. 把网页、详情页和 SQLite 数据库提交回仓库。

默认不需要设置 `OPENAI_API_KEY`。

## 手动运行一次 GitHub Actions

1. 打开仓库的 `Actions` 页面。
2. 选择 `中文投资学习雷达`。
3. 点击 `Run workflow`。
4. command 选择 `dashboard`。
5. 点击运行。

## 启用 GitHub Pages

1. 进入仓库 `Settings -> Pages`。
2. `Source` 选择 `Deploy from a branch`。
3. `Branch` 选择 `main`。
4. Folder 选择 `/docs`。
5. 保存。

网页地址通常是：

```text
https://你的GitHub用户名.github.io/investment-learning-radar/
```

## 查看历史数据

```bash
sqlite3 data/investment_radar.sqlite3
```

最近新闻：

```sql
SELECT id, title_zh, source, score, published_at, url
FROM news
ORDER BY published_at DESC
LIMIT 20;
```

市场追踪：

```sql
SELECT news_id, symbol, asset_type, event_price, pct_1d, pct_5d, pct_20d
FROM market_snapshots
ORDER BY updated_at DESC
LIMIT 50;
```

## 可选 OpenAI 增强

默认关闭。确实需要时再设置：

```env
OPENAI_API_KEY=你的 key
ENABLE_OPENAI_ANALYSIS=true
```

即使 OpenAI 调用失败，系统也会自动回退到规则分析，不应导致 GitHub Actions 失败。

## 风险提示

本页面仅用于投资学习和信息整理，不构成任何投资建议。市场有风险，投资需谨慎。

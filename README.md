# daily-investment-tech-brief V1.1

一个面向中国大陆服务器环境的 OpenClaw Skill：抓取全球/A股财经资讯、主要指数和 A 股行业资金流，交给 OpenClaw 当前配置的模型生成每日投资科技晨报。

## 目录

```text
daily-investment-tech-brief/
├── SKILL.md
├── requirements.txt
├── scripts/
│   └── fetch_market_data.py
└── tests/
    └── test_fetch_market_data.py
```

## 一条命令安装（推荐）

在上海服务器执行：

```bash
rm -rf ~/.openclaw/workspace/skills/daily-investment-tech-brief && git clone --depth 1 https://github.com/kmrzm521/daily-investment-tech-brief.git ~/.openclaw/workspace/skills/daily-investment-tech-brief && python3 -m pip install -r ~/.openclaw/workspace/skills/daily-investment-tech-brief/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 已安装用户升级到 V1.1

```bash
cd ~/.openclaw/workspace/skills/daily-investment-tech-brief && git pull --ff-only && python3 -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

升级后直接做真实数据验收：

```bash
python3 scripts/fetch_market_data.py --pretty > /tmp/brief-data.json && python3 - <<'PY'
import json
p=json.load(open('/tmp/brief-data.json', encoding='utf-8'))
print('collector:', p.get('meta', {}).get('collector'))
print('market sources:', p.get('meta', {}).get('market_sources'))
print('fund flow sources:', p.get('meta', {}).get('fund_flow_sources'))
print('news:', len(p.get('news', [])))
print('global indices:', len(p.get('market', {}).get('global_indices', [])))
print('A indices:', len(p.get('market', {}).get('a_share_indices', [])))
for k in ('今日','5日','10日'):
    x=p.get('fund_flow', {}).get('industry', {}).get(k, {})
    print(k, 'inflow:', len(x.get('top_inflow', [])), 'outflow:', len(x.get('top_outflow', [])))
print('errors:', p.get('errors', []))
PY
```

## V1.1 数据源自动降级

上海服务器若遇到东方财富行情接口 `RemoteDisconnected/ConnectionError`，脚本会自动尝试：

- A股指数：新浪 `stock_zh_index_spot_sina`
- 美股核心指数：新浪 `index_us_stock_sina`（标普500/纳指/道指/纳斯达克100）
- 行业资金流：同花顺 `stock_fund_flow_industry`（即时/5日排行/10日排行）

查看实际用了哪个来源：JSON 的 `meta.market_sources` 和 `meta.fund_flow_sources`。


## V1.2：厄尔尼诺专项投资雷达

晨报固定增加厄尔尼诺研究栏目，覆盖官方 ENSO 状态、全球关键作物产区天气、USDA/FAO 供需与库存、农产品价格、A股产业链、ETF 持仓与估值、最多 8 只候选观察池、买入条件和逻辑失效条件。每周复盘预测与实际数据的差异；没有有效新信号时明确写出，不为凑篇幅重复旧闻。

同时，固定增加每日地缘政治栏目，重点覆盖中美关系/台海、俄乌、中东、欧美与亚太，以及关键航运和能源通道，并分析对市场、黄金、原油、利率和科技供应链的可能影响。

**数据能力说明：** V1.2 的研究规则已写入 SKILL.md；现有 fetch_market_data.py 仍主要采集财经新闻、指数行情和A股行业资金流，尚未自动采集 ENSO、作物产量/库存和国际农产品报价。运行环境若没有可用联网搜索或相应数据源，晨报必须披露“本次未获取/未验证”，不得伪造实时数据。专项数据源接入与真实网络验收应作为后续工程任务。

## 1. 环境要求

- 64 位 Linux
- Python 3.8+（推荐 3.10 / 3.11）
- OpenClaw 已正常运行

## 2. 安装 AKShare

上海服务器建议直接使用国内 PyPI 镜像：

```bash
python3 -m pip install -U akshare -i https://pypi.tuna.tsinghua.edu.cn/simple
```

或者：

```bash
python3 -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 3. 先单独测试数据脚本

在本目录执行：

```bash
python3 scripts/fetch_market_data.py --pretty > /tmp/brief-data.json
```

确认 JSON：

```bash
python3 -m json.tool /tmp/brief-data.json >/dev/null && echo OK
```

## 4. 安装到 OpenClaw

如果按一键安装命令安装，目录已经位于：

```text
~/.openclaw/workspace/skills/daily-investment-tech-brief
```

检查：

```bash
openclaw skills list
openclaw skills info daily-investment-tech-brief
```

如当前会话没有刷新 Skill，开启一个新会话或重启 gateway：

```bash
openclaw gateway restart
```

## 5. 调用

在 OpenClaw 聊天中直接说：

```text
生成今天的每日投资科技晨报
```

也可以显式调用：

```text
/skill daily-investment-tech-brief
```

## 6. 数据源（V1.1）

新闻：

- 东方财富全球财经快讯 `stock_info_global_em`
- 财联社重点电报 `stock_info_global_cls`
- 新浪财经全球快讯 `stock_info_global_sina`

行情：

- 全球指数优先：东方财富 `index_global_spot_em`
- 全球指数降级：新浪 `index_us_stock_sina`
- A股指数优先：东方财富 `stock_zh_index_spot_em`
- A股指数降级：新浪 `stock_zh_index_spot_sina`

行业资金流：

- 优先：东方财富 `stock_sector_fund_flow_rank`
- 降级：同花顺 `stock_fund_flow_industry`

V1.1 不依赖 Google、ChatGPT、Cloudflare 或海外 VPS。

## 7. 注意

- AKShare 的上游网页接口可能变化，因此“代码测试通过”不等于“服务器真实网络一定可用”，上线前必须执行真实数据验收命令。
- 行业“主力资金流”是数据供应商按成交特征统计出的指标，不是交易所官方资金进出统计。
- 本 Skill 不绑定模型，使用 OpenClaw 当前已配置的模型。
- 不单独分析科大讯飞，也不包含无线电/空间天气模块。

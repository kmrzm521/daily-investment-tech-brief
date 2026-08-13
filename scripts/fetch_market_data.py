#!/usr/bin/env python3
"""Fetch evidence for the daily-investment-tech-brief OpenClaw skill.

V1.1 uses AKShare-accessible sources with multi-source fallbacks so it can run on a mainland
China server without Google, ChatGPT, Cloudflare, or an overseas VPS.

The script prints JSON to stdout. Individual source failures are recorded in
`errors` and do not stop the remaining sources from being collected.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    ZoneInfo = None  # type: ignore


NEWS_KEYWORDS = {
    "ai_tech": [
        "AI", "人工智能", "大模型", "模型", "Agent", "智能体", "芯片", "半导体",
        "GPU", "算力", "数据中心", "云计算", "机器人", "存储", "光模块", "CPO",
        "英伟达", "NVIDIA", "微软", "Microsoft", "OpenAI", "谷歌", "Google",
        "Meta", "DeepSeek", "Qwen", "阿里", "腾讯", "华为",
    ],
    "markets_macro": [
        "A股", "上证", "深证", "创业板", "科创", "美股", "纳指", "纳斯达克",
        "标普", "道指", "美联储", "利率", "降息", "加息", "CPI", "PPI", "非农",
        "就业", "通胀", "GDP", "PMI", "人民币", "美元", "国债", "收益率", "黄金",
        "金价", "原油", "油价", "ETF", "央行", "证监会", "政策",
    ],
    "new_energy_auto": [
        "新能源", "汽车", "电动车", "电动汽车", "智能驾驶", "自动驾驶", "电池", "锂电",
        "储能", "光伏", "风电", "充电", "比亚迪", "特斯拉", "Tesla", "宁德时代",
    ],
}

GLOBAL_INDEX_KEYWORDS = [
    "纳斯达克", "纳斯达克综合指数", "NASDAQ", "纳指", "标普500", "S&P 500", "标普",
    "道琼斯", "Dow Jones", "DJIA", "道指", "日经225", "日经",
    "韩国KOSPI", "KOSPI", "恒生指数", "恒生科技", "英国富时", "法国CAC", "德国DAX",
    "美元指数",
]

A_INDEX_KEYWORDS = [
    "上证指数", "深证成指", "创业板指", "沪深300", "科创50", "上证50", "中证500", "中证1000",
]


def shanghai_now() -> datetime:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Shanghai"))
    return datetime.now()


def safe_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if hasattr(value, "item"):
        try:
            return safe_scalar(value.item())
        except Exception:
            pass
    text = str(value)
    return None if text in {"nan", "NaT", "None"} else text


def record_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k): safe_scalar(v) for k, v in row.items()}


def df_records(df: Any) -> List[Dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    return [record_dict(x) for x in df.to_dict(orient="records")]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def infer_news_category(text: str) -> str:
    lowered = text.lower()
    best = ("other", 0)
    for category, keywords in NEWS_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in lowered)
        if score > best[1]:
            best = (category, score)
    return best[0]


def news_score(text: str) -> int:
    lowered = text.lower()
    score = 0
    for keywords in NEWS_KEYWORDS.values():
        for kw in keywords:
            if kw.lower() in lowered:
                score += 1
    high_value = ["美联储", "CPI", "非农", "证监会", "国务院", "央行", "财报", "中标", "发布", "政策"]
    score += 2 * sum(1 for kw in high_value if kw.lower() in lowered)
    return score


def normalize_news_em(df: Any) -> List[Dict[str, Any]]:
    items = []
    for row in df_records(df):
        title = clean_text(row.get("标题"))
        summary = clean_text(row.get("摘要"))
        text = f"{title} {summary}".strip()
        if not text:
            continue
        items.append({
            "source": "东方财富-全球财经快讯",
            "title": title or summary[:80],
            "summary": summary,
            "published_at": clean_text(row.get("发布时间")),
            "url": clean_text(row.get("链接")),
            "category": infer_news_category(text),
            "relevance_score": news_score(text),
        })
    return items


def normalize_news_cls(df: Any) -> List[Dict[str, Any]]:
    items = []
    for row in df_records(df):
        title = clean_text(row.get("标题"))
        summary = clean_text(row.get("内容"))
        text = f"{title} {summary}".strip()
        if not text:
            continue
        published = " ".join(x for x in [clean_text(row.get("发布日期")), clean_text(row.get("发布时间"))] if x)
        items.append({
            "source": "财联社-电报",
            "title": title or summary[:80],
            "summary": summary,
            "published_at": published,
            "url": "",
            "category": infer_news_category(text),
            "relevance_score": news_score(text),
        })
    return items


def normalize_news_sina(df: Any) -> List[Dict[str, Any]]:
    items = []
    for row in df_records(df):
        content = clean_text(row.get("内容"))
        if not content:
            continue
        title = content[:80] + ("…" if len(content) > 80 else "")
        items.append({
            "source": "新浪财经-全球财经快讯",
            "title": title,
            "summary": content,
            "published_at": clean_text(row.get("时间")),
            "url": "",
            "category": infer_news_category(content),
            "relevance_score": news_score(content),
        })
    return items


def dedupe_and_rank_news(items: Sequence[Dict[str, Any]], limit: int = 80) -> List[Dict[str, Any]]:
    seen = set()
    unique: List[Dict[str, Any]] = []
    for item in items:
        key = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", clean_text(item.get("title"))).lower()[:100]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    indexed = list(enumerate(unique))
    indexed.sort(key=lambda pair: (-int(pair[1].get("relevance_score") or 0), pair[0]))
    return [item for _, item in indexed[:limit]]


def select_named_rows(df: Any, keywords: Sequence[str], limit: int = 20) -> List[Dict[str, Any]]:
    rows = df_records(df)
    picked: List[Dict[str, Any]] = []
    seen_names = set()
    for kw in keywords:
        for row in rows:
            name = clean_text(row.get("名称"))
            if kw.lower() in name.lower() and name not in seen_names:
                picked.append(row)
                seen_names.add(name)
                break
    return picked[:limit]


def find_column(columns: Iterable[str], candidates: Sequence[str], suffixes: Sequence[str] = ()) -> Optional[str]:
    cols = [str(c) for c in columns]
    for cand in candidates:
        if cand in cols:
            return cand
    for suffix in suffixes:
        for col in cols:
            if col.endswith(suffix):
                return col
    return None


def normalize_fund_flow(df: Any, period: str, top_n: int = 12) -> Dict[str, Any]:
    if df is None or getattr(df, "empty", True):
        return {"period": period, "top_inflow": [], "top_outflow": []}
    columns = [str(c) for c in df.columns]
    amount_col = find_column(columns, [f"{period}主力净流入-净额", "主力净流入-净额"], suffixes=("主力净流入-净额",))
    ratio_col = find_column(columns, [f"{period}主力净流入-净占比", "主力净流入-净占比"], suffixes=("主力净流入-净占比",))
    change_col = find_column(columns, [f"{period}涨跌幅", "今日涨跌幅", "涨跌幅"], suffixes=("涨跌幅",))
    leader_col = find_column(columns, [f"{period}主力净流入最大股", "今日主力净流入最大股", "主力净流入最大股"], suffixes=("主力净流入最大股",))
    if amount_col is None:
        raise ValueError(f"Cannot find main fund-flow amount column for period={period}; columns={columns}")
    rows: List[Dict[str, Any]] = []
    for raw in df_records(df):
        amount_num = parse_number(raw.get(amount_col))
        if amount_num is None:
            continue
        rows.append({
            "sector": clean_text(raw.get("名称")),
            "change_pct": safe_scalar(raw.get(change_col)) if change_col else None,
            "main_net_inflow": amount_num,
            "main_net_inflow_yi": round(amount_num / 100_000_000, 3),
            "main_net_inflow_ratio_pct": safe_scalar(raw.get(ratio_col)) if ratio_col else None,
            "top_contributor": clean_text(raw.get(leader_col)) if leader_col else "",
        })
    top_in = sorted(rows, key=lambda x: x["main_net_inflow"], reverse=True)[:top_n]
    top_out = sorted(rows, key=lambda x: x["main_net_inflow"])[:top_n]
    return {"period": period, "top_inflow": top_in, "top_outflow": top_out, "sector_count": len(rows)}


def normalize_fund_flow_ths(df: Any, period: str, top_n: int = 12) -> Dict[str, Any]:
    if df is None or getattr(df, "empty", True):
        return {"period": period, "top_inflow": [], "top_outflow": []}
    rows: List[Dict[str, Any]] = []
    for raw in df_records(df):
        sector = clean_text(raw.get("行业"))
        amount_yi = parse_number(raw.get("净额"))
        if not sector or amount_yi is None:
            continue
        change = parse_number(raw.get("行业-涨跌幅"))
        if change is None:
            change = parse_number(raw.get("阶段涨跌幅"))
        rows.append({
            "sector": sector,
            "change_pct": change,
            "main_net_inflow": amount_yi * 100_000_000,
            "main_net_inflow_yi": round(amount_yi, 3),
            "main_net_inflow_ratio_pct": None,
            "top_contributor": clean_text(raw.get("领涨股")),
        })
    top_in = sorted(rows, key=lambda x: x["main_net_inflow"], reverse=True)[:top_n]
    top_out = sorted(rows, key=lambda x: x["main_net_inflow"])[:top_n]
    return {"period": period, "top_inflow": top_in, "top_outflow": top_out, "sector_count": len(rows)}


def fetch_us_indices_sina(ak_module: Any) -> List[Dict[str, Any]]:
    symbols = [(".INX", "标普500"), (".IXIC", "纳斯达克综合指数"), (".DJI", "道琼斯工业平均指数"), (".NDX", "纳斯达克100")]
    rows: List[Dict[str, Any]] = []
    for symbol, name in symbols:
        records = df_records(ak_module.index_us_stock_sina(symbol=symbol))
        if not records:
            continue
        latest = records[-1]
        previous = records[-2] if len(records) >= 2 else None
        close = parse_number(latest.get("close"))
        prev_close = parse_number(previous.get("close")) if previous else None
        change_pct = None
        if close is not None and prev_close not in (None, 0):
            change_pct = round((close / prev_close - 1) * 100, 4)
        rows.append({"代码": symbol, "名称": name, "最新价": close, "涨跌幅": change_pct, "日期": safe_scalar(latest.get("date")), "来源": "新浪财经"})
    return rows


def persistent_flow_hints(fund_flow: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    def names(period: str, direction: str, n: int = 12) -> List[str]:
        return [x.get("sector", "") for x in fund_flow.get(period, {}).get(direction, [])[:n] if x.get("sector")]
    inflow_sets = [set(names(p, "top_inflow")) for p in ("今日", "5日", "10日") if p in fund_flow]
    outflow_sets = [set(names(p, "top_outflow")) for p in ("今日", "5日", "10日") if p in fund_flow]
    return {
        "persistent_inflow_top12_all_periods": sorted(set.intersection(*inflow_sets)) if len(inflow_sets) == 3 else [],
        "persistent_outflow_top12_all_periods": sorted(set.intersection(*outflow_sets)) if len(outflow_sets) == 3 else [],
    }


def fetch_all(ak_module: Any = None, news_limit: int = 80, fund_top_n: int = 12) -> Dict[str, Any]:
    if ak_module is None:
        try:
            import akshare as ak_module  # type: ignore
        except ImportError as exc:
            raise RuntimeError("AKShare is not installed. Run: pip install -U akshare -i https://pypi.tuna.tsinghua.edu.cn/simple") from exc

    errors: List[Dict[str, str]] = []
    all_news: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    news_sources = [
        ("eastmoney_global_news", lambda: normalize_news_em(ak_module.stock_info_global_em())),
        ("cls_telegraph", lambda: normalize_news_cls(ak_module.stock_info_global_cls(symbol="重点"))),
        ("sina_global_news", lambda: normalize_news_sina(ak_module.stock_info_global_sina())),
    ]
    for name, getter in news_sources:
        try:
            items = getter()
            source_counts[name] = len(items)
            all_news.extend(items)
        except Exception as exc:
            source_counts[name] = 0
            errors.append({"source": name, "error": f"{type(exc).__name__}: {exc}"})

    market: Dict[str, Any] = {"global_indices": [], "a_share_indices": []}
    market_sources: Dict[str, str] = {"global_indices": "", "a_share_indices": ""}
    try:
        market["global_indices"] = select_named_rows(ak_module.index_global_spot_em(), GLOBAL_INDEX_KEYWORDS)
        if market["global_indices"]:
            market_sources["global_indices"] = "eastmoney"
    except Exception as exc:
        errors.append({"source": "global_indices_eastmoney", "error": f"{type(exc).__name__}: {exc}"})
    if not market["global_indices"]:
        try:
            market["global_indices"] = fetch_us_indices_sina(ak_module)
            if market["global_indices"]:
                market_sources["global_indices"] = "sina_us_indices"
        except Exception as exc:
            errors.append({"source": "global_indices_sina", "error": f"{type(exc).__name__}: {exc}"})

    try:
        market["a_share_indices"] = select_named_rows(ak_module.stock_zh_index_spot_em(symbol="沪深重要指数"), A_INDEX_KEYWORDS)
        if market["a_share_indices"]:
            market_sources["a_share_indices"] = "eastmoney"
    except Exception as exc:
        errors.append({"source": "a_share_indices_eastmoney", "error": f"{type(exc).__name__}: {exc}"})
    if not market["a_share_indices"]:
        try:
            market["a_share_indices"] = select_named_rows(ak_module.stock_zh_index_spot_sina(), A_INDEX_KEYWORDS)
            if market["a_share_indices"]:
                market_sources["a_share_indices"] = "sina"
        except Exception as exc:
            errors.append({"source": "a_share_indices_sina", "error": f"{type(exc).__name__}: {exc}"})

    fund_flow: Dict[str, Dict[str, Any]] = {}
    fund_flow_sources: Dict[str, str] = {}
    ths_period_map = {"今日": "即时", "5日": "5日排行", "10日": "10日排行"}
    for period in ("今日", "5日", "10日"):
        source_name = f"industry_fund_flow_{period}"
        try:
            df = ak_module.stock_sector_fund_flow_rank(indicator=period, sector_type="行业资金流")
            fund_flow[period] = normalize_fund_flow(df, period, top_n=fund_top_n)
            if fund_flow[period].get("sector_count"):
                fund_flow_sources[period] = "eastmoney"
        except Exception as exc:
            errors.append({"source": f"{source_name}_eastmoney", "error": f"{type(exc).__name__}: {exc}"})
        if not fund_flow.get(period, {}).get("sector_count"):
            try:
                df = ak_module.stock_fund_flow_industry(symbol=ths_period_map[period])
                fund_flow[period] = normalize_fund_flow_ths(df, period, top_n=fund_top_n)
                if fund_flow[period].get("sector_count"):
                    fund_flow_sources[period] = "tonghuashun"
            except Exception as exc:
                fund_flow[period] = {"period": period, "top_inflow": [], "top_outflow": []}
                errors.append({"source": f"{source_name}_tonghuashun", "error": f"{type(exc).__name__}: {exc}"})

    hints = persistent_flow_hints(fund_flow)
    now = shanghai_now()
    payload = {
        "meta": {
            "generated_at": now.isoformat(timespec="seconds"),
            "timezone": "Asia/Shanghai",
            "collector": "daily-investment-tech-brief-v1.1",
            "akshare_version": clean_text(getattr(ak_module, "__version__", "unknown")),
            "news_source_counts": source_counts,
            "news_selected_count": 0,
            "market_sources": market_sources,
            "fund_flow_sources": fund_flow_sources,
            "fund_flow_note": "主力资金流为数据供应商按成交特征统计的指标，不等同于交易所官方披露的真实资金进出。",
        },
        "news": [],
        "market": market,
        "fund_flow": {"industry": fund_flow, "hints": hints},
        "errors": errors,
    }
    payload.update(_with_ranked_news(all_news, news_limit))
    return payload


def _with_ranked_news(all_news: Sequence[Dict[str, Any]], news_limit: int) -> Dict[str, Any]:
    ranked = dedupe_and_rank_news(all_news, limit=news_limit)
    return {"news": ranked, "_news_selected_count": len(ranked)}


def finalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    selected = int(payload.pop("_news_selected_count", len(payload.get("news", []))))
    payload.setdefault("meta", {})["news_selected_count"] = selected
    return payload


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch evidence for the OpenClaw daily investment tech brief.")
    parser.add_argument("--output", help="Optional JSON output file path. Stdout is always written.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    parser.add_argument("--news-limit", type=int, default=80, help="Maximum normalized news items (default: 80).")
    parser.add_argument("--fund-top", type=int, default=12, help="Top inflow/outflow sectors per window (default: 12).")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        payload = finalize_payload(fetch_all(news_limit=max(10, args.news_limit), fund_top_n=max(5, args.fund_top)))
    except Exception as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_market_data.py"
spec = importlib.util.spec_from_file_location("fetch_market_data", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class FakeAK:
    __version__ = "test"

    def stock_info_global_em(self):
        return pd.DataFrame([
            {"标题": "英伟达发布AI芯片新进展", "摘要": "数据中心相关", "发布时间": "2026-08-13 08:00:00", "链接": "https://example.com/a"},
            {"标题": "无关娱乐新闻", "摘要": "娱乐", "发布时间": "2026-08-13 07:00:00", "链接": "https://example.com/b"},
        ])

    def stock_info_global_cls(self, symbol="重点"):
        return pd.DataFrame([
            {"标题": "央行发布重要政策", "内容": "涉及市场流动性", "发布日期": "2026-08-13", "发布时间": "09:00:00"},
        ])

    def stock_info_global_sina(self):
        return pd.DataFrame([
            {"时间": "2026-08-13 09:05:00", "内容": "美联储官员讨论利率路径"},
        ])

    def index_global_spot_em(self):
        return pd.DataFrame([
            {"名称": "纳斯达克", "最新价": 100.0, "涨跌幅": 1.2},
            {"名称": "标普500", "最新价": 200.0, "涨跌幅": 0.8},
            {"名称": "其他指数", "最新价": 1.0, "涨跌幅": 0.0},
        ])

    def stock_zh_index_spot_em(self, symbol="沪深重要指数"):
        return pd.DataFrame([
            {"名称": "上证指数", "最新价": 3900.0, "涨跌幅": 0.5},
            {"名称": "创业板指", "最新价": 2500.0, "涨跌幅": -0.2},
        ])

    def stock_sector_fund_flow_rank(self, indicator="今日", sector_type="行业资金流"):
        amount_col = "主力净流入-净额" if indicator == "今日" else f"{indicator}主力净流入-净额"
        ratio_col = "主力净流入-净占比" if indicator == "今日" else f"{indicator}主力净流入-净占比"
        change_col = "今日涨跌幅" if indicator == "今日" else f"{indicator}涨跌幅"
        leader_col = "主力净流入最大股" if indicator == "今日" else f"{indicator}主力净流入最大股"
        return pd.DataFrame([
            {"名称": "半导体", change_col: 2.0, amount_col: 3_000_000_000, ratio_col: 5.0, leader_col: "A公司"},
            {"名称": "电力设备", change_col: 1.0, amount_col: 2_000_000_000, ratio_col: 3.0, leader_col: "B公司"},
            {"名称": "银行", change_col: -1.0, amount_col: -4_000_000_000, ratio_col: -6.0, leader_col: "C公司"},
            {"名称": "煤炭", change_col: -0.5, amount_col: -2_000_000_000, ratio_col: -2.0, leader_col: "D公司"},
        ])


class EastmoneyMarketBroken(FakeAK):
    def index_global_spot_em(self):
        raise ConnectionError("eastmoney global blocked")

    def stock_zh_index_spot_em(self, symbol="沪深重要指数"):
        raise ConnectionError("eastmoney a-index blocked")

    def stock_sector_fund_flow_rank(self, indicator="今日", sector_type="行业资金流"):
        raise ConnectionError("eastmoney fund-flow blocked")

    def stock_zh_index_spot_sina(self):
        return pd.DataFrame([
            {"代码": "sh000001", "名称": "上证指数", "最新价": 4010.0, "涨跌幅": 0.6},
            {"代码": "sz399006", "名称": "创业板指", "最新价": 2600.0, "涨跌幅": -0.3},
        ])

    def index_us_stock_sina(self, symbol=".INX"):
        base = {".INX": 6000.0, ".IXIC": 20000.0, ".DJI": 45000.0, ".NDX": 22000.0}[symbol]
        return pd.DataFrame([
            {"date": "2026-08-11", "open": base-20, "high": base+10, "low": base-30, "close": base-10, "volume": 100, "amount": 1000},
            {"date": "2026-08-12", "open": base-5, "high": base+20, "low": base-15, "close": base, "volume": 120, "amount": 1200},
        ])

    def stock_fund_flow_industry(self, symbol="即时"):
        if symbol == "即时":
            return pd.DataFrame([
                {"行业": "半导体", "行业指数": 1000.0, "行业-涨跌幅": 2.5, "流入资金": 80.0, "流出资金": 50.0, "净额": 30.0, "领涨股": "A公司"},
                {"行业": "银行", "行业指数": 800.0, "行业-涨跌幅": -1.1, "流入资金": 20.0, "流出资金": 60.0, "净额": -40.0, "领涨股": "B公司"},
            ])
        return pd.DataFrame([
            {"行业": "半导体", "行业指数": 1000.0, "阶段涨跌幅": "6.5%", "流入资金": 100.0, "流出资金": 70.0, "净额": 30.0},
            {"行业": "银行", "行业指数": 800.0, "阶段涨跌幅": "-3.2%", "流入资金": 30.0, "流出资金": 70.0, "净额": -40.0},
        ])


class BrokenCLS(FakeAK):
    def stock_info_global_cls(self, symbol="重点"):
        raise RuntimeError("temporary failure")


class CollectorTests(unittest.TestCase):
    def test_fetch_all_returns_expected_sections(self):
        payload = mod.finalize_payload(mod.fetch_all(FakeAK(), news_limit=20, fund_top_n=5))
        self.assertIn("news", payload)
        self.assertIn("market", payload)
        self.assertIn("fund_flow", payload)
        self.assertGreaterEqual(len(payload["news"]), 3)
        self.assertEqual(payload["market"]["a_share_indices"][0]["名称"], "上证指数")
        self.assertEqual(payload["fund_flow"]["industry"]["今日"]["top_inflow"][0]["sector"], "半导体")
        self.assertEqual(payload["fund_flow"]["industry"]["今日"]["top_outflow"][0]["sector"], "银行")
        self.assertIn("半导体", payload["fund_flow"]["hints"]["persistent_inflow_top12_all_periods"])

    def test_source_failure_degrades_gracefully(self):
        payload = mod.finalize_payload(mod.fetch_all(BrokenCLS(), news_limit=20, fund_top_n=5))
        self.assertGreater(len(payload["news"]), 0)
        self.assertTrue(any(e["source"] == "cls_telegraph" for e in payload["errors"]))

    def test_fund_flow_converts_yuan_to_yi(self):
        df = FakeAK().stock_sector_fund_flow_rank(indicator="今日")
        result = mod.normalize_fund_flow(df, "今日", top_n=5)
        self.assertEqual(result["top_inflow"][0]["main_net_inflow_yi"], 30.0)
        self.assertEqual(result["top_outflow"][0]["main_net_inflow_yi"], -40.0)

    def test_eastmoney_market_failures_fall_back_to_sina_and_ths(self):
        payload = mod.finalize_payload(mod.fetch_all(EastmoneyMarketBroken(), news_limit=20, fund_top_n=5))
        self.assertEqual(payload["market"]["a_share_indices"][0]["名称"], "上证指数")
        self.assertTrue(any(x["名称"] == "标普500" for x in payload["market"]["global_indices"]))
        self.assertEqual(payload["fund_flow"]["industry"]["今日"]["top_inflow"][0]["sector"], "半导体")
        self.assertEqual(payload["fund_flow"]["industry"]["今日"]["top_inflow"][0]["main_net_inflow_yi"], 30.0)
        self.assertEqual(payload["meta"]["market_sources"]["a_share_indices"], "sina")
        self.assertEqual(payload["meta"]["fund_flow_sources"]["今日"], "tonghuashun")

    def test_ths_multi_day_percent_strings_are_normalized(self):
        result = mod.normalize_fund_flow_ths(EastmoneyMarketBroken().stock_fund_flow_industry("5日排行"), "5日", top_n=5)
        self.assertEqual(result["top_inflow"][0]["change_pct"], 6.5)
        self.assertEqual(result["top_outflow"][0]["change_pct"], -3.2)


if __name__ == "__main__":
    unittest.main()

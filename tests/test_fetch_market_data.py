import importlib.util
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


if __name__ == "__main__":
    unittest.main()

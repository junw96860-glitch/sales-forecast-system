# core/cashflow_calculator.py - 基于新结构（修正版：严格按月推进）
from __future__ import annotations

import pandas as pd
from typing import Dict, Any

from core.cash_flow_helper import CashFlowHelper


class CashFlowCalculator:
    """
    现金流计算引擎（Facade）

    设计原则：
    - core 层只做“纯计算”，不直接依赖 data 层
    - 所有“按月推进”的逻辑统一走 CashFlowHelper._add_months（严格按月，避免 timedelta(days=30*i) 漂移）
    - 对外提供稳定接口，便于 pages 逐步迁移
    """

    def calculate_cash_flow(self, df: pd.DataFrame, revenue_column: str = "_final_amount") -> pd.DataFrame:
        """
        基于项目 DataFrame 计算现金流明细。

        返回列（约定）：
        ['项目名称', '业务线', '现金流类型', '金额', '支付日期', '支付月份', '付款比例']
        """
        if df is None or df.empty:
            return pd.DataFrame(
                columns=["项目名称", "业务线", "现金流类型", "金额", "支付日期", "支付月份", "付款比例"]
            )

        cash_flow_df = CashFlowHelper.calculate_dataframe_cash_flow(df, revenue_column=revenue_column)

        # 兜底保证列存在
        if cash_flow_df is None or cash_flow_df.empty:
            return pd.DataFrame(
                columns=["项目名称", "业务线", "现金流类型", "金额", "支付日期", "支付月份", "付款比例"]
            )

        return cash_flow_df

    def get_cashflow_forecast(self, df: pd.DataFrame, months_ahead: int = 12) -> pd.DataFrame:
        """
        基于 DataFrame 生成现金流预测（严格按月）。

        为了兼容旧页面习惯，输出列名沿用：
        ['支付月份', '预测现金流', '累计现金流']
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=["支付月份", "预测现金流", "累计现金流"])

        cash_flow_df = self.calculate_cash_flow(df)
        forecast = CashFlowHelper.forecast_cash_flow(cash_flow_df, months_ahead=months_ahead, fill_zero_months=True)

        if forecast is None or forecast.empty:
            return pd.DataFrame(columns=["支付月份", "预测现金流", "累计现金流"])

        # CashFlowHelper 输出是：['月份','预测现金流','累计现金流']，这里改名为兼容旧口径
        forecast = forecast.rename(columns={"月份": "支付月份"})
        return forecast[["支付月份", "预测现金流", "累计现金流"]]

    def calculate_runway(
        self,
        df: pd.DataFrame,
        initial_cash: float,
        monthly_expense: float,
        months_ahead: int = 24,
    ) -> Dict[str, Any]:
        """
        计算 runway（月数）。

        返回：
        - runway_months: runway 月数
        - min_cash_balance: 最小现金余额
        - cash_flow_summary: 月度汇总表（包含月份、收入、支出、净现金流、累计现金余额）
        """
        if df is None or df.empty:
            return {
                "runway_months": 0,
                "min_cash_balance": float(initial_cash),
                "cash_flow_summary": pd.DataFrame(),
            }

        cash_flow_df = self.calculate_cash_flow(df)

        result = CashFlowHelper.calculate_runway(
            cash_flow_df=cash_flow_df,
            initial_cash=float(initial_cash),
            monthly_expense=float(monthly_expense),
            months_ahead=int(months_ahead),
        )

        # helper 返回 monthly_summary，这里做个兼容映射
        monthly_summary = result.get("monthly_summary", pd.DataFrame())

        return {
            "runway_months": int(result.get("runway_months", 0)),
            "min_cash_balance": float(result.get("min_cash_balance", float(initial_cash))),
            "cash_flow_summary": monthly_summary,
        }

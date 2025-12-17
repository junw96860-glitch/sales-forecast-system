# core/cost_calculator.py
from __future__ import annotations

import pandas as pd
from typing import Dict, Optional


class CostCalculator:
    """
    成本计算引擎（纯计算层）

    设计原则：
    - 只接收 DataFrame，不主动拉数据
    - 不导入 data 层任何模块
    - 统一收入基数：优先 _final_amount（人工纠偏后），否则人工纠偏金额，否则金额
    """

    def __init__(self):
        # 纯计算层：不持有任何数据服务
        pass

    # -----------------------------
    # Public APIs
    # -----------------------------
    def calculate_total_cost(self, df: pd.DataFrame, cost_rate: float = 0.7) -> float:
        """基于 DataFrame 计算总成本（按成本率）"""
        if df is None or df.empty:
            return 0.0
        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        total_income = float(working_df[revenue_col].sum())
        return total_income * float(cost_rate)

    def get_cost_by_category(self, df: pd.DataFrame, cost_structure: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """按成本类型获取成本明细（按收入拆分）"""
        if df is None or df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        total_income = float(working_df[revenue_col].sum())

        if cost_structure is None:
            cost_structure = {
                '直接成本': 0.5,
                '间接成本': 0.15,
                '管理费用': 0.05
            }

        rows = []
        for category, rate in cost_structure.items():
            rate_f = float(rate)
            rows.append({
                '成本类型': category,
                '成本金额': total_income * rate_f,
                '成本比例': f"{rate_f * 100:.1f}%",
                '基于收入': total_income
            })

        return pd.DataFrame(rows)

    def get_cost_forecast(self, df: pd.DataFrame, months_ahead: int = 12, cost_rate: float = 0.7) -> pd.DataFrame:
        """生成成本预测（跟随收入预测的月份口径）"""
        if df is None or df.empty:
            return pd.DataFrame()

        from core.income_calculator import IncomeCalculator

        income_calc = IncomeCalculator()
        income_forecast = income_calc.get_income_forecast(df, months_ahead)

        if income_forecast is None or income_forecast.empty:
            return pd.DataFrame()

        cost_forecast = income_forecast.copy()
        cost_forecast['成本金额'] = pd.to_numeric(cost_forecast['收入金额'], errors='coerce').fillna(0) * float(cost_rate)
        cost_forecast = cost_forecast.rename(columns={
            '收入类型': '成本类型',
            '收入金额': '收入金额（参考）'
        })

        monthly_cost = cost_forecast.groupby('收入月份', as_index=False).agg({
            '成本金额': 'sum',
            '收入金额（参考）': 'sum'
        })

        monthly_cost = monthly_cost.rename(columns={
            '收入月份': '月份',
            '收入金额（参考）': '预计收入'
        }).sort_values('月份')

        return monthly_cost

    def get_cost_by_project(self, df: pd.DataFrame, cost_rate: float = 0.7) -> pd.DataFrame:
        """按项目获取成本明细（按成本率）"""
        if df is None or df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '客户')
        self._ensure_string_column(working_df, '业务线')
        contract_amount = self._ensure_numeric_column(working_df, '金额')
        base_revenue = working_df[revenue_col]

        cost_by_project = pd.DataFrame({
            '项目名称': working_df['客户'],
            '业务线': working_df['业务线'],
            '合同金额': contract_amount,
            '纠偏后收入': base_revenue
        })

        cost_by_project['预计成本'] = cost_by_project['纠偏后收入'] * float(cost_rate)
        cost_by_project['毛利润'] = cost_by_project['纠偏后收入'] - cost_by_project['预计成本']
        cost_by_project['毛利率'] = cost_by_project.apply(
            lambda r: round((r['毛利润'] / r['纠偏后收入'] * 100), 2) if r['纠偏后收入'] else 0,
            axis=1
        )

        return cost_by_project

    def calculate_gross_margin(self, df: pd.DataFrame, cost_rate: float = 0.7) -> Dict[str, float]:
        """毛利分析（按成本率）"""
        if df is None or df.empty:
            return {'总收入': 0.0, '总成本': 0.0, '总毛利': 0.0, '平均毛利率': 0.0}

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        total_income = float(working_df[revenue_col].sum())
        total_cost = total_income * float(cost_rate)
        total_gross = total_income - total_cost
        avg_margin = (total_gross / total_income * 100) if total_income else 0.0

        return {
            '总收入': total_income,
            '总成本': total_cost,
            '总毛利': total_gross,
            '平均毛利率': round(avg_margin, 2)
        }

    def get_cost_breakdown_by_business_line(self, df: pd.DataFrame, cost_structure: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """按业务线获取成本分解（按收入拆分）"""
        if df is None or df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '业务线')
        working_df['__revenue_base'] = working_df[revenue_col]

        if cost_structure is None:
            cost_structure = {
                '直接成本': 0.5,
                '间接成本': 0.15,
                '管理费用': 0.05
            }

        income_by_line = working_df.groupby('业务线', as_index=False)['__revenue_base'].sum()
        income_by_line = income_by_line.rename(columns={'__revenue_base': '收入'})

        rows = []
        for _, r in income_by_line.iterrows():
            revenue = float(r['收入'])
            for cat, rate in cost_structure.items():
                rate_f = float(rate)
                rows.append({
                    '业务线': r['业务线'],
                    '成本类型': cat,
                    '成本金额': revenue * rate_f,
                    '成本比例': f"{rate_f * 100:.1f}%",
                    '收入基数': revenue
                })

        return pd.DataFrame(rows)

    def apply_material_cost(
        self,
        df: pd.DataFrame,
        material_ratios: Dict[str, float],
        revenue_column: Optional[str] = None,
        business_line_column: str = '业务线',
        output_column: str = '物料成本',
        default_ratio: float = 0.30,
    ) -> pd.DataFrame:
        """
        将“物料成本”写回 DataFrame（按业务线比例）。
        - material_ratios: {'光谱设备/服务':0.30, ...}，比例是 0~1（与页面 slider 一致）
        """
        if df is None or df.empty:
            return df.copy() if df is not None else pd.DataFrame()

        working_df = df.copy()
        if revenue_column is None:
            revenue_column = self._ensure_revenue_column(working_df)
        else:
            self._ensure_numeric_column(working_df, revenue_column)

        self._ensure_string_column(working_df, business_line_column)

        def _ratio(line: str) -> float:
            if line in material_ratios:
                return float(material_ratios[line])
            return float(default_ratio)

        working_df[output_column] = working_df.apply(
            lambda row: float(row.get(revenue_column, 0) or 0) * _ratio(str(row.get(business_line_column, ''))),
            axis=1
        )

        # 规范为数值
        working_df[output_column] = pd.to_numeric(working_df[output_column], errors='coerce').fillna(0.0)
        return working_df

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _ensure_revenue_column(self, df: pd.DataFrame) -> str:
        """确定统一的收入列并转换为数值"""
        for column in ['_final_amount', '人工纠偏金额', '金额']:
            if column in df.columns:
                self._ensure_numeric_column(df, column)
                return column
        df['_final_amount'] = 0.0
        return '_final_amount'

    def _ensure_numeric_column(self, df: pd.DataFrame, column: str) -> pd.Series:
        """确保列存在且为数值"""
        if column not in df.columns:
            df[column] = 0.0
        df[column] = pd.to_numeric(df[column], errors='coerce').fillna(0)
        return df[column]

    def _ensure_string_column(self, df: pd.DataFrame, column: str, default: str = '') -> pd.Series:
        """确保列存在且为字符串"""
        if column not in df.columns:
            df[column] = default
        df[column] = df[column].fillna('').astype(str)
        return df[column]

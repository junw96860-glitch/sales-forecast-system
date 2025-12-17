# core/budget_calculator.py - 基于新结构
import pandas as pd
from datetime import datetime
from typing import Dict, List
from core.income_calculator import IncomeCalculator
from core.cost_calculator import CostCalculator


class BudgetCalculator:
    """预算汇总引擎"""

    def __init__(self):
        self.income_calc = IncomeCalculator()
        self.cost_calc = CostCalculator()

    def calculate_budget_summary(self, df: pd.DataFrame, budget_year: int = None) -> pd.DataFrame:
        """基于DataFrame计算预算汇总（统一收入基数）"""
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '业务线')
        ratio_columns = ['首付款比例', '次付款比例', '尾款比例', '质保金比例']
        for col in ratio_columns:
            self._ensure_numeric_column(working_df, col)

        if budget_year is None:
            budget_year = datetime.now().year

        budget_summary = []
        for business_line, business_df in working_df.groupby('业务线'):
            base_revenue = business_df[revenue_col]
            first_payment_total = (base_revenue * (business_df['首付款比例'] / 100)).sum()
            second_payment_total = (base_revenue * (business_df['次付款比例'] / 100)).sum()
            final_payment_total = (base_revenue * (business_df['尾款比例'] / 100)).sum()
            retention_payment_total = (base_revenue * (business_df['质保金比例'] / 100)).sum()
            total_income = base_revenue.sum()

            project_count = len(business_df)
            budget_summary.append({
                '业务线': business_line,
                '总预算收入': total_income,
                '首付款预算': first_payment_total,
                '次付款预算': second_payment_total,
                '尾款预算': final_payment_total,
                '质保金预算': retention_payment_total,
                '项目数量': project_count,
                '平均项目预算': total_income / project_count if project_count else 0
            })

        budget_df = pd.DataFrame(budget_summary)

        if not budget_df.empty:
            total_row = {
                '业务线': '总计',
                '总预算收入': budget_df['总预算收入'].sum(),
                '首付款预算': budget_df['首付款预算'].sum(),
                '次付款预算': budget_df['次付款预算'].sum(),
                '尾款预算': budget_df['尾款预算'].sum(),
                '质保金预算': budget_df['质保金预算'].sum(),
                '项目数量': budget_df['项目数量'].sum(),
                '平均项目预算': budget_df['总预算收入'].sum() / budget_df['项目数量'].sum() if budget_df['项目数量'].sum() else 0
            }
            budget_df = pd.concat([budget_df, pd.DataFrame([total_row])], ignore_index=True)

        return budget_df

    def compare_budget_vs_actual(self, df: pd.DataFrame, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """对比预算与实际（统一收入口径）"""
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '客户')
        self._ensure_string_column(working_df, '业务线')
        contract_amount = self._ensure_numeric_column(working_df, '金额')
        ratio_columns = ['首付款比例', '次付款比例', '尾款比例', '质保金比例']
        for col in ratio_columns:
            self._ensure_numeric_column(working_df, col)

        budget_comparison = []
        for _, project in working_df.iterrows():
            revenue = self._get_project_revenue(project, revenue_col)
            first_budget = revenue * (self._safe_float(project.get('首付款比例')) / 100)
            second_budget = revenue * (self._safe_float(project.get('次付款比例')) / 100)
            final_budget = revenue * (self._safe_float(project.get('尾款比例')) / 100)
            retention_budget = revenue * (self._safe_float(project.get('质保金比例')) / 100)

            delivery_time = project.get('交付时间')
            if isinstance(delivery_time, pd.Timestamp):
                predicted_month = delivery_time.to_period('M').strftime('%Y-%m')
            elif isinstance(delivery_time, datetime):
                predicted_month = delivery_time.strftime('%Y-%m')
            else:
                predicted_month = ''

            budget_comparison.append({
                '客户': project.get('客户', ''),
                '业务线': project.get('业务线', ''),
                '合同金额': contract_amount.loc[project.name] if project.name in contract_amount.index else 0,
                '人工纠偏金额': revenue,
                '首付款预算': first_budget,
                '次付款预算': second_budget,
                '尾款预算': final_budget,
                '质保金预算': retention_budget,
                '总预算收入': revenue,
                '预计交付月份': predicted_month,
                '当前进展': project.get('当前进展', '')
            })

        return pd.DataFrame(budget_comparison)

    def calculate_monthly_budget(self, df: pd.DataFrame, budget_year: int = None) -> pd.DataFrame:
        """计算月度预算（基于付款时间配置）"""
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '业务线')
        self._ensure_string_column(working_df, '客户')

        if budget_year is None:
            budget_year = datetime.now().year

        monthly_budget = []
        stage_configs = [
            ('首付款', '首付款比例', '首付款时间'),
            ('次付款', '次付款比例', '次付款时间'),
            ('尾款', '尾款比例', '尾款时间'),
            ('质保金', '质保金比例', '质保金时间')
        ]

        for _, project in working_df.iterrows():
            revenue = self._get_project_revenue(project)
            for stage_name, ratio_col, time_col in stage_configs:
                ratio = self._safe_float(project.get(ratio_col))
                payment_time = project.get(time_col)

                if ratio > 0 and isinstance(payment_time, (pd.Timestamp, datetime)):
                    payment_amount = revenue * (ratio / 100)
                    month_label = payment_time.strftime('%Y-%m')
                    if payment_amount > 0:
                        monthly_budget.append({
                            '月份': month_label,
                            '业务线': project.get('业务线', ''),
                            '现金流类型': stage_name,
                            '预算金额': payment_amount,
                            '客户': project.get('客户', '')
                        })

        monthly_df = pd.DataFrame(monthly_budget) if monthly_budget else pd.DataFrame(
            columns=['月份', '业务线', '现金流类型', '预算金额', '客户']
        )

        if not monthly_df.empty:
            monthly_summary = monthly_df.groupby(['月份', '业务线']).agg({
                '预算金额': 'sum',
                '客户': 'count'
            }).reset_index()
            monthly_summary = monthly_summary.rename(columns={'客户': '项目数'})
            return monthly_summary

        return monthly_df

    def calculate_payment_schedule(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算付款时间表（基于付款配置）"""
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '客户')
        self._ensure_string_column(working_df, '业务线')
        contract_amount = self._ensure_numeric_column(working_df, '金额')
        ratio_columns = ['首付款比例', '次付款比例', '尾款比例', '质保金比例']
        for col in ratio_columns:
            self._ensure_numeric_column(working_df, col)

        schedule_data = []
        stage_configs = [
            ('首付款', '首付款时间', '首付款比例'),
            ('次付款', '次付款时间', '次付款比例'),
            ('尾款', '尾款时间', '尾款比例'),
            ('质保金', '质保金时间', '质保金比例')
        ]

        for _, project in working_df.iterrows():
            revenue = self._get_project_revenue(project, revenue_col)
            for stage_name, time_col, ratio_col in stage_configs:
                payment_amount = revenue * (self._safe_float(project.get(ratio_col)) / 100)
                payment_time = project.get(time_col)
                if payment_amount > 0 and pd.notna(payment_time):
                    schedule_data.append({
                        '客户': project.get('客户', ''),
                        '业务线': project.get('业务线', ''),
                        '付款阶段': stage_name,
                        '付款金额': payment_amount,
                        '付款时间': payment_time,
                        '付款比例': f"{self._safe_float(project.get(ratio_col)):.1f}%",
                        '合同金额': contract_amount.loc[project.name] if project.name in contract_amount.index else 0,
                        '人工纠偏金额': revenue
                    })

        schedule_df = pd.DataFrame(schedule_data) if schedule_data else pd.DataFrame(
            columns=['客户', '业务线', '付款阶段', '付款金额', '付款时间', '付款比例', '合同金额', '人工纠偏金额']
        )

        return schedule_df

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

    def _get_project_revenue(self, project_row: pd.Series, preferred_column: str = None) -> float:
        """为单条项目记录获取收入基数"""
        revenue = project_row.get(preferred_column) if preferred_column else None
        if revenue in (None, ''):
            revenue = project_row.get('_final_amount', project_row.get('人工纠偏金额', project_row.get('金额', 0)))
        try:
            if revenue in (None, ''):
                return 0.0
            return float(revenue)
        except Exception:
            return 0.0

    def _safe_float(self, value) -> float:
        """安全地转换为浮点数"""
        try:
            if value in (None, ''):
                return 0.0
            return float(value)
        except Exception:
            return 0.0

# core/income_calculator.py - 修复版
# 【修复】移除了对 data.data_service 的导入，符合 "core 不碰数据层" 的铁律
import pandas as pd
from typing import Dict, List
import datetime


class IncomeCalculator:
    """
    收入计算引擎
    
    【架构说明】
    - 这是纯计算层，只接收 DataFrame，不主动拉取数据
    - 不导入 data 层的任何模块
    - 不发送任何 HTTP 请求
    - 不使用 Streamlit
    """

    def __init__(self):
        # 【修复】移除了 self.data_service = SalesDataService()
        pass

    def calculate_total_income(self, df: pd.DataFrame) -> float:
        """基于DataFrame计算总收入（使用统一收入口径）"""
        if df.empty:
            return 0.0

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        return working_df[revenue_col].sum()

    def get_income_by_project(self, df: pd.DataFrame) -> pd.DataFrame:
        """基于DataFrame按项目获取收入明细（使用统一收入口径和四阶段配置）"""
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '客户')
        self._ensure_string_column(working_df, '业务线')
        contract_amount = self._ensure_numeric_column(working_df, '金额')
        stage_rate = self._ensure_numeric_column(working_df, '成单率')
        base_revenue = working_df[revenue_col]

        income_by_project = pd.DataFrame({
            '项目名称': working_df['客户'],
            '业务线': working_df['业务线'],
            '合同金额': contract_amount,
            '纠偏后收入': base_revenue,
            '成单率(%)': stage_rate
        })

        stage_columns = [
            ('首付款收入', '首付款比例'),
            ('次付款收入', '次付款比例'),
            ('尾款收入', '尾款比例'),
            ('质保金收入', '质保金比例')
        ]

        for label, ratio_col in stage_columns:
            ratio_series = self._ensure_numeric_column(working_df, ratio_col)
            income_by_project[label] = base_revenue * (ratio_series / 100)

        income_by_project['收入差异'] = income_by_project['纠偏后收入'] - (
            income_by_project['合同金额'] * (income_by_project['成单率(%)'] / 100)
        )

        return income_by_project

    def get_income_forecast(self, df: pd.DataFrame, months_ahead: int = 12) -> pd.DataFrame:
        """基于DataFrame生成收入预测（使用付款时间配置）"""
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '客户')
        self._ensure_string_column(working_df, '业务线')

        forecast_data = []

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

                if ratio > 0 and pd.notna(payment_time):
                    payment_amount = revenue * (ratio / 100)
                    if payment_amount > 0:
                        forecast_data.append({
                            '项目名称': project.get('客户', ''),
                            '业务线': project.get('业务线', ''),
                            '收入类型': stage_name,
                            '收入金额': payment_amount,
                            '收入时间': payment_time,
                            '收入月份': payment_time.strftime('%Y-%m') if isinstance(payment_time, (datetime.date, datetime.datetime, pd.Timestamp)) else '',
                            '付款比例': f"{ratio:.1f}%"
                        })

        forecast_df = pd.DataFrame(forecast_data) if forecast_data else pd.DataFrame(
            columns=['项目名称', '业务线', '收入类型', '收入金额', '收入时间', '收入月份', '付款比例']
        )

        if not forecast_df.empty:
            current_month = datetime.date.today().replace(day=1)
            end_month = current_month
            for _ in range(months_ahead):
                end_month = end_month.replace(day=1) + datetime.timedelta(days=32)
                end_month = end_month.replace(day=1)

            forecast_df['收入月份_date'] = pd.to_datetime(forecast_df['收入月份'] + '-01', errors='coerce')
            forecast_df = forecast_df[
                (forecast_df['收入月份_date'] >= pd.to_datetime(current_month)) &
                (forecast_df['收入月份_date'] <= pd.to_datetime(end_month))
            ].drop('收入月份_date', axis=1)

        return forecast_df

    def get_income_by_stage(self, df: pd.DataFrame) -> pd.DataFrame:
        """获取各阶段收入汇总"""
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        base_revenue = working_df[revenue_col]

        stage_ratios = {
            '首付款': self._ensure_numeric_column(working_df, '首付款比例'),
            '次付款': self._ensure_numeric_column(working_df, '次付款比例'),
            '尾款': self._ensure_numeric_column(working_df, '尾款比例'),
            '质保金': self._ensure_numeric_column(working_df, '质保金比例')
        }

        stages_data = {
            '收入类型': [],
            '总收入': [],
            '项目数量': []
        }

        for stage_name, ratio_series in stage_ratios.items():
            stage_income = (base_revenue * (ratio_series / 100)).sum()
            stages_data['收入类型'].append(stage_name)
            stages_data['总收入'].append(stage_income)
            stages_data['项目数量'].append(int((ratio_series > 0).sum()))

        return pd.DataFrame(stages_data)

    def get_income_by_business_line(self, df: pd.DataFrame) -> pd.DataFrame:
        """按业务线获取收入汇总"""
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_col = self._ensure_revenue_column(working_df)
        self._ensure_string_column(working_df, '业务线')
        self._ensure_string_column(working_df, '客户')
        contract_amount = self._ensure_numeric_column(working_df, '金额')
        working_df['__revenue_base'] = working_df[revenue_col]
        working_df['金额'] = contract_amount

        income_by_line = working_df.groupby('业务线').agg({
            '__revenue_base': 'sum',
            '金额': 'sum',
            '客户': 'count'
        }).reset_index()

        income_by_line = income_by_line.rename(columns={
            '__revenue_base': '纠偏后收入',
            '金额': '合同总额',
            '客户': '项目数量'
        })

        income_by_line['收入差异'] = income_by_line['纠偏后收入'] - income_by_line['合同总额']
        income_by_line['收入差异率'] = income_by_line.apply(
            lambda row: round((row['收入差异'] / row['合同总额'] * 100), 2) if row['合同总额'] else 0,
            axis=1
        )

        return income_by_line

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

    def _get_project_revenue(self, project_row: pd.Series) -> float:
        """获取单条项目的收入基数"""
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
# core/cash_flow_helper.py - 现金流计算辅助类
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import numpy as np
import calendar


class CashFlowHelper:
    """现金流计算辅助类

    提供统一的现金流计算方法，避免在多个页面重复实现类似逻辑
    """

    @staticmethod
    def calculate_single_project_cash_flow(
        project_row: pd.Series,
        revenue_column: str = "_final_amount"
    ) -> pd.DataFrame:
        """计算单个项目的现金流

        Args:
            project_row: 单个项目的Series数据
            revenue_column: 收入金额列名，默认为"_final_amount"

        Returns:
            包含现金流信息的DataFrame
        """
        if project_row.empty:
            return pd.DataFrame()

        cash_flow_items = []
        revenue = CashFlowHelper._get_project_revenue(project_row, revenue_column)

        stage_configs = [
            ("首付款", "首付款比例", "首付款时间", "start"),
            ("次付款", "次付款比例", "次付款时间", "delivery"),
            ("尾款", "尾款比例", "尾款时间", "delivery_plus_one"),
            ("质保金", "质保金比例", "质保金时间", "delivery_plus_one")
        ]

        for stage_name, ratio_col, time_col, fallback in stage_configs:
            ratio = CashFlowHelper._safe_float(project_row.get(ratio_col, 0))
            payment_date = CashFlowHelper._resolve_payment_date(project_row, time_col, fallback)

            if ratio > 0 and payment_date and pd.notna(payment_date):
                payment_amount = revenue * (ratio / 100)
                if payment_amount > 0:
                    cash_flow_items.append({
                        "项目名称": project_row.get("客户", ""),
                        "业务线": project_row.get("业务线", ""),
                        "现金流类型": stage_name,
                        "金额": payment_amount,
                        "支付日期": payment_date,
                        "支付月份": CashFlowHelper._format_to_month(payment_date),
                        "付款比例": f"{ratio:.1f}%"
                    })

        return pd.DataFrame(cash_flow_items)

    @staticmethod
    def calculate_dataframe_cash_flow(
        df: pd.DataFrame,
        revenue_column: str = "_final_amount"
    ) -> pd.DataFrame:
        """计算整个DataFrame的现金流

        Args:
            df: 包含项目数据的DataFrame
            revenue_column: 收入金额列名，默认为"_final_amount"

        Returns:
            包含所有项目现金流信息的DataFrame
        """
        if df.empty:
            return pd.DataFrame()

        working_df = df.copy()
        revenue_column = CashFlowHelper._ensure_revenue_column(working_df, revenue_column)
        all_cash_flows = []

        # 遍历每个项目
        for _, project in working_df.iterrows():
            # 跳过无效数据
            if CashFlowHelper._get_project_revenue(project, revenue_column) == 0:
                continue

            # 计算单个项目的现金流
            project_cash_flow = CashFlowHelper.calculate_single_project_cash_flow(
                project, revenue_column)

            if not project_cash_flow.empty:
                all_cash_flows.append(project_cash_flow)

        # 合并所有现金流
        if all_cash_flows:
            return pd.concat(all_cash_flows, ignore_index=True)
        else:
            return pd.DataFrame(
                columns=[
                    "项目名称", "业务线", "现金流类型", "金额", "支付日期", "支付月份",
                    "付款比例"
                ])

    @staticmethod
    def calculate_monthly_summary(cash_flow_df: pd.DataFrame) -> pd.DataFrame:
        """按月汇总现金流（统一输出列：月份）

        Returns:
            DataFrame: 至少包含 ['月份','月度现金流','项目数量']，并保留兼容列 '支付月份'
        """
        if cash_flow_df.empty:
            return pd.DataFrame(columns=["月份", "月度现金流", "项目数量", "支付月份"])

        working_df = cash_flow_df.copy()

        # 确保存在支付月份（明细现金流通常用支付月份）
        if "支付月份" not in working_df.columns or working_df["支付月份"].isna().all():
            working_df["支付月份"] = pd.to_datetime(
                working_df.get("支付日期", None), errors="coerce"
            ).dt.to_period("M").astype(str)

        monthly_summary = (
            working_df.dropna(subset=["支付月份"])
            .groupby("支付月份")
            .agg({"金额": "sum", "项目名称": "nunique"})
            .reset_index()
        )

        # 统一列名：预测/汇总统一用“月份”
        monthly_summary = monthly_summary.rename(
            columns={
                "支付月份": "月份",
                "项目名称": "项目数量",
                "金额": "月度现金流",
            }
        )

        # 兼容：保留旧列名，避免外部调用依赖“支付月份”
        monthly_summary["支付月份"] = monthly_summary["月份"]

        # 按月份排序
        monthly_summary = monthly_summary.sort_values("月份")

        return monthly_summary[["月份", "月度现金流", "项目数量", "支付月份"]]


    @staticmethod
    def calculate_business_line_summary(cash_flow_df: pd.DataFrame) -> pd.DataFrame:
        """按业务线汇总现金流

        Args:
            cash_flow_df: 现金流DataFrame

        Returns:
            按业务线汇总的DataFrame
        """
        if cash_flow_df.empty:
            return pd.DataFrame(columns=["业务线", "现金流", "项目数量"])

        # 按业务线汇总
        summary = cash_flow_df.groupby("业务线").agg({
            "金额": "sum",
            "项目名称": "nunique"
        }).reset_index()

        summary = summary.rename(columns={
            "项目名称": "项目数量",
            "金额": "现金流"
        })

        # 按现金流排序
        summary = summary.sort_values("现金流", ascending=False)

        return summary

    @staticmethod
    def calculate_stage_summary(cash_flow_df: pd.DataFrame) -> pd.DataFrame:
        """按付款阶段汇总现金流

        Args:
            cash_flow_df: 现金流DataFrame

        Returns:
            按付款阶段汇总的DataFrame
        """
        if cash_flow_df.empty:
            return pd.DataFrame(columns=["付款阶段", "金额", "项目数量"])

        # 按付款阶段汇总
        summary = cash_flow_df.groupby("现金流类型").agg({
            "金额": "sum",
            "项目名称": "nunique"
        }).reset_index()

        summary = summary.rename(columns={
            "现金流类型": "付款阶段",
            "项目名称": "项目数量"
        })

        return summary

    @staticmethod
    def merge_with_original_df(
        original_df: pd.DataFrame,
        cash_flow_df: pd.DataFrame,
        stage_income_suffix: str = "现金"
    ) -> pd.DataFrame:
        """合并现金流原始表

        Args:
            original_df: 原始项目数据
            cash_flow_df: 现金流数据
            stage_income_suffix: 添加到收入列名的后缀

        Returns:
            合并后的DataFrame
        """
        if original_df.empty or cash_flow_df.empty:
            return original_df.copy()

        merged_df = original_df.copy()

        # 为每个付款阶段添加计算列
        stages = [("首付款", "首付款比例"), ("次付款", "次付款比例"),
                  ("尾款", "尾款比例"), ("质保金", "质保金比例")]

        for stage_name, ratio_col in stages:
            stage_cash = cash_flow_df[cash_flow_df["现金流类型"] == stage_name]
            if not stage_cash.empty:
                # 按项目和业务线汇总
                stage_summary = stage_cash.groupby(
                    ["项目名称", "业务线"])["金额"].sum()

                # 添加合并列
                income_col = f"{stage_name}{stage_income_suffix}"
                merged_df[income_col] = merged_df.apply(
                    lambda row: stage_summary.get((row.get("客户", ""),
                                                   row.get("业务线", "")), 0),
                    axis=1)

        return merged_df

    @staticmethod
    def get_project_payment_schedule(project_row: pd.Series) -> pd.DataFrame:
        """获取项目的详细付款计划

        Args:
            project_row: 单个项目的数据

        Returns:
            付款计划DataFrame
        """
        if project_row.empty:
            return pd.DataFrame()

        payments = []
        revenue = CashFlowHelper._get_project_revenue(project_row)
        customer = project_row.get("客户", "")
        business_line = project_row.get("业务线", "")

        stage_configs = [
            ("首付款", "首付款比例", "首付款时间", "start"),
            ("次付款", "次付款比例", "次付款时间", "delivery"),
            ("尾款", "尾款比例", "尾款时间", "delivery_plus_one"),
            ("质保金", "质保金比例", "质保金时间", "delivery_plus_one")
        ]

        for stage, ratio_col, date_col, fallback in stage_configs:
            ratio = project_row.get(ratio_col, 0)
            payment_date = CashFlowHelper._resolve_payment_date(project_row, date_col, fallback)

            if ratio > 0:
                amount = revenue * (ratio / 100)
                payments.append({
                    "客户": customer,
                    "业务线": business_line,
                    "付款阶段": stage,
                    "付款比例": ratio,
                    "付款金额": amount,
                    "付款时间": payment_date,
                    "合同金额": project_row.get("金额", 0),
                    "预期收入": revenue
                })

        schedule_df = pd.DataFrame(payments)

        # 按日期排序
        if not schedule_df.empty and "付款时间" in schedule_df.columns:
            schedule_df = schedule_df.sort_values("付款时间",
                                                  na_position='last').reset_index(
                                                      drop=True)

        return schedule_df

    @staticmethod
    def forecast_cash_flow(
        cash_flow_df: pd.DataFrame,
        months_ahead: int = 12,
        fill_zero_months: bool = True
    ) -> pd.DataFrame:
        """预测未来现金流

        Args:
            cash_flow_df: 现有现金流数据
            months_ahead: 预测月份数
            fill_zero_months: 是否填充没有现金流的月份

        Returns:
            预测现金流DataFrame
        """
        if cash_flow_df.empty:
            return pd.DataFrame(
                columns=["月份", "预测现金流", "累计现金流"])

        # 从当前月份开始生成未来月份
        from datetime import datetime
        current_month = datetime.now().replace(day=1)

        future_months = []
        for i in range(months_ahead):
            month = CashFlowHelper._add_months(current_month, i)
            future_months.append(month.strftime('%Y-%m'))

        # 获取现有现金流数据
        monthly_cash = CashFlowHelper.calculate_monthly_summary(cash_flow_df)
        if "月份" not in monthly_cash.columns and "支付月份" in monthly_cash.columns:
            monthly_cash = monthly_cash.rename(columns={"支付月份": "月份"})

        # 创建完整的时间序列
        all_months = pd.DataFrame({"月份": future_months})

        # 合并数据
        if not monthly_cash.empty:
            all_months = all_months.merge(monthly_cash,
                                          on="月份",
                                          how="left",
                                          suffixes=("", "_预计"))
            all_months["预测现金流"] = all_months["月度现金流"].fillna(0)
        else:
            all_months["预测现金流"] = 0

        # 计算累计现金流
        all_months["累计现金流"] = all_months["预测现金流"].cumsum()

        # 如果设置了，删除现金流为0的月份
        if not fill_zero_months:
            all_months = all_months[all_months["预测现金流"] != 0]

        return all_months[["月份", "预测现金流", "累计现金流"]]

    @staticmethod
    def _ensure_revenue_column(df: pd.DataFrame, preferred_column: Optional[str] = None) -> str:
        """确定可用的收入列并进行数值化"""
        candidates: List[str] = []
        if preferred_column:
            candidates.append(preferred_column)
        candidates.extend(["_final_amount", "人工纠偏金额", "金额"])

        for column in candidates:
            if column and column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
                return column

        df["_final_amount"] = 0.0
        return "_final_amount"

    @staticmethod
    def _get_project_revenue(project_row: pd.Series, preferred_column: Optional[str] = None) -> float:
        """对单条记录获取收入基数"""
        candidates: List[str] = []
        if preferred_column:
            candidates.append(preferred_column)
        candidates.extend(["_final_amount", "人工纠偏金额", "金额"])

        for column in candidates:
            if column and column in project_row:
                value = project_row.get(column)
                if value not in (None, ""):
                    try:
                        return float(value)
                    except Exception:
                        continue
        return 0.0

    @staticmethod
    def _safe_float(value) -> float:
        """安全地转换为浮点数"""
        try:
            if value in (None, ""):
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _format_to_month(date_value) -> str:
        """格式化日期为月份字符串"""
        if pd.isna(date_value):
            return ""

        if isinstance(date_value, (pd.Timestamp, datetime)):
            return date_value.strftime('%Y-%m')

        if isinstance(date_value, str):
            if '-' in date_value and len(date_value) >= 7:
                return date_value[:7]  # 取年月部分

        return str(date_value)[:7] if str(date_value) else ""

    @staticmethod
    def _resolve_payment_date(project_row: pd.Series, explicit_col: str, fallback: str):
        """优先使用明细字段，否则根据规则推导付款时间"""
        explicit_value = project_row.get(explicit_col)
        if pd.notna(explicit_value):
            return explicit_value

        start_time = project_row.get("开始时间")
        delivery_time = project_row.get("交付时间")

        if fallback == "start":
            return start_time
        if fallback == "delivery":
            return delivery_time
        if fallback == "delivery_plus_one" and pd.notna(delivery_time):
            return delivery_time + pd.DateOffset(months=1)

        return explicit_value

    @staticmethod
    def _add_months(date: datetime, months: int) -> datetime:
        """添加月份"""
        month = date.month - 1 + months
        year = date.year + month // 12
        month = month % 12 + 1
        day = min(date.day, calendar.monthrange(year, month)[1])
        return date.replace(year=year, month=month, day=day)

    @staticmethod
    def calculate_runway(
        cash_flow_df: pd.DataFrame,
        initial_cash: float,
        monthly_expense: float,
        months_ahead: int = 24
    ) -> Dict[str, Any]:
        """计算现金余额Runway

        Args:
            cash_flow_df: 现金流数据
            initial_cash: 初始现金余额
            monthly_expense: 月度支出
            months_ahead: 预测月份数

        Returns:
            包含Runway分析结果的字典
        """
        if cash_flow_df.empty:
            return {
                "runway_months": 0,
                "min_cash_balance": initial_cash,
                "monthly_summary": pd.DataFrame()
            }

        # 获取月度现金流预测
        forecast_df = CashFlowHelper.forecast_cash_flow(cash_flow_df, months_ahead)

        if forecast_df.empty:
            return {
                "runway_months": 0,
                "min_cash_balance": initial_cash,
                "monthly_summary": pd.DataFrame()
            }

        # 计算现金流和余额
        monthly_summary = pd.DataFrame({
            "月份": forecast_df["月份"],
            "收入": forecast_df["预测现金流"],
            "支出": monthly_expense,
            "净现金流": forecast_df["预测现金流"] - monthly_expense
        })

        # 计算累计现金余额
        monthly_summary["累计现金余额"] = initial_cash
        for i in range(len(monthly_summary)):
            if i == 0:
                monthly_summary.loc[i, "累计现金余额"] = initial_cash + monthly_summary.loc[i, "净现金流"]
            else:
                monthly_summary.loc[i, "累计现金余额"] = (
                    monthly_summary.loc[i - 1, "累计现金余额"] +
                    monthly_summary.loc[i, "净现金流"]
                )

        # 计算Runway
        runway_months = 0
        for i, row in monthly_summary.iterrows():
            if row["累计现金余额"] <= 0:
                break
            runway_months += 1

        return {
            "runway_months": runway_months,
            "min_cash_balance": monthly_summary["累计现金余额"].min(),
            "monthly_summary": monthly_summary
        }

# core/unified_cashflow_service.py
"""
统一现金流服务 - V1

整合收入预测页面和现金流分析页面的逻辑，确保数据一致性。

核心逻辑：
1. 优先使用飞书表格中保存的自定义付款节奏（PaymentSchedule）
2. 如果没有自定义配置，则使用默认模板
3. 根据付款节奏计算每笔付款的日期和金额
"""

import pandas as pd
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dateutil.relativedelta import relativedelta

# 导入付款模板配置
try:
    from payment_templates import (
        PAYMENT_TEMPLATES,
        get_template,
        get_default_template_for_business,
        get_all_template_names,
    )
except ImportError:
    # 如果配置文件不存在，使用内置默认值
    PAYMENT_TEMPLATES = {
        "标准三笔(5-4-1)": [
            {"name": "首付款", "ratio": 0.5, "offset_months": -1, "base": "开始时间"},
            {"name": "到货验收款", "ratio": 0.4, "offset_months": 0, "base": "交付时间"},
            {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
        ],
    }
    get_template = lambda name: PAYMENT_TEMPLATES.get(name, list(PAYMENT_TEMPLATES.values())[0])
    get_default_template_for_business = lambda _: "标准三笔(5-4-1)"
    get_all_template_names = lambda: list(PAYMENT_TEMPLATES.keys())


class UnifiedCashFlowService:
    """统一现金流服务"""
    
    def __init__(self, feishu_client=None, payment_schedule_table_id: str = None):
        """
        初始化服务
        
        Args:
            feishu_client: 飞书客户端（可选，用于读取自定义付款节奏）
            payment_schedule_table_id: 付款节奏表ID
        """
        self.feishu_client = feishu_client
        self.payment_schedule_table_id = payment_schedule_table_id
        self._payment_schedule_cache = None
    
    def load_payment_schedules(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        加载所有项目的付款节奏配置
        
        Returns:
            DataFrame包含: record_id, template_name, payment_stages(JSON)
        """
        if self._payment_schedule_cache is not None and not force_refresh:
            return self._payment_schedule_cache
        
        if not self.feishu_client or not self.payment_schedule_table_id:
            self._payment_schedule_cache = pd.DataFrame()
            return self._payment_schedule_cache
        
        try:
            records = self.feishu_client.get_records(self.payment_schedule_table_id)
            if records is None:
                records = []
        except Exception as e:
            print(f"加载付款节奏表失败: {e}")
            self._payment_schedule_cache = pd.DataFrame()
            return self._payment_schedule_cache
        
        if not records:
            self._payment_schedule_cache = pd.DataFrame()
            return self._payment_schedule_cache
        
        rows = []
        for item in records:
            if item is None:
                continue
            fields = item.get("fields", {}) or {}
            rows.append({
                "_ps_record_id": item.get("record_id"),
                "record_id": fields.get("record_id", ""),
                "template_name": fields.get("template_name", ""),
                "payment_stages": fields.get("payment_stages", "[]"),
            })
        
        self._payment_schedule_cache = pd.DataFrame(rows) if rows else pd.DataFrame()
        return self._payment_schedule_cache
    
    def get_project_payment_stages(self, record_id: str) -> Tuple[str, List[Dict]]:
        """
        获取单个项目的付款节奏
        
        Args:
            record_id: 项目的record_id
        
        Returns:
            (template_name, stages_list) 元组
        """
        df = self.load_payment_schedules()
        if df.empty or "record_id" not in df.columns:
            return "", []
        
        hit = df[df["record_id"] == record_id]
        if hit.empty:
            return "", []
        
        row = hit.iloc[0]
        template_name = row.get("template_name", "")
        stages_json = row.get("payment_stages", "[]")
        
        try:
            stages = json.loads(stages_json) if stages_json else []
        except json.JSONDecodeError:
            stages = []
        
        return template_name, stages
    
    def apply_template_with_dates(
        self,
        template_stages: List[Dict],
        start_date,
        delivery_date,
    ) -> List[Dict]:
        """
        应用模板并计算具体日期
        
        Args:
            template_stages: 模板定义的付款节点
            start_date: 项目开始时间
            delivery_date: 项目交付时间
        
        Returns:
            包含具体日期的付款节点列表
        """
        result = []
        for stage in template_stages:
            base = stage.get("base", "交付时间")
            base_date = start_date if base == "开始时间" else delivery_date
            offset = stage.get("offset_months", 0)
            
            pay_date = None
            pay_date_ts = None
            if base_date and pd.notna(base_date):
                try:
                    base_dt = pd.to_datetime(base_date, errors="coerce")
                    if pd.notna(base_dt):
                        pay_date = base_dt + relativedelta(months=offset)
                        pay_date_ts = int(pay_date.timestamp() * 1000)
                except Exception:
                    pass
            
            result.append({
                "name": stage.get("name", ""),
                "ratio": stage.get("ratio", 0),
                "date": pay_date_ts,
                "date_obj": pay_date,
            })
        return result
    
    def calculate_project_cash_flow(
        self,
        project_row: pd.Series,
        revenue_column: str = "_final_amount"
    ) -> List[Dict]:
        """
        计算单个项目的现金流
        
        Args:
            project_row: 项目数据行
            revenue_column: 收入列名
        
        Returns:
            现金流条目列表
        """
        record_id = project_row.get("record_id", "")
        revenue = self._get_revenue(project_row, revenue_column)
        
        if revenue <= 0:
            return []
        
        # 获取项目的付款节奏
        template_name, saved_stages = self.get_project_payment_stages(record_id)
        
        # 获取日期
        start_date = project_row.get("开始时间")
        delivery_date = project_row.get("交付时间") or project_row.get("预计截止时间")
        business_line = project_row.get("业务线", "")
        customer = project_row.get("客户", "")
        
        # 如果有保存的付款节奏，使用它
        if saved_stages:
            stages = saved_stages
        else:
            # 否则使用默认模板
            default_template_name = get_default_template_for_business(business_line)
            template_def = get_template(default_template_name)
            stages = self.apply_template_with_dates(template_def, start_date, delivery_date)
        
        # 生成现金流条目
        cash_flow_items = []
        for stage in stages:
            ratio = stage.get("ratio", 0)
            if ratio <= 0:
                continue
            
            # 获取付款日期
            pay_date = None
            if "date_obj" in stage and stage["date_obj"]:
                pay_date = stage["date_obj"]
            elif "date" in stage and stage["date"]:
                try:
                    pay_date = pd.to_datetime(stage["date"], unit="ms")
                except:
                    pass
            
            # 如果没有日期，尝试根据模板计算
            if pay_date is None and not saved_stages:
                # 这种情况不应该发生，因为apply_template_with_dates已经计算了日期
                continue
            
            payment_amount = revenue * ratio
            payment_month = pay_date.strftime('%Y-%m') if pay_date and pd.notna(pay_date) else ""
            
            cash_flow_items.append({
                "项目名称": customer,
                "业务线": business_line,
                "现金流类型": stage.get("name", ""),
                "金额": payment_amount,
                "支付日期": pay_date,
                "支付月份": payment_month,
                "付款比例": f"{ratio * 100:.1f}%",
                "record_id": record_id,
            })
        
        return cash_flow_items
    
    def calculate_all_cash_flows(
        self,
        df: pd.DataFrame,
        revenue_column: str = "_final_amount"
    ) -> pd.DataFrame:
        """
        计算所有项目的现金流
        
        Args:
            df: 项目数据DataFrame
            revenue_column: 收入列名
        
        Returns:
            包含所有现金流的DataFrame
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=[
                "项目名称", "业务线", "现金流类型", "金额", 
                "支付日期", "支付月份", "付款比例", "record_id"
            ])
        
        all_cash_flows = []
        
        for _, row in df.iterrows():
            project_cash_flows = self.calculate_project_cash_flow(row, revenue_column)
            all_cash_flows.extend(project_cash_flows)
        
        if all_cash_flows:
            return pd.DataFrame(all_cash_flows)
        else:
            return pd.DataFrame(columns=[
                "项目名称", "业务线", "现金流类型", "金额", 
                "支付日期", "支付月份", "付款比例", "record_id"
            ])
    
    def get_monthly_income_summary(
        self,
        df: pd.DataFrame,
        start_date: datetime.date,
        end_date: datetime.date,
        revenue_column: str = "_final_amount"
    ) -> pd.DataFrame:
        """
        获取月度收入汇总
        
        Args:
            df: 项目数据DataFrame
            start_date: 开始日期
            end_date: 结束日期
            revenue_column: 收入列名
        
        Returns:
            月度收入汇总DataFrame
        """
        cash_flow_df = self.calculate_all_cash_flows(df, revenue_column)
        
        if cash_flow_df.empty:
            return pd.DataFrame(columns=["月份", "收入"])
        
        # 过滤日期范围
        cash_flow_df["支付日期"] = pd.to_datetime(cash_flow_df["支付日期"], errors="coerce")
        
        # 生成月份列表
        months = []
        current = start_date.replace(day=1)
        end = end_date.replace(day=1)
        while current <= end:
            months.append(current.strftime('%Y-%m'))
            current = current + relativedelta(months=1)
        
        # 按月汇总
        monthly_summary = pd.DataFrame({"月份": months})
        
        if not cash_flow_df.empty and "支付月份" in cash_flow_df.columns:
            monthly_income = cash_flow_df.groupby("支付月份")["金额"].sum().reset_index()
            monthly_income = monthly_income.rename(columns={"支付月份": "月份", "金额": "收入"})
            monthly_summary = monthly_summary.merge(monthly_income, on="月份", how="left")
        
        monthly_summary["收入"] = monthly_summary.get("收入", 0).fillna(0)
        
        return monthly_summary
    
    def _get_revenue(self, project_row: pd.Series, preferred_column: str = None) -> float:
        """获取项目收入"""
        candidates = []
        if preferred_column:
            candidates.append(preferred_column)
        candidates.extend(["_final_amount", "人工纠偏金额", "金额"])
        
        for column in candidates:
            if column and column in project_row.index:
                value = project_row.get(column)
                if value not in (None, "") and pd.notna(value):
                    try:
                        return float(value)
                    except:
                        continue
        return 0.0


# 便捷函数
def create_unified_cashflow_service(feishu_client=None, payment_schedule_table_id: str = None):
    """创建统一现金流服务实例"""
    return UnifiedCashFlowService(feishu_client, payment_schedule_table_id)
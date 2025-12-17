# data/payment_schedule_service.py
"""
付款节奏服务 - 管理付款节点的读写

支持功能：
1. 从飞书加载付款节奏配置
2. 应用模板生成付款节点
3. 自定义编辑付款节点
4. 保存到飞书
"""

import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from dateutil.relativedelta import relativedelta


class PaymentScheduleService:
    """付款节奏服务"""
    
    def __init__(self, feishu_client, table_id: str):
        self.client = feishu_client
        self.table_id = table_id
        self._cache = None
    
    def load(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        加载付款节奏表所有记录
        
        Returns:
            DataFrame: 包含 record_id, template_name, payment_stages 等字段
        """
        if self._cache is not None and not force_refresh:
            return self._cache
        
        try:
            records = self.client.get_records(self.table_id)
            if records is None:
                records = []
        except Exception as e:
            print(f"加载付款节奏表失败: {e}")
            return pd.DataFrame()
        
        if not records:
            self._cache = pd.DataFrame()
            return self._cache
        
        rows = []
        for item in records:
            if item is None:
                continue
            fields = item.get("fields", {}) or {}
            row = {
                "_ps_record_id": item.get("record_id"),  # 飞书的 record_id
                "record_id": fields.get("record_id", ""),  # 关联主表的 record_id
                "template_name": fields.get("template_name", ""),
                "payment_stages": fields.get("payment_stages", "[]"),
                "updated_at": fields.get("updated_at"),
            }
            rows.append(row)
        
        self._cache = pd.DataFrame(rows) if rows else pd.DataFrame()
        return self._cache
    
    def get_payment_stages(self, source_record_id: str) -> List[Dict]:
        """
        获取指定记录的付款节点
        
        Args:
            source_record_id: 主表的 record_id
            
        Returns:
            付款节点列表
        """
        df = self.load()
        if df.empty or "record_id" not in df.columns:
            return []
        
        hit = df[df["record_id"] == source_record_id]
        if hit.empty:
            return []
        
        stages_json = hit.iloc[0].get("payment_stages", "[]")
        try:
            return json.loads(stages_json) if stages_json else []
        except json.JSONDecodeError:
            return []
    
    def get_template_name(self, source_record_id: str) -> str:
        """获取指定记录使用的模板名称"""
        df = self.load()
        if df.empty or "record_id" not in df.columns:
            return ""
        
        hit = df[df["record_id"] == source_record_id]
        if hit.empty:
            return ""
        
        return hit.iloc[0].get("template_name", "")
    
    def save(
        self,
        source_record_id: str,
        template_name: str,
        payment_stages: List[Dict],
    ) -> bool:
        """
        保存付款节奏配置
        
        Args:
            source_record_id: 主表的 record_id
            template_name: 模板名称
            payment_stages: 付款节点列表
            
        Returns:
            是否保存成功
        """
        # 查找是否已存在记录
        df = self.load(force_refresh=True)
        ps_record_id = None
        
        if not df.empty and "record_id" in df.columns:
            hit = df[df["record_id"] == source_record_id]
            if not hit.empty:
                ps_record_id = hit.iloc[0].get("_ps_record_id")
        
        # 构建字段数据
        fields = {
            "record_id": source_record_id,
            "template_name": template_name,
            "payment_stages": json.dumps(payment_stages, ensure_ascii=False),
            "updated_at": int(datetime.now().timestamp() * 1000),  # Unix 时间戳（毫秒）
        }
        
        try:
            if ps_record_id:
                # 更新已有记录
                self.client.update_record(
                    table_id=self.table_id,
                    record_id=ps_record_id,
                    fields=fields,
                )
            else:
                # 创建新记录
                self.client.create_record(
                    table_id=self.table_id,
                    fields=fields,
                )
            
            # 清除缓存
            self._cache = None
            return True
            
        except Exception as e:
            print(f"保存付款节奏失败: {e}")
            raise
    
    @staticmethod
    def apply_template(
        template_stages: List[Dict],
        start_date: Optional[datetime],
        delivery_date: Optional[datetime],
    ) -> List[Dict]:
        """
        应用模板生成具体的付款节点（含日期）
        
        Args:
            template_stages: 模板定义的付款节点
            start_date: 项目开始时间
            delivery_date: 项目交付时间
            
        Returns:
            带有具体日期的付款节点列表
        """
        result = []
        
        for stage in template_stages:
            # 确定基准日期
            base = stage.get("base", "交付时间")
            if base == "开始时间":
                base_date = start_date
            else:
                base_date = delivery_date
            
            # 计算付款日期
            offset = stage.get("offset_months", 0)
            if base_date and pd.notna(base_date):
                if isinstance(base_date, str):
                    base_date = pd.to_datetime(base_date, errors="coerce")
                if pd.notna(base_date):
                    pay_date = base_date + relativedelta(months=offset)
                    pay_date_ts = int(pay_date.timestamp() * 1000)
                else:
                    pay_date_ts = None
            else:
                pay_date_ts = None
            
            result.append({
                "name": stage.get("name", ""),
                "ratio": stage.get("ratio", 0),
                "date": pay_date_ts,
            })
        
        return result
    
    @staticmethod
    def calculate_payment_amounts(
        payment_stages: List[Dict],
        total_amount: float,
    ) -> List[Dict]:
        """
        计算每个付款节点的金额
        
        Args:
            payment_stages: 付款节点列表
            total_amount: 总金额（_final_amount）
            
        Returns:
            包含金额的付款节点列表
        """
        result = []
        for stage in payment_stages:
            amount = total_amount * stage.get("ratio", 0)
            result.append({
                **stage,
                "amount": round(amount, 2),
            })
        return result
    
    @staticmethod
    def stages_to_dataframe(
        payment_stages: List[Dict],
        project_info: Dict = None,
    ) -> pd.DataFrame:
        """
        将付款节点转换为 DataFrame（用于显示和分析）
        
        Args:
            payment_stages: 付款节点列表
            project_info: 项目信息（可选，用于添加项目名称等）
            
        Returns:
            DataFrame
        """
        rows = []
        for stage in payment_stages:
            row = {
                "付款节点": stage.get("name", ""),
                "付款比例": stage.get("ratio", 0),
                "付款金额": stage.get("amount", 0),
                "付款日期": stage.get("date"),
            }
            if project_info:
                row["客户"] = project_info.get("客户", "")
                row["业务线"] = project_info.get("业务线", "")
                row["record_id"] = project_info.get("record_id", "")
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # 转换日期格式
        if "付款日期" in df.columns:
            df["付款日期"] = pd.to_datetime(df["付款日期"], unit="ms", errors="coerce")
            df["付款月份"] = df["付款日期"].dt.strftime("%Y-%m")
        
        return df
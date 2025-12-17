# data/override_service.py - 修复版
import pandas as pd
import requests
from typing import Dict, Optional
from datetime import datetime


class OverrideService:
    """
    Override 服务：负责管理人工纠偏数据
    
    【职责】
    - 只负责 Overrides 表的读写
    - 提供 fetch_overrides() 和 upsert_override() 两个核心方法
    
    【存储字段】
    - record_id: 源记录ID（关联主表）
    - 人工纠偏金额: override_amount
    - updated_at: 更新时间
    """
    
    def __init__(self, feishu_client):
        """
        初始化 OverrideService

        Args:
            feishu_client: FeishuClient 实例，用于获取访问令牌和发送请求
        """
        self.feishu_client = feishu_client
        self._base_url = "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        # 【优化】缓存 record_id 到 feishu_record_id 的映射，避免重复请求
        self._record_id_cache: Optional[Dict[str, str]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # 缓存有效期60秒

    def _get_headers(self) -> Dict[str, str]:
        """获取包含认证信息的请求头"""
        token = self.feishu_client._get_tenant_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._record_id_cache is None or self._cache_timestamp is None:
            return False
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl_seconds

    def _invalidate_cache(self):
        """使缓存失效"""
        self._record_id_cache = None
        self._cache_timestamp = None

    def fetch_overrides(self) -> pd.DataFrame:
        """
        获取所有 Overrides 表记录

        Returns:
            DataFrame: 包含 source_record_id、override_amount、updated_at 列的数据框
        """
        from config import OVERRIDES_TABLE_ID

        url = self._base_url.format(
            app_token=self.feishu_client.app_token,
            table_id=OVERRIDES_TABLE_ID
        )

        headers = self._get_headers()
        all_records = []
        page_token = None

        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                raise Exception(f"Failed to fetch overrides: {response.status_code} - {response.text}")

            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"Feishu API error: {data.get('msg', 'Unknown error')} - {response.text}")

            records = data.get("data", {}).get("items", [])
            for record in records:
                fields = record.get("fields", {})
                source_record_id = None
                override_amount = None
                updated_at = None

                # 获取 source_record_id (Overrides 表中的 record_id 字段)
                source_record_id = str(fields.get("record_id") or "").strip()

                # 获取 人工纠偏金额
                raw_amt = fields.get("人工纠偏金额")
                try:
                    override_amount = float(raw_amt) if raw_amt not in (None, "") else None
                except (TypeError, ValueError):
                    override_amount = None

                # 获取 updated_at
                if "updated_at" in fields:
                    updated_at = fields["updated_at"]
                else:
                    # 如果没有 updated_at 字段，使用记录的创建或修改时间
                    updated_at = fields.get("创建时间", fields.get("修改时间", ""))

                if source_record_id and override_amount is not None:
                    all_records.append({
                        "source_record_id": source_record_id,
                        "override_amount": override_amount,
                        "updated_at": updated_at
                    })

            # 检查是否有更多分页
            page_token = data.get("data", {}).get("page_token")
            if not page_token:
                break

        return pd.DataFrame(all_records)

    def _get_record_id_mapping(self, force_refresh: bool = False) -> Dict[str, str]:
        """
        【优化】获取 source_record_id 到 feishu_record_id 的映射
        使用缓存避免重复请求
        
        Returns:
            Dict: {source_record_id: feishu_record_id}
        """
        if not force_refresh and self._is_cache_valid():
            return self._record_id_cache

        from config import OVERRIDES_TABLE_ID

        url = self._base_url.format(
            app_token=self.feishu_client.app_token,
            table_id=OVERRIDES_TABLE_ID
        )

        headers = self._get_headers()
        all_feishu_records = {}
        page_token = None

        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                raise Exception(f"Failed to fetch overrides: {response.status_code} - {response.text}")

            data = response.json()
            if data.get("code") != 0:
                raise Exception(f"Feishu API error: {data.get('msg', 'Unknown error')} - {response.text}")

            records = data.get("data", {}).get("items", [])
            for record in records:
                fields = record.get("fields", {})
                feishu_record_id = str(fields.get("record_id") or "").strip()
                if feishu_record_id:
                    all_feishu_records[feishu_record_id] = record["record_id"]  # Feishu 的实际 record_id

            page_token = data.get("data", {}).get("page_token")
            if not page_token:
                break

        # 更新缓存
        self._record_id_cache = all_feishu_records
        self._cache_timestamp = datetime.now()

        return all_feishu_records

    def upsert_override(self, source_record_id: str, override_amount: float, updated_at: str) -> None:
        """
        更新或创建 Override 记录

        Args:
            source_record_id: 源记录 ID
            override_amount: 人工纠偏金额
            updated_at: 更新时间
        """
        from config import OVERRIDES_TABLE_ID

        url = self._base_url.format(
            app_token=self.feishu_client.app_token,
            table_id=OVERRIDES_TABLE_ID
        )

        headers = self._get_headers()

        # 【优化】使用缓存的映射
        all_feishu_records = self._get_record_id_mapping()

        # 准备要更新的字段
        fields_data = {
            "record_id": source_record_id,
            "人工纠偏金额": override_amount,
            "updated_at": updated_at
        }

        # 检查是否存在对应的记录
        if source_record_id in all_feishu_records:
            # 存在记录，使用 PUT 更新
            update_url = f"{url}/{all_feishu_records[source_record_id]}"

            response = requests.put(
                update_url,
                headers=headers,
                json={"fields": fields_data}
            )

            if response.status_code != 200:
                raise Exception(f"Failed to update override: {response.status_code} - {response.text}")

            result = response.json()
            if result.get("code") != 0:
                raise Exception(f"Feishu API error: {result.get('msg', 'Unknown error')} - {response.text}")

        else:
            # 不存在记录，使用 POST 创建
            response = requests.post(
                url,
                headers=headers,
                json={"fields": fields_data}
            )

            if response.status_code != 200:
                raise Exception(f"Failed to create override: {response.status_code} - {response.text}")

            result = response.json()
            if result.get("code") != 0:
                raise Exception(f"Feishu API error: {result.get('msg', 'Unknown error')} - {response.text}")
            
            # 【优化】创建成功后，更新缓存
            new_feishu_record_id = result.get("data", {}).get("record", {}).get("record_id")
            if new_feishu_record_id and self._record_id_cache is not None:
                self._record_id_cache[source_record_id] = new_feishu_record_id

    def delete_override(self, source_record_id: str) -> bool:
        """
        删除 Override 记录
        
        Args:
            source_record_id: 源记录 ID
            
        Returns:
            bool: 删除是否成功
        """
        from config import OVERRIDES_TABLE_ID

        all_feishu_records = self._get_record_id_mapping()
        
        if source_record_id not in all_feishu_records:
            return False  # 记录不存在

        url = self._base_url.format(
            app_token=self.feishu_client.app_token,
            table_id=OVERRIDES_TABLE_ID
        )
        delete_url = f"{url}/{all_feishu_records[source_record_id]}"

        headers = self._get_headers()
        response = requests.delete(delete_url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to delete override: {response.status_code} - {response.text}")

        result = response.json()
        if result.get("code") != 0:
            raise Exception(f"Feishu API error: {result.get('msg', 'Unknown error')} - {response.text}")

        # 从缓存中移除
        if self._record_id_cache is not None and source_record_id in self._record_id_cache:
            del self._record_id_cache[source_record_id]

        return True

    def batch_upsert_overrides(self, records: list) -> int:
        """
        批量更新或创建 Override 记录
        
        Args:
            records: 记录列表，每个记录是一个字典，包含:
                     - source_record_id: 源记录ID
                     - override_amount: 人工纠偏金额
                     - updated_at: 更新时间（可选，默认当前时间）
        
        Returns:
            int: 成功处理的记录数
        """
        success_count = 0
        for record in records:
            try:
                source_record_id = record.get("source_record_id")
                override_amount = record.get("override_amount")
                updated_at = record.get("updated_at", datetime.now().isoformat())
                
                if source_record_id and override_amount is not None:
                    self.upsert_override(source_record_id, override_amount, updated_at)
                    success_count += 1
            except Exception as e:
                # 记录错误但继续处理其他记录
                print(f"Error upserting override for {record.get('source_record_id')}: {e}")
                continue
        
        return success_count
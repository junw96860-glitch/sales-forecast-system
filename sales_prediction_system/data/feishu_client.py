# data/feishu_client.py
import requests
import time


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, app_token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.app_token = app_token
        self._tenant_access_token = None
        self._token_expire_time = 0

    def _get_tenant_access_token(self):
        if not self._tenant_access_token or time.time() >= self._token_expire_time:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            resp = requests.post(url, json={
                "app_id": self.app_id,
                "app_secret": self.app_secret
            })
            data = resp.json()
            if "tenant_access_token" not in data:
                raise Exception(f"Failed to get tenant_access_token: {data}")
            self._tenant_access_token = data["tenant_access_token"]
            self._token_expire_time = time.time() + data.get("expire", 7200) - 60
        return self._tenant_access_token

    def get_records(self, table_id: str, page_size=100):
        """
        获取表格所有记录
        
        Returns:
            list: 记录列表，每个记录包含 record_id 和 fields。空表返回空列表 []
        """
        headers = {"Authorization": f"Bearer {self._get_tenant_access_token()}"}
        records = []
        page_token = None
        
        while True:
            params = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
                
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records"
            resp = requests.get(url, headers=headers, params=params)
            data = resp.json()
            
            if data.get("code") != 0:
                raise Exception(f"Feishu API error: {data}")
            
            # 【修复】处理 items 为 None 的情况
            items = data.get("data", {}).get("items")
            if items is None:
                items = []
            records.extend(items)
            
            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data["data"].get("page_token")
            
        return records

    def create_record(self, table_id: str, fields: dict):
        """
        创建新记录
        
        Args:
            table_id: 表格ID
            fields: 字段数据字典
            
        Returns:
            str: 新记录的 record_id
        """
        headers = {
            "Authorization": f"Bearer {self._get_tenant_access_token()}",
            "Content-Type": "application/json"
        }
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records"
        resp = requests.post(url, headers=headers, json={"fields": fields})
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"Create record failed: {data}")
        return data["data"]["record"]["record_id"]

    def update_record(self, table_id: str, record_id: str, fields: dict):
        """
        更新已有记录
        
        Args:
            table_id: 表格ID
            record_id: 记录ID（飞书的 record_id）
            fields: 要更新的字段数据字典
            
        Returns:
            dict: 更新后的记录数据
        """
        headers = {
            "Authorization": f"Bearer {self._get_tenant_access_token()}",
            "Content-Type": "application/json"
        }
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}"
        resp = requests.put(url, headers=headers, json={"fields": fields})
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"Update record failed: {data}")
        return data.get("data", {}).get("record", {})

    def delete_record(self, table_id: str, record_id: str):
        """
        删除记录
        
        Args:
            table_id: 表格ID
            record_id: 记录ID
            
        Returns:
            bool: 是否删除成功
        """
        headers = {
            "Authorization": f"Bearer {self._get_tenant_access_token()}",
            "Content-Type": "application/json"
        }
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}"
        resp = requests.delete(url, headers=headers)
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"Delete record failed: {data}")
        return True

    def batch_create_records(self, table_id: str, records: list):
        """
        批量创建记录
        
        Args:
            table_id: 表格ID
            records: 记录列表，每个记录是一个 {"fields": {...}} 字典
            
        Returns:
            list: 创建的记录ID列表
        """
        headers = {
            "Authorization": f"Bearer {self._get_tenant_access_token()}",
            "Content-Type": "application/json"
        }
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/batch_create"
        resp = requests.post(url, headers=headers, json={"records": records})
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"Batch create records failed: {data}")
        return [r["record_id"] for r in data.get("data", {}).get("records", [])]
# data/data_service.py
from __future__ import annotations

import os
import pickle
import json
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN, SALES_TABLES
from data.feishu_client import FeishuClient


class SalesDataService:
    """飞书销售事实数据的 I/O 层（只负责读写，不做口径计算）。

    设计约束（用于系统严谨性）：
    - 不写回派生/计算列（例如 _final_amount、_system_pred_amount 等）
    - 不写回“人工纠偏金额”（应由 OverrideService 写入 overrides 表）
    - 仅写回事实字段白名单（字段映射见 _FACT_FIELD_MAPPING）
    """

    # 事实字段白名单（DataFrame 列 -> 飞书字段）
    _FACT_FIELD_MAPPING: Dict[str, str] = {
        "客户": "客户",
        "金额": "金额",
        "成单率": "成单率",
        "交付时间": "交付时间",
        "主要描述": "主要描述",
        "预计截止时间": "预计截止时间",
        "数量": "数量",
        "开始时间": "开始时间",
        "交付内容": "交付内容",
        "当前进展": "当前进展",
        # 付款条款（事实字段，可写回）
        "首付款比例": "首付款比例",
        "次付款比例": "次付款比例",
        "尾款比例": "尾款比例",
        "质保金比例": "质保金比例",
        "首付款时间": "首付款时间",
        "次付款时间": "次付款时间",
        "尾款时间": "尾款时间",
        "质保金时间": "质保金时间",
    }

    # 绝不允许写回的列（即使存在于 df 里）
    _FORBIDDEN_WRITEBACK_COLS = {
        "人工纠偏金额",
        "_final_amount",
        "_system_pred_amount",
        "_金额_num",
        "_成单率_num",
        "_交付月份",
        "交付月份",
        "预期收入",
    }

    def __init__(self):
        self.client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN)
        self.cache_dir = "data/cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        self.cache_file = os.path.join(self.cache_dir, "edited_data_cache.pkl")
        self.version_file = os.path.join(self.cache_dir, "data_version.txt")

    # -----------------------------
    # Read
    # -----------------------------
    def load_all_sales_data(self, prefer_local_cache: bool = True) -> pd.DataFrame:
        """加载所有销售事实数据。

        Args:
            prefer_local_cache: True 时优先读取本地缓存（编辑后的数据）。
                               注意：如果你希望强制从飞书拉取，传 False。
        """
        if prefer_local_cache:
            cached_df = self.load_from_local_cache()
            if cached_df is not None:
                return cached_df

        all_data = []
        for business_line, table_id in SALES_TABLES.items():
            try:
                records = self.client.get_records(table_id)
                for record in records:
                    fields = record.get("fields", {})
                    fields["业务线"] = business_line
                    fields["record_id"] = record.get("record_id", "")
                    all_data.append(fields)
            except Exception as e:
                print(f"获取{business_line}数据时出错: {str(e)}")

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)

        # 兼容飞书多维表日期字段的常见返回格式
        def _extract_feishu_date_value(x):
            if x is None or (isinstance(x, float) and pd.isna(x)):
                return None
            if isinstance(x, dict):
                for k in ("value", "timestamp", "start_time", "end_time"):
                    if k in x:
                        return x[k]
                return None
            if isinstance(x, list):
                return _extract_feishu_date_value(x[0]) if len(x) > 0 else None
            return x

        def _parse_maybe_timestamp(v):
            if v is None:
                return pd.NaT
            vn = pd.to_numeric(v, errors="coerce")
            if pd.notna(vn):
                if vn >= 1e12:
                    return pd.to_datetime(vn, unit="ms", errors="coerce")
                if vn >= 1e9:
                    return pd.to_datetime(vn, unit="s", errors="coerce")
                return pd.NaT
            return pd.to_datetime(str(v).strip(), errors="coerce")

        date_columns = ["开始时间", "预计截止时间", "交付时间", "首付款时间", "次付款时间", "尾款时间", "质保金时间"]
        for col in date_columns:
            if col in df.columns:
                df[col] = df[col].apply(_extract_feishu_date_value).apply(_parse_maybe_timestamp)

        return df

    # -----------------------------
    # Write
    # -----------------------------
    def save_data(self, df: pd.DataFrame) -> bool:
        """保存事实字段到飞书（严格白名单）。

        注意：
        - df 中可能包含派生列（_final_amount 等），这里会自动过滤，不会写回。
        - “人工纠偏金额”不写回事实表（应写 overrides 表）。
        """
        if df is None or df.empty:
            return False

        if "业务线" not in df.columns or "客户" not in df.columns:
            raise ValueError("保存飞书失败：DataFrame 必须包含列：业务线、客户")

        total_updated = 0
        total_created = 0
        total_failed = 0

        for business_line, table_id in SALES_TABLES.items():
            business_df = df[df["业务线"] == business_line].copy()
            if business_df.empty:
                continue

            try:
                existing_records = self.client.get_records(table_id)

                client_to_record_id: Dict[str, str] = {}
                record_id_set = set()
                for r in existing_records:
                    rid = r.get("record_id", "") or ""
                    fields = r.get("fields", {}) or {}
                    client_name = str(fields.get("客户", "") or "").strip()
                    if rid:
                        record_id_set.add(rid)
                    if client_name and rid:
                        client_to_record_id[client_name] = rid

                for _, row in business_df.iterrows():
                    record_data = self._prepare_record_data(row)
                    if not record_data:
                        continue

                    # 优先使用 row 的 record_id；否则用 客户 匹配
                    rid = str(row.get("record_id", "") or "").strip()
                    client_name = str(row.get("客户", "") or "").strip()

                    target_id: Optional[str] = None
                    if rid and rid in record_id_set:
                        target_id = rid
                    elif client_name and client_name in client_to_record_id:
                        target_id = client_to_record_id[client_name]

                    try:
                        if target_id:
                            self.client.update_record(table_id, target_id, record_data)
                            total_updated += 1
                        else:
                            self.client.create_record(table_id, record_data)
                            total_created += 1
                    except Exception as e:
                        total_failed += 1
                        print(f"[飞书写入失败] 业务线={business_line} 客户={client_name}: {e}")

            except Exception as e:
                total_failed += 1
                print(f"保存{business_line}数据时出错: {str(e)}")

        print(f"[飞书保存汇总] updated={total_updated} created={total_created} failed={total_failed}")
        return total_failed == 0

    def update_record(self, table_id: str, record_id: str, fields: dict) -> bool:
        """更新单条记录（兼容旧调用，内部走 FeishuClient）。"""
        self.client.update_record(table_id, record_id, fields)
        return True

    # -----------------------------
    # Local cache
    # -----------------------------
    def save_to_local_cache(self, df: pd.DataFrame, version_info: Optional[str] = None) -> bool:
        if df is None or df.empty:
            return False
        try:
            with open(self.cache_file, "wb") as f:
                pickle.dump(df, f)

            version_data = {
                "version": version_info or datetime.now().isoformat(),
                "timestamp": datetime.now().isoformat(),
                "row_count": len(df),
                "columns": list(df.columns),
            }
            with open(self.version_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(version_data, ensure_ascii=False, indent=2))
            return True
        except Exception as e:
            print(f"保存本地缓存失败: {str(e)}")
            return False

    def load_from_local_cache(self) -> Optional[pd.DataFrame]:
        if not os.path.exists(self.cache_file):
            return None
        try:
            with open(self.cache_file, "rb") as f:
                df = pickle.load(f)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                return None
            return df
        except Exception as e:
            print(f"加载本地缓存失败: {str(e)}")
            return None

    def get_cache_version_info(self) -> Optional[dict]:
        if not os.path.exists(self.version_file):
            return None
        try:
            with open(self.version_file, "r", encoding="utf-8") as f:
                return json.loads(f.read())
        except Exception:
            return None

    def clear_local_cache(self) -> bool:
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
            if os.path.exists(self.version_file):
                os.remove(self.version_file)
            return True
        except Exception:
            return False

    # -----------------------------
    # Helpers
    # -----------------------------
    def _prepare_record_data(self, row: Any) -> Dict[str, Any]:
        """准备写回飞书的 fields（严格白名单 + 禁写列）"""
        record_data: Dict[str, Any] = {}

        for df_col, ls_col in self._FACT_FIELD_MAPPING.items():
            # 禁写列优先
            if df_col in self._FORBIDDEN_WRITEBACK_COLS:
                continue

            # pandas Series: df_col in row 是检查 index；dict-like 也兼容
            try:
                exists = df_col in row
            except Exception:
                exists = False
            if not exists:
                continue

            value = row[df_col]
            if pd.isna(value):
                continue

            # 统一日期序列化
            if isinstance(value, (pd.Timestamp, datetime)):
                record_data[ls_col] = value.strftime("%Y-%m-%d")
            # 数值字段保持数值
            elif isinstance(value, (int, float)):
                record_data[ls_col] = value
            else:
                record_data[ls_col] = str(value)

        # 额外安全：过滤 df 中以 "_" 开头的列（即使误配到 mapping，也不写）
        record_data = {k: v for k, v in record_data.items() if not str(k).startswith("_")}

        return record_data

# data/data_manager.py
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, MutableMapping, Optional

import numpy as np
import pandas as pd

from core.config_manager import config_manager
from data.data_service import SalesDataService
from data.override_service import OverrideService
from data.schema import DataSchema
from utils.validators import DataValidator, get_default_validator


class DataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.service = SalesDataService()
        self.validator = DataValidator()
        self.custom_validator = get_default_validator()

        # 外部可注入的“会话态存储”，避免 data 层依赖 streamlit
        self._state_store: Optional[MutableMapping[str, Any]] = None
        self._fallback_state: Dict[str, Any] = {}

        self._initialized = True

    # -----------------------------
    # State store（替代 st.session_state）
    # -----------------------------
    def set_state_store(self, store: Optional[MutableMapping[str, Any]]) -> None:
        """
        注入一个 dict-like 的状态容器（推荐在 Streamlit 页面里调用）：
            data_manager.set_state_store(st.session_state)

        不注入也能跑（使用 fallback_state），但多用户场景会共享进程内状态，不推荐。
        """
        self._state_store = store

    def _state(self, state: Optional[MutableMapping[str, Any]] = None) -> MutableMapping[str, Any]:
        return state if state is not None else (self._state_store if self._state_store is not None else self._fallback_state)

    def _init_state(self, state: Optional[MutableMapping[str, Any]] = None) -> None:
        s = self._state(state)
        s.setdefault("data_version", None)
        s.setdefault("data_hash", None)
        s.setdefault("edited_data", None)
        s.setdefault("data_source", None)

    # -----------------------------
    # 入口：读取 active data
    # -----------------------------
    def get_active_data(self, force_reload: bool = False, state: Optional[MutableMapping[str, Any]] = None) -> pd.DataFrame:
        self._init_state(state)
        s = self._state(state)

        if force_reload:
            return self._load_from_feishu(state=state)

        if s.get("edited_data") is not None:
            return s["edited_data"].copy()

        cached = self.service.load_from_local_cache()
        if cached is not None and not cached.empty:
            cached = self._standardize_data(cached)
            s["edited_data"] = cached
            s["data_source"] = "local_cache"
            s["data_hash"] = self._compute_hash(cached)
            s["data_version"] = datetime.now().isoformat()
            return cached.copy()

        return self._load_from_feishu(state=state)

    def _load_from_feishu(self, state: Optional[MutableMapping[str, Any]] = None) -> pd.DataFrame:
        self._init_state(state)
        s = self._state(state)

        df = self.service.load_all_sales_data()
        if df is None or df.empty:
            return pd.DataFrame()

        df = self._standardize_data(df)

        s["edited_data"] = df
        s["data_source"] = "feishu"
        s["data_hash"] = self._compute_hash(df)
        s["data_version"] = datetime.now().isoformat()
        return df.copy()

    # -----------------------------
    # 核心口径：金额/成单率/预测/纠偏
    # -----------------------------
    @staticmethod
    def _parse_amount_wan(series: pd.Series) -> pd.Series:
        """
        金额统一成"万元"数值：
        - 飞书金额录入：89.5 表示 89.5 万（你的口径）
        - 支持 "¥1,234.5" 这种符号，但不做单位推断
        """

        def _one(x):
            if pd.isna(x) or x == "":
                return 0.0
            s = str(x).strip()
            s = s.replace("¥", "").replace(",", "")
            s = re.sub(r"[^0-9\.\-]", "", s)
            try:
                return float(s) if s not in ("", "-", ".", "-.") else 0.0
            except Exception:
                return 0.0

        return series.apply(_one).astype(float)

    @staticmethod
    def _parse_rate_percent(series: pd.Series) -> pd.Series:
        """
        成单率统一成"百分比数值"(0~100)：
        - 支持 80 / "80%" / "50%-80%" 等区间写法
        - 与 Dashboard "项目列表预览" 的展示逻辑保持一致
        """
        if series is None:
            return pd.Series(pd.NA, dtype="float64")

        s = series.astype(str).str.strip()

        def _one(value: str):
            if value == "" or value.lower() in ("nan", "none"):
                return pd.NA

            clean = value.replace("%", "").strip()
            if "-" in clean:
                parts = [p.strip() for p in clean.split("-") if p.strip()]
                if len(parts) >= 2:
                    a = pd.to_numeric(parts[0], errors="coerce")
                    b = pd.to_numeric(parts[1], errors="coerce")
                    if pd.notna(a) and pd.notna(b):
                        return float(a + b) / 2.0

            return pd.to_numeric(clean, errors="coerce")

        parsed = pd.to_numeric(s.apply(_one), errors="coerce")
        parsed = parsed.where(parsed.isna() | ((parsed >= 0) & (parsed <= 100)))
        return parsed

    def _compute_time_decay_factor(self, df: pd.DataFrame) -> pd.Series:
        """
        根据配置的时间衰减系数 λ 和基准日期，计算每一行的衰减因子。
        优先使用"预计截止时间"，缺失时依次回退到"交付时间""开始时间"。
        """
        if df.empty:
            return pd.Series([], dtype="float64")

        forecast_cfg = config_manager.get_config("forecast") or {}
        decay_lambda = forecast_cfg.get("decay_lambda", 0.0) or 0.0
        base_offset = forecast_cfg.get("base_date_offset", 0) or 0

        if decay_lambda <= 0:
            return pd.Series(1.0, index=df.index, dtype="float64")

        base_dt = pd.Timestamp(datetime.now() + timedelta(days=base_offset))

        date_series = None
        for col in ["预计截止时间", "交付时间", "开始时间"]:
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().any():
                    date_series = parsed
                    break

        if date_series is None:
            return pd.Series(1.0, index=df.index, dtype="float64")

        delta_days = (date_series - base_dt).dt.days
        delta_months = (delta_days / 30.0).clip(lower=0).fillna(0.0)

        decay_factor = np.exp(-decay_lambda * delta_months)
        decay_factor = pd.Series(decay_factor, index=df.index).fillna(1.0)
        return decay_factor.astype(float)

    def _standardize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        # 必须有 record_id（用于 merge overrides）
        if "record_id" not in result.columns:
            result["record_id"] = None

        # 1) 金额(万元) -> _金额_num
        if "金额" in result.columns:
            result["_金额_num"] = self._parse_amount_wan(result["金额"])
        else:
            result["_金额_num"] = 0.0

        # 2) 成单率(%) -> _成单率_num
        if "成单率" in result.columns:
            result["_成单率_num"] = self._parse_rate_percent(result["成单率"])
        else:
            result["_成单率_num"] = 0.0

        # 3) 系统预测金额（万元）：金额 * 成单率% * 时间衰减
        rate_for_calc = pd.to_numeric(result["_成单率_num"], errors="coerce").fillna(0.0)
        decay_factor = self._compute_time_decay_factor(result)
        if decay_factor.empty:
            decay_factor = pd.Series(1.0, index=result.index, dtype="float64")
        result["_system_pred_amount"] = result["_金额_num"] * (rate_for_calc / 100.0) * decay_factor

        # 4) merge Overrides -> 人工纠偏金额（万元）
        ov_df = self._fetch_overrides_latest()
        if not ov_df.empty:
            merged = pd.merge(
                result,
                ov_df[["record_id", "override_amount", "updated_at"]],
                on="record_id",
                how="left",
                suffixes=("", "_ov"),
            )
            result = merged
            result["人工纠偏金额"] = pd.to_numeric(result["override_amount"], errors="coerce")
            result.drop(columns=[c for c in ["override_amount"] if c in result.columns], inplace=True)
        else:
            result["人工纠偏金额"] = pd.Series([pd.NA] * len(result), index=result.index, dtype="object")

        # 5) _final_amount（万元）：人工纠偏优先，否则系统预测
        manual = pd.to_numeric(result["人工纠偏金额"], errors="coerce")
        result["_final_amount"] = manual.where(manual.notna(), result["_system_pred_amount"]).fillna(0.0).astype(float)

        round_2_cols = [
            "_金额_num",
            "_成单率_num",
            "_system_pred_amount",
            "人工纠偏金额",
            "_final_amount",
        ]
        for col in round_2_cols:
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors="coerce").round(2)

        # 兼容旧页面：预期收入 = _final_amount（但不写回飞书原表）
        if "预期收入" not in result.columns:
            result["预期收入"] = result["_final_amount"]

        # ============ 统一生成 _交付月份 字段 ============
        date_col_for_month = None
        for col in ["交付时间", "预计截止时间"]:
            if col in result.columns:
                date_col_for_month = col
                break

        if date_col_for_month is not None:
            parsed_dates = pd.to_datetime(result[date_col_for_month], errors="coerce")
            result["_交付月份"] = parsed_dates.dt.to_period("M").astype(str).where(parsed_dates.notna(), pd.NA)
        else:
            result["_交付月份"] = pd.NA

        # 同时生成不带下划线的版本，兼容旧代码
        result["交付月份"] = result["_交付月份"]
        # ============ 结束 ============

        if "_final_amount" not in result.columns:
            raise RuntimeError("DataManager 输出必须包含 _final_amount")

        return result

    def _fetch_overrides_latest(self) -> pd.DataFrame:
        """
        拉 overrides 表，并按 record_id 取最新一条
        返回：record_id, override_amount, updated_at
        """
        try:
            from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN
            from data.feishu_client import FeishuClient

            feishu_client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN)
            ov_service = OverrideService(feishu_client)
            ov_df = ov_service.fetch_overrides()
        except Exception:
            return pd.DataFrame(columns=["record_id", "override_amount", "updated_at"])

        if ov_df is None or ov_df.empty:
            return pd.DataFrame(columns=["record_id", "override_amount", "updated_at"])

        # 统一字段名：override_service 可能返回 source_record_id / record_id 两种
        if "source_record_id" in ov_df.columns and "record_id" not in ov_df.columns:
            ov_df = ov_df.rename(columns={"source_record_id": "record_id"})

        if "record_id" not in ov_df.columns:
            return pd.DataFrame(columns=["record_id", "override_amount", "updated_at"])

        # 统一 override_amount 列名
        if "override_amount" not in ov_df.columns and "人工纠偏金额" in ov_df.columns:
            ov_df["override_amount"] = ov_df["人工纠偏金额"]

        ov_df["record_id"] = ov_df["record_id"].astype(str)
        ov_df["override_amount"] = pd.to_numeric(ov_df["override_amount"], errors="coerce")
        ov_df["updated_at"] = pd.to_datetime(ov_df.get("updated_at"), errors="coerce")

        ov_df = ov_df.dropna(subset=["record_id"])
        ov_df = ov_df.sort_values("updated_at").groupby("record_id", as_index=False).last()

        return ov_df[["record_id", "override_amount", "updated_at"]]

    # -----------------------------
    # 保存（目前保留，但不建议写回原表"金额/成单率/预期收入"）
    # -----------------------------
    def save_data(
        self,
        df: pd.DataFrame,
        save_to_feishu: bool = True,
        state: Optional[MutableMapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._init_state(state)
        s = self._state(state)

        result: Dict[str, Any] = {"success": False, "local_cache": False, "feishu": False, "errors": []}

        errors = self._validate_data(df)
        if errors:
            result["errors"] = errors
            return result

        schema_result = DataSchema.validate_dataframe(df)
        if schema_result.get("errors"):
            result["errors"].extend(schema_result["errors"])
            return result

        df = DataSchema.ensure_required_columns(df)
        df = DataSchema.cast_column_types(df)
        df = self._custom_standardize(df)

        # 再走一遍口径保证 _final_amount 一定正确
        df = self._standardize_data(df)

        try:
            cache_version = datetime.now().isoformat()
            if self.service.save_to_local_cache(df, cache_version):
                result["local_cache"] = True
        except Exception as e:
            result["errors"].append(f"本地缓存保存失败: {str(e)}")

        if save_to_feishu:
            try:
                if self.service.save_data(df):
                    result["feishu"] = True
            except Exception as e:
                result["errors"].append(f"飞书保存失败: {str(e)}")

        s["edited_data"] = df.copy()
        s["data_hash"] = self._compute_hash(df)
        s["data_version"] = datetime.now().isoformat()
        s["data_source"] = "feishu" if result["feishu"] else "local_cache"

        result["success"] = result["local_cache"] or result["feishu"]
        return result

    def _custom_standardize(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        if "record_id" not in result.columns:
            result["record_id"] = None
        return result

    def _validate_data(self, df: pd.DataFrame) -> list:
        errors = []
        required_columns = ["客户", "业务线", "金额"]
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            errors.append(f"缺少必需列: {', '.join(missing)}")
        return errors

    def _compute_hash(self, df: pd.DataFrame) -> str:
        return hashlib.md5(df.to_json().encode()).hexdigest()

    def has_unsaved_changes(self, state: Optional[MutableMapping[str, Any]] = None) -> bool:
        self._init_state(state)
        s = self._state(state)

        if s.get("edited_data") is None:
            return False
        return self._compute_hash(s["edited_data"]) != s.get("data_hash")

    def get_data_info(self, state: Optional[MutableMapping[str, Any]] = None) -> Dict[str, Any]:
        self._init_state(state)
        s = self._state(state)

        cache_info = self.service.get_cache_version_info()
        return {
            "source": s.get("data_source"),
            "version": s.get("data_version"),
            "has_changes": self.has_unsaved_changes(state=state),
            "cache_info": cache_info,
            "row_count": len(s["edited_data"]) if s.get("edited_data") is not None else 0,
        }

    def clear_cache(self, state: Optional[MutableMapping[str, Any]] = None) -> None:
        self._init_state(state)
        s = self._state(state)

        self.service.clear_local_cache()
        s["edited_data"] = None
        s["data_hash"] = None
        s["data_version"] = None
        s["data_source"] = None


data_manager = DataManager()

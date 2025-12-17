# core/config_manager.py - 统一配置管理器 (修正版)
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple, Union

import pandas as pd
import streamlit as st


class ConfigManager:
    """统一配置管理器

    管理所有页面级别的配置，包括：
    - 预测参数（时间衰减、基准日期等）
    - 成本参数（物料比例、税率、付款配置等）
    - 显示配置（图表选项、列显示等）
    - 预算/对比/现金流页的通用筛选条件

    设计目标：
    1) 跨页面共享（使用同一份 config + 统一 widget key）
    2) 跨刷新持久化（落盘到 config/app_config.json）
    """

    def __init__(self, config_file: str = "config/app_config.json"):
        self.config_file = config_file
        self.default_config = self._get_default_config()
        self.current_config = self._load_config()

        # 确保配置目录存在
        Path(os.path.dirname(self.config_file)).mkdir(parents=True, exist_ok=True)

        # 如果配置文件不存在，写入默认配置
        if not os.path.exists(self.config_file):
            self.save_config(self.default_config)

    # -----------------------------
    # 默认配置
    # -----------------------------
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "forecast": {
                "decay_lambda": 0.0315,  # 时间衰减系数
                "base_date_offset": 0,  # 基准日期偏移（天）
                "months_ahead": 12,  # 预测月份数
                "show_stage_details": True,  # 显示阶段详情
                "auto_refresh": True,  # 自动刷新
            },
            "cost": {
                # 注意：你现在希望"按业务线分别配置"，所以 material_cost_rate 保留但不作为主口径
                "material_cost_rate": 0.3,  # 全局物料成本率（兼容旧逻辑）
                "labor_cost_rate": 0.4,  # 人工成本率
                "admin_cost_rate": 0.15,  # 行政成本率

                # 按业务线物料比例（主口径）
                "material_ratios_by_line": {
                    "光谱设备/服务": 0.30,
                    "配液设备": 0.35,
                    "自动化项目": 0.40,
                },

                # 税率（增值税）
                "tax_rate": 0.13,

                # 默认付款阶段比例（%）
                "default_payment_stages": {
                    "首付款比例": 50.0,
                    "次付款比例": 40.0,
                    "尾款比例": 0.0,
                    "质保金比例": 10.0,
                },
            },
            "cashflow": {
                "current_cash": 100.0,  # 当前现金余额（万元）
                "months_ahead": 12,  # 现金流预测周期（月）
            },
            "budget": {
                "start_month": "2025-01",
                "end_month": "2025-12",
            },
            "compare": {
                "start_month": "2025-01",
                "end_month": "2025-12",
            },
            "display": {
                "chart_height": 400,  # 图表高度
                "table_page_size": 10,  # 表格分页大小
                "show_empty_categories": False,  # 显示空分类
                "color_palette": "plotly",  # 配色方案
            },
            "data": {
                "auto_save": True,  # 自动保存
                "cache_hours": 24,  # 缓存时间（小时）
                "backup_count": 5,  # 备份数量
                "validate_on_save": True,  # 保存时验证
                "show_data_source": True,  # 显示数据来源
            },
            "feishu": {
                "app_id": "",
                "app_secret": "",
            },
            "business": {
                "lines": ["光谱设备/服务", "配液设备", "自动化项目"],
            },
        }

    # -----------------------------
    # 读写配置（落盘）
    # -----------------------------
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                # 合并默认配置和当前配置，确保新增字段不会丢
                return self._merge_config(self.default_config, config)
            return self.default_config.copy()
        except Exception as e:
            st.error(f"加载配置文件失败: {str(e)}")
            return self.default_config.copy()

    def _merge_config(self, default: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
        """合并配置（递归更新）"""
        result = default.copy()
        for key, value in current.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def get_config(self, category: str, key: Optional[str] = None) -> Any:
        """获取配置值"""
        if category not in self.current_config:
            return None
        if key is None:
            return self.current_config[category]
        return self.current_config[category].get(key)

    def set_config(self, category: str, key_or_value: Union[str, Dict[str, Any]], value: Any = None):
        """设置配置值
        
        支持两种调用方式：
        1. set_config("forecast", "decay_lambda", 0.05)  # 设置单个键值
        2. set_config("forecast", {"decay_lambda": 0.05, "months_ahead": 24})  # 设置整个分类
        """
        if category not in self.current_config:
            self.current_config[category] = {}
        
        # 判断调用方式
        if isinstance(key_or_value, dict):
            # 方式2：整个 dict 覆盖/合并
            for k, v in key_or_value.items():
                self.current_config[category][k] = v
        else:
            # 方式1：单个键值
            self.current_config[category][key_or_value] = value

        # 自动保存
        if self.get_config("data", "auto_save"):
            self.save_config()

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """保存配置到文件"""
        try:
            if config is not None:
                self.current_config = config

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.current_config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            st.error(f"保存配置文件失败: {str(e)}")
            return False

    def reset_to_default(self, category: Optional[str] = None):
        """重置配置到默认值"""
        if category is None:
            self.current_config = self.default_config.copy()
        else:
            if category in self.default_config:
                self.current_config[category] = self.default_config[category].copy()

        self.save_config()

    # -----------------------------
    # UI helpers（统一 key + 自动持久化）
    # -----------------------------
    @staticmethod
    def _safe_key(s: str) -> str:
        # 将业务线等文本变成稳定、安全的 widget key
        return "".join(ch if ch.isalnum() else "_" for ch in str(s))

    def render_forecast_config_ui(self, sidebar: bool = True) -> Dict[str, Any]:
        """渲染预测配置UI"""
        if sidebar:
            st.sidebar.markdown("---")
            st.sidebar.header("📈 预测配置")
        else:
            st.header("📈 预测配置")

        container = st.sidebar if sidebar else st
        config = self.get_config("forecast")

        decay_lambda = container.number_input(
            "时间衰减系数 λ",
            min_value=0.0,
            max_value=1.0,
            value=float(config.get("decay_lambda", 0.0315)),
            step=0.001,
            format="%.4f",
            help="λ 越大，越远期的项目折扣越大",
            key="cfg_forecast_decay_lambda",
        )

        base_offset = container.number_input(
            "基准日期偏移（天）",
            min_value=-365,
            max_value=365,
            value=int(config.get("base_date_offset", 0)),
            step=1,
            help="用于调整预测的基准日期",
            key="cfg_forecast_base_offset",
        )

        months_ahead = container.number_input(
            "预测月份数",
            min_value=1,
            max_value=60,
            value=int(config.get("months_ahead", 12)),
            step=1,
            key="cfg_forecast_months_ahead",
        )

        show_stage_details = container.checkbox(
            "显示阶段详情",
            value=bool(config.get("show_stage_details", True)),
            key="cfg_forecast_show_stage_details",
        )

        auto_refresh = container.checkbox(
            "自动刷新",
            value=bool(config.get("auto_refresh", True)),
            key="cfg_forecast_auto_refresh",
        )

        # 保存配置
        if decay_lambda != config.get("decay_lambda"):
            self.set_config("forecast", "decay_lambda", decay_lambda)
        if base_offset != config.get("base_date_offset"):
            self.set_config("forecast", "base_date_offset", base_offset)
        if months_ahead != config.get("months_ahead"):
            self.set_config("forecast", "months_ahead", months_ahead)
        if show_stage_details != config.get("show_stage_details"):
            self.set_config("forecast", "show_stage_details", show_stage_details)
        if auto_refresh != config.get("auto_refresh"):
            self.set_config("forecast", "auto_refresh", auto_refresh)

        return {
            "decay_lambda": decay_lambda,
            "base_date_offset": base_offset,
            "months_ahead": months_ahead,
            "show_stage_details": show_stage_details,
            "auto_refresh": auto_refresh,
        }

    def render_cost_config_ui(self, sidebar: bool = True) -> Dict[str, Any]:
        """渲染成本配置UI（全局成本率，兼容旧逻辑）"""
        if sidebar:
            st.sidebar.markdown("---")
            st.sidebar.header("💰 成本配置")
        else:
            st.header("💰 成本配置")

        container = st.sidebar if sidebar else st
        config = self.get_config("cost")

        material_rate = container.slider(
            "物料成本率（全局）",
            min_value=0.0,
            max_value=1.0,
            value=float(config.get("material_cost_rate", 0.30)),
            format="%.0f%%",
            help="全局物料成本率（兼容旧逻辑，推荐使用按业务线物料比例）",
            key="cfg_cost_material_cost_rate",
        )
        labor_rate = container.slider(
            "人工成本率",
            min_value=0.0,
            max_value=1.0,
            value=float(config.get("labor_cost_rate", 0.40)),
            format="%.0f%%",
            help="人工成本占收入的比例",
            key="cfg_cost_labor_cost_rate",
        )
        admin_rate = container.slider(
            "行政成本率",
            min_value=0.0,
            max_value=1.0,
            value=float(config.get("admin_cost_rate", 0.15)),
            format="%.0f%%",
            help="费用支出占收入的比例",
            key="cfg_cost_admin_cost_rate",
        )

        if material_rate != config.get("material_cost_rate"):
            self.set_config("cost", "material_cost_rate", material_rate)
        if labor_rate != config.get("labor_cost_rate"):
            self.set_config("cost", "labor_cost_rate", labor_rate)
        if admin_rate != config.get("admin_cost_rate"):
            self.set_config("cost", "admin_cost_rate", admin_rate)

        return {
            "material_cost_rate": material_rate,
            "labor_cost_rate": labor_rate,
            "admin_cost_rate": admin_rate,
        }

    def render_material_ratios_ui(
        self,
        business_lines: Optional[List[str]] = None,
        sidebar: bool = True,
        header: str = "📦 物料比例配置",
        default_ratio: float = 0.30,
    ) -> Dict[str, float]:
        """按业务线渲染物料比例配置（主口径，自动持久化）
        
        Args:
            business_lines: 业务线列表，如果为 None 则从配置读取
        """
        container = st.sidebar if sidebar else st
        if header:
            if sidebar:
                container.markdown("---")
                container.header(header)
            else:
                container.header(header)

        # 如果没有传入业务线列表，从配置读取
        if business_lines is None:
            business_lines = self.get_config("business", "lines") or ["光谱设备/服务", "配液设备", "自动化项目"]

        config = self.get_config("cost") or {}
        current = dict(config.get("material_ratios_by_line", {}) or {})

        new_ratios: Dict[str, float] = {}
        for line in business_lines:
            key = f"cfg_cost_material_ratio_{self._safe_key(line)}"
            value = float(current.get(line, default_ratio))
            new_ratios[line] = float(
                container.slider(
                    f"{line} 物料比例",
                    0.0,
                    1.0,
                    value,
                    0.01,
                    key=key,
                )
            )

        if new_ratios != current:
            self.set_config("cost", "material_ratios_by_line", new_ratios)

        return new_ratios

    def render_tax_rate_ui(self, sidebar: bool = True, header: str = "🏛️ 税率配置") -> float:
        """渲染税率配置（自动持久化）"""
        container = st.sidebar if sidebar else st
        if header:
            if sidebar:
                container.markdown("---")
                container.header(header)
            else:
                container.header(header)

        config = self.get_config("cost") or {}
        current = float(config.get("tax_rate", 0.13))

        new_value = float(
            container.slider(
                "税率",
                0.0,
                0.5,
                current,
                0.01,
                help="增值税税率",
                key="cfg_cost_tax_rate",
            )
        )

        if new_value != current:
            self.set_config("cost", "tax_rate", new_value)

        return new_value

    def render_default_payment_stages_ui(self, sidebar: bool = True, header: str = "💳 付款比例配置") -> Dict[str, float]:
        """渲染默认付款阶段比例（自动持久化）"""
        container = st.sidebar if sidebar else st
        if header:
            if sidebar:
                container.markdown("---")
                container.header(header)
            else:
                container.header(header)

        cost_cfg = self.get_config("cost") or {}
        current = dict(cost_cfg.get("default_payment_stages", {}) or {})

        def _get(name: str, default: float) -> float:
            return float(current.get(name, default))

        col1, col2 = container.columns(2)
        first = col1.slider("首付款比例", 0, 100, int(_get("首付款比例", 50.0)), 1, key="cfg_payment_first")
        second = col2.slider("次付款比例", 0, 100, int(_get("次付款比例", 40.0)), 1, key="cfg_payment_second")
        col3, col4 = container.columns(2)
        final = col3.slider("尾款比例", 0, 100, int(_get("尾款比例", 0.0)), 1, key="cfg_payment_final")
        warranty = col4.slider("质保金比例", 0, 100, int(_get("质保金比例", 10.0)), 1, key="cfg_payment_warranty")

        new_value = {
            "首付款比例": float(first),
            "次付款比例": float(second),
            "尾款比例": float(final),
            "质保金比例": float(warranty),
        }

        if new_value != current:
            self.set_config("cost", "default_payment_stages", new_value)

        return new_value

    def render_month_range_ui(
        self,
        category: str,
        sidebar: bool = False,
        header: str = "📅 时间段筛选",
        year_range: Tuple[int, int] = (2024, 2027),
        default_start: str = "2025-01",
        default_end: str = "2025-12",
    ) -> Tuple[str, str]:
        """渲染月份范围选择（自动持久化）"""
        container = st.sidebar if sidebar else st
        if not sidebar:
            container.subheader(header)
        else:
            container.markdown("---")
            container.header(header)

        cfg = self.get_config(category) or {}
        current_start = str(cfg.get("start_month", default_start))
        current_end = str(cfg.get("end_month", default_end))

        options = [f"{y}-{m:02d}" for y in range(year_range[0], year_range[1] + 1) for m in range(1, 13)]

        col1, col2 = container.columns(2)
        start_idx = options.index(current_start) if current_start in options else options.index(default_start)
        end_idx = options.index(current_end) if current_end in options else options.index(default_end)

        start_month = col1.selectbox("开始月份", options=options, index=start_idx, key=f"cfg_{category}_start_month")
        end_month = col2.selectbox("结束月份", options=options, index=end_idx, key=f"cfg_{category}_end_month")

        # 自动修正：如果开始 > 结束，交换
        if start_month > end_month:
            start_month, end_month = end_month, start_month

        if start_month != current_start:
            self.set_config(category, "start_month", start_month)
        if end_month != current_end:
            self.set_config(category, "end_month", end_month)

        return start_month, end_month

    def render_cashflow_base_ui(self, sidebar: bool = True, header: str = "⚙️ 现金流配置") -> Dict[str, Any]:
        """渲染现金流基础配置（自动持久化）"""
        container = st.sidebar if sidebar else st
        if header:
            if sidebar:
                container.markdown("---")
                container.header(header)
            else:
                container.header(header)

        cfg = self.get_config("cashflow") or {}
        current_cash = float(cfg.get("current_cash", 100.0))
        months_ahead = int(cfg.get("months_ahead", 12))

        new_cash = float(container.number_input("当前现金余额 (万元)", min_value=0.0, value=current_cash, step=1.0, key="cfg_cashflow_current_cash"))
        new_months = int(container.number_input("预测月份数", min_value=1, max_value=60, value=months_ahead, step=1, key="cfg_cashflow_months_ahead"))

        if new_cash != current_cash:
            self.set_config("cashflow", "current_cash", new_cash)
        if new_months != months_ahead:
            self.set_config("cashflow", "months_ahead", new_months)

        return {"current_cash": new_cash, "months_ahead": new_months}

    def render_display_config_ui(self, sidebar: bool = True) -> Dict[str, Any]:
        """渲染显示配置UI"""
        if sidebar:
            st.sidebar.markdown("---")
            st.sidebar.header("🎨 显示配置")
        else:
            st.header("🎨 显示配置")

        container = st.sidebar if sidebar else st
        config = self.get_config("display")

        chart_height = container.number_input(
            "图表高度",
            min_value=200,
            max_value=800,
            value=int(config.get("chart_height", 400)),
            step=50,
            key="cfg_display_chart_height",
        )

        table_page_size = container.number_input(
            "表格分页大小",
            min_value=5,
            max_value=100,
            value=int(config.get("table_page_size", 10)),
            step=5,
            key="cfg_display_table_page_size",
        )

        show_empty_categories = container.checkbox(
            "显示空分类",
            value=bool(config.get("show_empty_categories", False)),
            key="cfg_display_show_empty_categories",
        )

        color_palette = container.selectbox(
            "配色方案",
            options=["plotly", "default", "pastel", "bold"],
            index=["plotly", "default", "pastel", "bold"].index(config.get("color_palette", "plotly")),
            key="cfg_display_color_palette",
        )

        if chart_height != config.get("chart_height"):
            self.set_config("display", "chart_height", chart_height)
        if table_page_size != config.get("table_page_size"):
            self.set_config("display", "table_page_size", table_page_size)
        if show_empty_categories != config.get("show_empty_categories"):
            self.set_config("display", "show_empty_categories", show_empty_categories)
        if color_palette != config.get("color_palette"):
            self.set_config("display", "color_palette", color_palette)

        return {
            "chart_height": chart_height,
            "table_page_size": table_page_size,
            "show_empty_categories": show_empty_categories,
            "color_palette": color_palette,
        }
    
    # -----------------------------
    # 便捷方法
    # -----------------------------
    def get_business_lines(self) -> List[str]:
        """获取业务线列表"""
        return self.get_config("business", "lines") or ["光谱设备/服务", "配液设备", "自动化项目"]
    
    def get_payment_defaults(self) -> Dict[str, float]:
        """获取默认付款比例"""
        return self.get_config("cost", "default_payment_stages") or {
            "首付款比例": 50.0,
            "次付款比例": 40.0,
            "尾款比例": 0.0,
            "质保金比例": 10.0,
        }


# 全局配置管理器实例
config_manager = ConfigManager()
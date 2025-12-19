# utils/config_ui.py - 配置 UI 渲染（Streamlit 层）
from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.config_manager import ConfigManager


class ConfigUI:
    """把配置相关的 Streamlit UI 渲染集中在这里，避免污染 core 层。"""

    @staticmethod
    def render_forecast_config_ui(cm: ConfigManager, sidebar: bool = True) -> Dict[str, Any]:
        """渲染预测配置 UI"""
        container = st.sidebar if sidebar else st
        if sidebar:
            st.sidebar.markdown("---")
            st.sidebar.markdown('<div class="cfg-section-title">🔮 预测配置</div>', unsafe_allow_html=True)
            st.sidebar.markdown('<div class="cfg-section-subtitle">影响收入预测与时间风险折扣</div>', unsafe_allow_html=True)
        else:
            st.markdown('### 🔮 预测配置')
            st.markdown('<div class="cfg-section-subtitle">影响收入预测与时间风险折扣</div>', unsafe_allow_html=True)

        config = cm.get_config("forecast") or {}

        decay_lambda = container.slider(
            "时间衰减系数 λ",
            min_value=0.01,
            max_value=0.1,
            value=float(config.get("decay_lambda", 0.0315)),
            step=0.0001,
            help="数值越大，时间风险越高",
        )

        base_date_offset = container.number_input(
            "基准日期偏移（天）",
            min_value=-365,
            max_value=365,
            value=int(config.get("base_date_offset", 0)),
            help="相对于今天的日期偏移",
        )

        months_ahead = container.slider(
            "预测月份数",
            min_value=6,
            max_value=24,
            value=int(config.get("months_ahead", 12)),
            step=1,
        )

        base_date = datetime.now() + timedelta(days=int(base_date_offset))

        # 仅当变化时写回（减少写盘）
        updates = {}
        if decay_lambda != config.get("decay_lambda"):
            updates["decay_lambda"] = decay_lambda
        if base_date_offset != config.get("base_date_offset"):
            updates["base_date_offset"] = int(base_date_offset)
        if months_ahead != config.get("months_ahead"):
            updates["months_ahead"] = int(months_ahead)
        if updates:
            cm.update_category("forecast", updates)

        return {
            "时间衰减系数": decay_lambda,
            "基准日期": base_date,
            "基准日期偏移": int(base_date_offset),
            "预测月份数": int(months_ahead),
        }

    @staticmethod
    def render_cost_config_ui(cm: ConfigManager, sidebar: bool = True) -> Dict[str, Any]:
        """渲染成本配置 UI"""
        container = st.sidebar if sidebar else st
        if sidebar:
            st.sidebar.markdown("---")
            st.sidebar.markdown('<div class="cfg-section-title">💰 成本配置</div>', unsafe_allow_html=True)
            st.sidebar.markdown('<div class="cfg-section-subtitle">控制材料/人工/其他成本的估算口径</div>', unsafe_allow_html=True)
        else:
            st.markdown('### 💰 成本配置')
            st.markdown('<div class="cfg-section-subtitle">控制材料/人工/其他成本的估算口径</div>', unsafe_allow_html=True)

        config = cm.get_config("cost") or {}

        material_rate = container.slider(
            "物料成本率",
            min_value=0.0,
            max_value=1.0,
            value=float(config.get("material_cost_rate", 0.3)),
            format="%.0f%%",
            help="物料成本占收入的比例",
        )

        labor_rate = container.slider(
            "人工成本率",
            min_value=0.0,
            max_value=1.0,
            value=float(config.get("labor_cost_rate", 0.4)),
            format="%.0f%%",
            help="人工成本占收入的比例",
        )

        admin_rate = container.slider(
            "行政成本率",
            min_value=0.0,
            max_value=1.0,
            value=float(config.get("admin_cost_rate", 0.15)),
            format="%.0f%%",
            help="费用支出占收入的比例",
        )

        updates = {}
        if material_rate != config.get("material_cost_rate"):
            updates["material_cost_rate"] = material_rate
        if labor_rate != config.get("labor_cost_rate"):
            updates["labor_cost_rate"] = labor_rate
        if admin_rate != config.get("admin_cost_rate"):
            updates["admin_cost_rate"] = admin_rate
        if updates:
            cm.update_category("cost", updates)

        return {
            "物料成本率": material_rate,
            "人工成本率": labor_rate,
            "行政成本率": admin_rate,
        }

    @staticmethod
    def render_payment_config_ui(
        cm: ConfigManager,
        df: Optional[pd.DataFrame] = None,
        sidebar: bool = True,
    ) -> Dict[str, Any]:
        """渲染付款配置 UI（默认付款比例）"""
        container = st.sidebar if sidebar else st
        if sidebar:
            st.sidebar.markdown("---")
            st.sidebar.markdown('<div class="cfg-section-title">💳 付款配置</div>', unsafe_allow_html=True)
            st.sidebar.markdown('<div class="cfg-section-subtitle">默认收款分期比例（可在项目层覆盖）</div>', unsafe_allow_html=True)
        else:
            st.markdown("### 💳 付款配置")
            st.markdown('<div class="cfg-section-subtitle">默认收款分期比例（可在项目层覆盖）</div>', unsafe_allow_html=True)

        config = cm.get_config("cost") or {}
        default_payment = config.get("default_payment_stages", {}) or {}

        col1, col2 = container.columns(2)
        first_payment = col1.number_input(
            "首付款比例(%)",
            min_value=0.0,
            max_value=100.0,
            value=float(default_payment.get("首付款比例", 50.0)),
            step=0.1,
        )
        second_payment = col2.number_input(
            "次付款比例(%)",
            min_value=0.0,
            max_value=100.0,
            value=float(default_payment.get("次付款比例", 40.0)),
            step=0.1,
        )

        col3, col4 = container.columns(2)
        final_payment = col3.number_input(
            "尾款比例(%)",
            min_value=0.0,
            max_value=100.0,
            value=float(default_payment.get("尾款比例", 0.0)),
            step=0.1,
        )
        retention_payment = col4.number_input(
            "质保金比例(%)",
            min_value=0.0,
            max_value=100.0,
            value=float(default_payment.get("质保金比例", 10.0)),
            step=0.1,
        )

        total_ratio = first_payment + second_payment + final_payment + retention_payment
        container.metric(
            "总比例",
            f"{total_ratio:.1f}%",
            delta=f"{total_ratio - 100:.1f}%" if abs(total_ratio - 100) > 0.1 else "",
            delta_color="inverse" if abs(total_ratio - 100) > 0.1 else "off",
        )

        payment_config = {
            "首付款比例": float(first_payment),
            "次付款比例": float(second_payment),
            "尾款比例": float(final_payment),
            "质保金比例": float(retention_payment),
        }

        if payment_config != default_payment:
            cm.set_config("cost", "default_payment_stages", payment_config)

        return payment_config

    @staticmethod
    def render_display_config_ui(cm: ConfigManager, sidebar: bool = True) -> None:
        """渲染显示配置 UI"""
        container = st.sidebar if sidebar else st
        if sidebar:
            st.sidebar.markdown("---")
            st.sidebar.markdown('<div class="cfg-section-title">🎨 显示配置</div>', unsafe_allow_html=True)
            st.sidebar.markdown('<div class="cfg-section-subtitle">图表与表格的显示偏好</div>', unsafe_allow_html=True)
        else:
            st.markdown("### 🎨 显示配置")
            st.markdown('<div class="cfg-section-subtitle">图表与表格的显示偏好</div>', unsafe_allow_html=True)

        config = cm.get_config("display") or {}

        chart_height = container.slider(
            "图表高度",
            min_value=200,
            max_value=800,
            value=int(config.get("chart_height", 400)),
            step=50,
        )

        options = [5, 10, 20, 50, 100]
        default_page_size = int(config.get("table_page_size", 10))
        idx = options.index(default_page_size) if default_page_size in options else 1
        table_page_size = container.selectbox("表格分页大小", options=options, index=idx)

        color_palettes = ["plotly", "colorblind", "pastel", "antique", "bold", "safe"]
        default_palette = str(config.get("color_palette", "plotly"))
        palette_idx = color_palettes.index(default_palette) if default_palette in color_palettes else 0
        color_palette = container.selectbox("配色方案", options=color_palettes, index=palette_idx)

        updates = {}
        if chart_height != config.get("chart_height"):
            updates["chart_height"] = int(chart_height)
        if table_page_size != config.get("table_page_size"):
            updates["table_page_size"] = int(table_page_size)
        if color_palette != config.get("color_palette"):
            updates["color_palette"] = str(color_palette)
        if updates:
            cm.update_category("display", updates)

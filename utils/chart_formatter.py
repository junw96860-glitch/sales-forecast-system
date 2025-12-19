"""Chart formatting helpers used across the Streamlit dashboards."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.date_utils import DateUtils


class ChartFormatter:
    """Central place for Plotly styling and small helper utilities."""

    COLOR_PALETTE: Dict[str, List[str]] = {
        # Primary (enterprise): sky / green / amber / red / violet / teal
        "primary": ["#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6"],
        # Plotly default-like
        "plotly": ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"],
        # Okabe-Ito (colorblind safe)
        "colorblind": ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"],
        # Pastel
        "pastel": ["#8ac6d1", "#ffd1dc", "#ffe7a0", "#c7ceea", "#b5ead7", "#ffdac1"],
        # Antique / muted
        "antique": ["#4E79A7", "#59A14F", "#F28E2B", "#E15759", "#B07AA1", "#76B7B2"],
        # Bold / high contrast
        "bold": ["#111827", "#2563eb", "#16a34a", "#f97316", "#dc2626", "#7c3aed"],
        # Safe neutrals + accents
        "safe": ["#0ea5e9", "#334155", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6"],
    }

    FONT_SETTINGS = {
        "family": 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        "color": "#0f172a",
        "size": 12,
    }

    BASE_LAYOUT = {
        "template": "plotly_white",
        "hovermode": "x unified",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "margin": {"l": 48, "r": 28, "t": 58, "b": 54},
        "font": FONT_SETTINGS,
        "legend": {"orientation": "h", "yanchor": "bottom", "y": -0.28, "x": 0.0, "xanchor": "left"},
        "xaxis": {
            "showgrid": True,
            "gridcolor": "rgba(148,163,184,.22)",
            "zeroline": False,
            "showline": True,
            "linecolor": "rgba(148,163,184,.35)",
            "tickfont": {"size": 11},
        },
        "yaxis": {
            "showgrid": True,
            "gridcolor": "rgba(148,163,184,.22)",
            "zeroline": False,
            "showline": True,
            "linecolor": "rgba(148,163,184,.35)",
            "tickfont": {"size": 11},
        },
    }

    # ------------------------------------------------------------------ #
    # Generic helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_palette(name: str) -> List[str]:
        return ChartFormatter.COLOR_PALETTE.get(
            name, ChartFormatter.COLOR_PALETTE["primary"]
        )

    @staticmethod
    def _ensure_columns(df: pd.DataFrame, required: List[str]) -> bool:
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.warning(f"缺少绘图所需列: {', '.join(missing)}")
            return False
        return True

    @staticmethod
    def _create_title(text: str) -> Dict[str, Any]:
        return {"text": text, "x": 0.02, "xanchor": "left", "font": {"size": 18}}

    # ------------------------------------------------------------------ #
    # Chart factories
    # ------------------------------------------------------------------ #
    @staticmethod
    def create_monthly_trend_chart(
        df: pd.DataFrame,
        month_column: str,
        value_column: str,
        title: str,
        value_label: str = "数值",
        palette: str = "primary",
    ) -> go.Figure:
        if not ChartFormatter._ensure_columns(df, [month_column, value_column]):
            return go.Figure()

        formatted = df.copy()
        formatted["_display_month"] = formatted[month_column].apply(
            lambda value: DateUtils.format_month_display(str(value))
        )

        fig = go.Figure(
            [
                go.Scatter(
                    x=formatted["_display_month"],
                    y=formatted[value_column],
                    mode="lines+markers",
                    name=value_label,
                    line={"color": ChartFormatter._resolve_palette(palette)[0], "width": 3},
                    marker={"size": 7},
                    hovertemplate=f"{value_label}: %{{y:.2f}}<br>%{{x}}<extra></extra>",
                )
            ]
        )

        fig.update_layout(
            ChartFormatter.BASE_LAYOUT,
            title=ChartFormatter._create_title(title),
            yaxis_title=value_label,
            xaxis_title="月份",
        )
        fig.update_xaxes(tickangle=-35)
        return fig

    @staticmethod
    def create_business_split_chart(
        df: pd.DataFrame,
        business_col: str,
        value_col: str,
        title: str,
        chart_type: str = "pie",
        palette: str = "primary",
    ) -> go.Figure:
        if not ChartFormatter._ensure_columns(df, [business_col, value_col]):
            return go.Figure()

        summary = df.groupby(business_col)[value_col].sum().reset_index()
        colors = ChartFormatter._resolve_palette(palette)

        if chart_type == "bar":
            fig = px.bar(
                summary,
                x=business_col,
                y=value_col,
                color=business_col,
                color_discrete_sequence=colors,
                text=value_col,
            )
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        else:
            fig = px.pie(
                summary,
                values=value_col,
                names=business_col,
                hole=0.4 if chart_type == "donut" else 0,
                color_discrete_sequence=colors,
            )

        fig.update_layout(
            ChartFormatter.BASE_LAYOUT,
            title=ChartFormatter._create_title(title),
        )
        return fig

    # ------------------------------------------------------------------ #
    # UI helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def create_interactive_controls(
        options: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        selections: Dict[str, Any] = {}
        if not options:
            return selections

        for key, values in options.items():
            if not values:
                continue
            label = key.replace("_", " ").title()
            selections[key] = st.selectbox(
                label, options=values, key=f"chart_ctrl_{key}"
            )
        return selections

    @staticmethod
    def render_data_quality_badge(df: pd.DataFrame) -> None:
        """Render a lightweight data quality badge (UI only)."""

        if df.empty:
            st.info("暂无数据用于评估质量")
            return

        completeness = 1 - df.isna().mean().mean()

        def _make_hashable(v):
            if isinstance(v, (list, dict, set, tuple)):
                return str(v)
            return v

        try:
            safe_df = df.applymap(_make_hashable)
            duplicates = 1 - safe_df.duplicated().mean()
        except Exception:
            duplicates = 1.0

        score = max(
            0,
            min(100, (completeness * 0.7 + duplicates * 0.3) * 100),
        )

        color = (
            "#52c41a"
            if score >= 80
            else "#faad14"
            if score >= 60
            else "#ff4d4f"
        )

        st.markdown(
            f"""
            <div style="
                display:inline-flex;
                align-items:center;
                padding:6px 12px;
                border-radius:20px;
                background-color:{color}1A;
                color:{color};
                font-weight:600;
            ">
                📊 数据质量评分：{score:.0f}分
            </div>
            """,
            unsafe_allow_html=True,
        )


def inject_plotly_css() -> None:
    """Inject small CSS tweaks once per session."""
    st.markdown(
        """
        <style>
        .js-plotly-plot .plotly .hoverlayer .hovertext {
            border-radius: 4px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }
        </style>

<style>
/* Plotly UI polish (UI-only) */
.js-plotly-plot .plotly .hoverlayer .hovertext{
  border-radius: 10px !important;
  box-shadow: 0 10px 24px rgba(2, 8, 23, .16) !important;
}
.js-plotly-plot .plotly .modebar{
  background: rgba(255,255,255,.72) !important;
  backdrop-filter: blur(6px);
  border-radius: 12px !important;
  box-shadow: 0 6px 18px rgba(2, 8, 23, .10) !important;
  padding: 4px 6px !important;
}
.js-plotly-plot .plotly .modebar-btn{
  border-radius: 10px !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

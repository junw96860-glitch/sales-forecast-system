# pages/1_📊_数据看板.py
"""
数据看板 - 销售预测系统核心概览

功能：
- 关键指标展示（总收入、项目数、成单率）
- 业务线收入分布
- 月度收入趋势
- 项目列表预览
"""

import streamlit as st

# ⚠️ 页面配置必须是第一个 Streamlit 命令
st.set_page_config(page_title="数据看板", layout="wide")

# 认证和权限检查
from utils.page_init import init_page
init_page()

# 其他导入
from data.data_manager import data_manager
data_manager.set_state_store(st.session_state)

import pandas as pd
from utils.chart_formatter import ChartFormatter, inject_plotly_css
from utils.display_helper import DisplayHelper


# ----------------------------
# 页面标题
# ----------------------------
st.title("📊 数据看板")
st.caption("销售预测与预算系统的核心概览，所有金额基于纠偏后口径。")

inject_plotly_css()
DisplayHelper.apply_global_styles()


# ----------------------------
# 加载数据
# ----------------------------
with st.spinner("🔄 正在加载销售数据..."):
    df = data_manager.get_active_data()

if df is None or df.empty:
    st.warning("⚠️ 暂无数据。确保飞书表格中有记录，并检查应用权限。")
    st.stop()

if "_final_amount" not in df.columns:
    st.error("❌ 数据未包含 _final_amount 列。请检查 data_manager 标准化流程。")
    st.stop()

df = df.copy()


# ----------------------------
# 核心指标
# ----------------------------
total_projects = len(df)
total_revenue_wan = pd.to_numeric(df["_final_amount"], errors="coerce").fillna(0).sum()

avg_win_rate_display = "--"
if "_成单率_num" in df.columns:
    rate = pd.to_numeric(df["_成单率_num"], errors="coerce")
    if rate.notna().any():
        avg_win_rate_display = f"{rate.mean():.1f}%"

st.success(f"✅ 成功加载 {total_projects} 条项目记录")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("总收入（万元）", f"{total_revenue_wan:,.2f}")
with c2:
    st.metric("项目总数", f"{total_projects}")
with c3:
    st.metric("平均成单率", avg_win_rate_display)

st.divider()


# ----------------------------
# 业务线收入分布
# ----------------------------
if "业务线" in df.columns and df["业务线"].notna().any():
    st.subheader("📈 各业务线收入贡献（万元）")

    chart_type = st.radio(
        "展示方式",
        options=["donut", "pie", "bar"],
        index=0,
        horizontal=True,
        key="dash_business_split_type",
    )

    fig_split = ChartFormatter.create_business_split_chart(
        df=df,
        business_col="业务线",
        value_col="_final_amount",
        title="各业务线收入贡献（万元）",
        chart_type=chart_type,
        palette="primary",
    )
    st.plotly_chart(fig_split, use_container_width=True)

st.divider()


# ----------------------------
# 月度收入趋势
# ----------------------------
st.subheader("📅 月度收入预测趋势（按交付时间，万元）")

if "_交付月份" not in df.columns:
    if "交付时间" in df.columns:
        dt = pd.to_datetime(df["交付时间"], errors="coerce")
        df["_交付月份"] = dt.dt.to_period("M").astype(str)
    else:
        df["_交付月份"] = pd.NA

monthly_base = df[
    df["_交付月份"].notna()
    & (df["_交付月份"].astype(str).str.strip() != "")
    & (df["_交付月份"].astype(str).str.lower() != "nat")
].copy()

if monthly_base.empty:
    st.info("交付时间为空或无法解析，暂无法绘制月度趋势。")
else:
    monthly_rev = (
        monthly_base.groupby("_交付月份")["_final_amount"]
        .sum()
        .reset_index()
        .sort_values("_交付月份")
    )

    fig_month = ChartFormatter.create_monthly_trend_chart(
        df=monthly_rev,
        month_column="_交付月份",
        value_column="_final_amount",
        title="月度收入预测趋势（万元）",
        value_label="月度收入",
        palette="primary",
    )
    st.plotly_chart(fig_month, use_container_width=True)

st.divider()


# ----------------------------
# 项目列表预览
# ----------------------------
st.subheader(f"📋 项目列表预览（共 {len(df)} 条记录）")

RAW_COLUMNS_WHITELIST = [
    "客户", "业务线", "金额", "成单率",
    "开始时间", "预计截止时间", "交付时间",
    "当前进展", "主要描述", "交付内容", "数量",
    "人工纠偏金额",
]

display_cols = [c for c in RAW_COLUMNS_WHITELIST if c in df.columns]
preview_df = df[display_cols].copy()

# 日期格式化
for col in ["开始时间", "预计截止时间", "交付时间"]:
    if col in preview_df.columns:
        preview_df[col] = pd.to_datetime(preview_df[col], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")

# 金额格式化
if "金额" in preview_df.columns:
    s = preview_df["金额"].astype(str)
    s = (
        s.str.replace(",", "", regex=False)
         .str.replace("¥", "", regex=False)
         .str.replace("￥", "", regex=False)
         .str.replace("万元", "", regex=False)
         .str.replace("万", "", regex=False)
         .str.replace(r"\s+", "", regex=True)
    )
    amt = pd.to_numeric(s, errors="coerce")
    preview_df["金额"] = amt.apply(lambda x: "" if pd.isna(x) else f"{x:,.2f}")

# 列表/字典转字符串
for col in ["交付内容", "当前进展"]:
    if col in preview_df.columns:
        preview_df[col] = preview_df[col].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else ("" if pd.isna(x) else str(x))
        )

# 渲染表格
DisplayHelper.render_aggrid_table(
    preview_df,
    key="dashboard_project_list",
    page_size=20,
    height=600,
    enable_selection=True,
    enable_filtering=True,
    enable_sorting=True,
    theme="alpine",
    return_mode="filtered",
)

# 下载功能
with st.expander("📥 下载当前展示数据", expanded=False):
    DisplayHelper.create_download_button(
        dataframe=preview_df,
        filename="dashboard_project_preview",
        label="📥 下载 CSV",
        file_format="csv",
        include_index=False,
    )

# pages/7_📋_项目明细.py
"""
项目明细管理页面 - 优化版 V3

优化：
1. 性能优化 - 使用缓存，减少重复计算
2. 业务繁忙度 - 简化显示，去掉建议
3. 工时统计 - 突出项目分类维度
"""

# === 认证检查 ===
from utils.page_init import init_page
init_page()

# === 导入 ===
import streamlit as st
from data.data_manager import data_manager
data_manager.set_state_store(st.session_state)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from utils.chart_formatter import inject_plotly_css
from utils.display_helper import DisplayHelper

# === 飞书客户端 ===
from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_APP_TOKEN,
    WORKTIME_TABLE_ID,
)
from data.feishu_client import FeishuClient

st.set_page_config(page_title="项目明细", layout="wide")
st.title("📋 项目明细")

inject_plotly_css()
DisplayHelper.apply_global_styles()


# ============================================================
# 缓存的飞书客户端
# ============================================================
@st.cache_resource
def get_feishu_client():
    return FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN)


# ============================================================
# 缓存的工时数据加载
# ============================================================
@st.cache_data(ttl=300)  # 缓存5分钟
def load_worktime_data(_client, table_id: str) -> pd.DataFrame:
    """加载工时数据（带缓存）"""
    try:
        records = _client.get_records(table_id)
        if not records:
            return pd.DataFrame()
    except Exception as e:
        st.warning(f"加载工时数据失败: {e}")
        return pd.DataFrame()
    
    rows = []
    for item in records:
        if item is None:
            continue
        fields = item.get("fields", {}) or {}
        
        # 处理月份（飞书时间戳是毫秒，需要转换为中国时区）
        month_val = fields.get("月份", "")
        if isinstance(month_val, (int, float)):
            try:
                # 飞书时间戳是毫秒，转换为北京时间（UTC+8）
                from datetime import timezone, timedelta
                utc_time = pd.to_datetime(month_val, unit="ms")
                beijing_time = utc_time + timedelta(hours=8)
                month_val = beijing_time.strftime("%Y-%m")
            except:
                month_val = ""
        elif isinstance(month_val, str) and len(month_val) >= 7:
            month_val = month_val[:7]
        
        rows.append({
            "人员": fields.get("人员", ""),
            "月份": month_val,
            "分类": fields.get("分类", ""),
            "项目": fields.get("项目", ""),
            "工时天数": float(fields.get("工时天数", 0) or 0),
        })
    
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ============================================================
# 缓存的项目数据加载
# ============================================================
@st.cache_data(ttl=300)
def load_project_summary() -> dict:
    """加载项目汇总数据（带缓存）"""
    df = data_manager.get_active_data()
    
    if df is None or df.empty:
        return {"total": 0, "by_business": pd.DataFrame(), "by_month": pd.DataFrame()}
    
    result = {"total": len(df)}
    
    # 按业务线汇总
    if "业务线" in df.columns:
        result["by_business"] = df.groupby("业务线").size().reset_index(name="项目数量")
        result["by_business"] = result["by_business"].sort_values("项目数量", ascending=False)
    else:
        result["by_business"] = pd.DataFrame()
    
    # 按月份汇总
    if "交付时间" in df.columns:
        df["_month"] = pd.to_datetime(df["交付时间"], errors="coerce").dt.to_period("M").astype(str)
    elif "预计截止时间" in df.columns:
        df["_month"] = pd.to_datetime(df["预计截止时间"], errors="coerce").dt.to_period("M").astype(str)
    else:
        df["_month"] = pd.NA
    
    valid_df = df[df["_month"].notna() & (df["_month"].astype(str) != "NaT")]
    if not valid_df.empty:
        result["by_month"] = valid_df.groupby("_month").size().reset_index(name="项目数量")
        result["by_month"] = result["by_month"].sort_values("_month")
        result["by_month"].columns = ["月份", "项目数量"]
    else:
        result["by_month"] = pd.DataFrame()
    
    return result


# ============================================================
# 页面布局
# ============================================================
tab1, tab2 = st.tabs(["📊 业务繁忙度", "⏱️ 工时统计"])


# ============================================================
# Tab 1: 业务繁忙度（简化版）
# ============================================================
with tab1:
    st.header("📊 业务繁忙度")
    
    # 加载数据
    project_data = load_project_summary()
    
    if project_data["total"] == 0:
        st.info("暂无项目数据")
    else:
        # 核心指标
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("项目总数", f"{project_data['total']}")
        with col2:
            if not project_data["by_business"].empty:
                st.metric("业务线数", f"{len(project_data['by_business'])}")
        with col3:
            current_month = datetime.date.today().strftime("%Y-%m")
            if not project_data["by_month"].empty:
                this_month = project_data["by_month"][project_data["by_month"]["月份"] == current_month]
                count = this_month["项目数量"].sum() if not this_month.empty else 0
                st.metric("本月交付", f"{count}")
        
        st.divider()
        
        # 业务线分布
        if not project_data["by_business"].empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.pie(
                    project_data["by_business"], 
                    values="项目数量", 
                    names="业务线",
                    title="业务线项目占比",
                    hole=0.4
                )
                fig.update_layout(height=350, margin=dict(t=40, b=20, l=20, r=20))
                fig.update_traces(textposition="outside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(
                    project_data["by_business"],
                    x="业务线",
                    y="项目数量",
                    title="各业务线项目数量",
                    color="业务线",
                    text="项目数量"
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(height=350, showlegend=False, margin=dict(t=40, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
        
        # 月度趋势
        if not project_data["by_month"].empty:
            st.subheader("📅 月度项目趋势")
            fig = px.bar(
                project_data["by_month"],
                x="月份",
                y="项目数量",
                text="项目数量"
            )
            fig.update_traces(textposition="outside", marker_color="#6366f1")
            fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Tab 2: 工时统计（以项目为核心）
# ============================================================
with tab2:
    st.header("⏱️ 工时统计")
    
    # 刷新按钮
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 刷新", key="refresh_wt"):
            st.cache_data.clear()
            st.rerun()
    
    # 加载数据
    worktime_df = load_worktime_data(get_feishu_client(), WORKTIME_TABLE_ID)
    
    if worktime_df.empty:
        st.warning("⚠️ 暂无工时数据")
        st.info(f"飞书表格ID: `{WORKTIME_TABLE_ID}`")
    else:
        # 核心指标
        total_hours = worktime_df["工时天数"].sum()
        total_persons = worktime_df["人员"].nunique()
        total_projects = worktime_df["项目"].nunique()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("总工时（天）", f"{total_hours:,.1f}")
        col2.metric("参与人员", f"{total_persons}")
        col3.metric("涉及项目", f"{total_projects}")
        
        st.divider()
        
        # 筛选器
        col1, col2, col3 = st.columns(3)
        
        with col1:
            month_opts = ["全部"] + sorted(worktime_df["月份"].dropna().unique().tolist(), reverse=True)
            sel_month = st.selectbox("月份", month_opts, key="wt_month")
        
        with col2:
            person_opts = ["全部"] + sorted(worktime_df["人员"].dropna().unique().tolist())
            sel_person = st.selectbox("人员", person_opts, key="wt_person")
        
        with col3:
            project_opts = ["全部"] + sorted(worktime_df["项目"].dropna().unique().tolist())
            sel_project = st.selectbox("项目", project_opts, key="wt_project")
        
        # 应用筛选
        filtered = worktime_df.copy()
        if sel_month != "全部":
            filtered = filtered[filtered["月份"] == sel_month]
        if sel_person != "全部":
            filtered = filtered[filtered["人员"] == sel_person]
        if sel_project != "全部":
            filtered = filtered[filtered["项目"] == sel_project]
        
        if filtered.empty:
            st.info("无匹配数据")
        else:
            st.divider()
            
            # ========== 项目工时排行（核心）==========
            st.subheader("📋 项目工时排行")
            
            proj_summary = filtered.groupby("项目").agg({
                "工时天数": "sum",
                "人员": "nunique"
            }).reset_index()
            proj_summary.columns = ["项目", "总工时", "人员数"]
            proj_summary = proj_summary.sort_values("总工时", ascending=False)
            
            # 项目工时柱状图（横向，按工时排序）
            fig = px.bar(
                proj_summary.head(15),  # 显示前15个项目
                y="项目",
                x="总工时",
                orientation="h",
                text="总工时",
                color="总工时",
                color_continuous_scale="Blues"
            )
            fig.update_traces(textposition="outside", texttemplate="%{text:.1f}")
            fig.update_layout(
                height=max(300, min(len(proj_summary), 15) * 40),
                margin=dict(t=20, b=20, l=20, r=20),
                showlegend=False,
                coloraxis_showscale=False,
                yaxis=dict(autorange="reversed")  # 工时最多的在上面
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 项目明细表
            st.dataframe(
                proj_summary.style.format({"总工时": "{:.1f}"}),
                use_container_width=True,
                hide_index=True
            )
            
            st.divider()
            
            # ========== 人员工时统计 ==========
            st.subheader("👥 人员工时统计")
            
            person_summary = filtered.groupby("人员").agg({
                "工时天数": "sum",
                "项目": "nunique"
            }).reset_index()
            person_summary.columns = ["人员", "总工时", "项目数"]
            person_summary = person_summary.sort_values("总工时", ascending=False)
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                fig = px.pie(
                    person_summary,
                    values="总工时",
                    names="人员",
                    title="人员工时占比",
                    hole=0.4
                )
                fig.update_layout(height=300, margin=dict(t=40, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    person_summary.style.format({"总工时": "{:.1f}"}),
                    use_container_width=True,
                    hide_index=True,
                    height=280
                )
            
            st.divider()
            
            # ========== 项目-人员明细 ==========
            with st.expander("📋 项目-人员明细"):
                detail = filtered.groupby(["项目", "人员"]).agg({
                    "工时天数": "sum"
                }).reset_index()
                detail.columns = ["项目", "人员", "工时天数"]
                detail = detail.sort_values(["项目", "工时天数"], ascending=[True, False])
                
                st.dataframe(
                    detail.style.format({"工时天数": "{:.1f}"}),
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
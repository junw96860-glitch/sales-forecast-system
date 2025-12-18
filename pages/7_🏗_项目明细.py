# pages/7_📋_项目明细.py
"""
项目明细管理页面 - 优化版 V4

优化：
1. 性能优化 - 使用缓存，减少重复计算
2. 业务繁忙度 - 简化显示，去掉建议
3. 工时统计 - 突出项目分类维度
4. 新增：订单现金流统计
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
from datetime import timezone, timedelta
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

# 订单现金流表格ID（需要在config.py中添加）
try:
    from config import ORDER_CASHFLOW_TABLE_ID
except ImportError:
    ORDER_CASHFLOW_TABLE_ID = "tblMKBm4yg1tZc9W"  # 默认值

st.set_page_config(page_title="项目明细", layout="wide")
st.title("📋 项目明细")

inject_plotly_css()
DisplayHelper.apply_global_styles()

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


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
# 缓存的订单现金流数据加载
# ============================================================
@st.cache_data(ttl=300)
def load_order_cashflow_data(_client, table_id: str) -> pd.DataFrame:
    """加载订单现金流数据（带缓存）"""
    try:
        records = _client.get_records(table_id)
        if not records:
            return pd.DataFrame()
    except Exception as e:
        st.warning(f"加载订单现金流数据失败: {e}")
        return pd.DataFrame()
    
    rows = []
    for item in records:
        if item is None:
            continue
        fields = item.get("fields", {}) or {}
        
        # 处理日期字段
        order_date = fields.get("订单确认年份", "")
        if isinstance(order_date, (int, float)):
            try:
                utc_time = pd.to_datetime(order_date, unit="ms")
                beijing_time = utc_time + timedelta(hours=8)
                order_date = beijing_time.strftime("%Y-%m-%d")
            except:
                order_date = ""
        
        # 处理金额字段（可能是空字符串或None）
        def parse_amount(val):
            if val is None or val == "":
                return 0.0
            try:
                return float(val)
            except:
                return 0.0
        
        rows.append({
            "销售收入编号": fields.get("销售收入编号", ""),
            "订单确认年份": order_date,
            "客户名称": fields.get("客户名称", ""),
            "销售类型": fields.get("销售类型", ""),
            "产品名称": fields.get("产品名称", ""),
            "是否交付": fields.get("是否交付", ""),
            "总金额": parse_amount(fields.get("总金额", 0)),
            "回款金额": parse_amount(fields.get("回款金额", 0)),
            "未回款金额": parse_amount(fields.get("未回款金额", 0)),
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
tab1, tab2, tab3 = st.tabs(["📊 业务繁忙度", "⏱️ 工时统计", "💰 订单现金流"])


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
            current_month = datetime.datetime.now(BEIJING_TZ).strftime("%Y-%m")
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


# ============================================================
# Tab 3: 订单现金流
# ============================================================
with tab3:
    st.header("💰 订单现金流")
    
    # 刷新按钮
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 刷新", key="refresh_cashflow"):
            st.cache_data.clear()
            st.rerun()
    
    # 加载数据
    cashflow_df = load_order_cashflow_data(get_feishu_client(), ORDER_CASHFLOW_TABLE_ID)
    
    if cashflow_df.empty:
        st.warning("⚠️ 暂无订单现金流数据")
        st.info(f"飞书表格ID: `{ORDER_CASHFLOW_TABLE_ID}`")
    else:
        # ========== 核心指标 ==========
        total_amount = cashflow_df["总金额"].sum()
        total_received = cashflow_df["回款金额"].sum()
        total_pending = cashflow_df["未回款金额"].sum()
        receive_rate = (total_received / total_amount * 100) if total_amount > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("订单总金额", f"¥{total_amount:,.2f}")
        col2.metric("已回款金额", f"¥{total_received:,.2f}")
        col3.metric("未回款金额", f"¥{total_pending:,.2f}", 
                   delta=f"-{total_pending/total_amount*100:.1f}%" if total_amount > 0 else "0%",
                   delta_color="inverse")
        col4.metric("回款率", f"{receive_rate:.1f}%")
        
        st.divider()
        
        # ========== 筛选器 ==========
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # 按年份筛选
            cashflow_df["_year"] = pd.to_datetime(cashflow_df["订单确认年份"], errors="coerce").dt.year
            year_opts = ["全部"] + sorted([str(int(y)) for y in cashflow_df["_year"].dropna().unique()], reverse=True)
            sel_year = st.selectbox("年份", year_opts, key="cf_year")
        
        with col2:
            # 按交付状态筛选
            delivery_opts = ["全部"] + cashflow_df["是否交付"].dropna().unique().tolist()
            sel_delivery = st.selectbox("交付状态", delivery_opts, key="cf_delivery")
        
        with col3:
            # 按销售类型筛选
            type_opts = ["全部"] + sorted(cashflow_df["销售类型"].dropna().unique().tolist())
            sel_type = st.selectbox("销售类型", type_opts, key="cf_type")
        
        with col4:
            # 按回款状态筛选
            payment_opts = ["全部", "已全部回款", "部分回款", "未回款"]
            sel_payment = st.selectbox("回款状态", payment_opts, key="cf_payment")
        
        # 应用筛选
        filtered_cf = cashflow_df.copy()
        if sel_year != "全部":
            filtered_cf = filtered_cf[filtered_cf["_year"] == int(sel_year)]
        if sel_delivery != "全部":
            filtered_cf = filtered_cf[filtered_cf["是否交付"] == sel_delivery]
        if sel_type != "全部":
            filtered_cf = filtered_cf[filtered_cf["销售类型"] == sel_type]
        if sel_payment != "全部":
            if sel_payment == "已全部回款":
                filtered_cf = filtered_cf[filtered_cf["未回款金额"] <= 0.01]
            elif sel_payment == "部分回款":
                filtered_cf = filtered_cf[(filtered_cf["回款金额"] > 0) & (filtered_cf["未回款金额"] > 0.01)]
            elif sel_payment == "未回款":
                filtered_cf = filtered_cf[filtered_cf["回款金额"] <= 0.01]
        
        if filtered_cf.empty:
            st.info("无匹配数据")
        else:
            # 筛选后的汇总
            f_total = filtered_cf["总金额"].sum()
            f_received = filtered_cf["回款金额"].sum()
            f_pending = filtered_cf["未回款金额"].sum()
            f_rate = (f_received / f_total * 100) if f_total > 0 else 0
            
            st.markdown(f"**筛选结果：** {len(filtered_cf)} 条订单，总金额 ¥{f_total:,.2f}，已回款 ¥{f_received:,.2f}，回款率 {f_rate:.1f}%")
            
            st.divider()
            
            # ========== 图表分析 ==========
            col1, col2 = st.columns(2)
            
            with col1:
                # 回款状态分布
                st.subheader("📊 回款状态分布")
                payment_data = pd.DataFrame({
                    "状态": ["已回款", "未回款"],
                    "金额": [f_received, f_pending]
                })
                fig = px.pie(
                    payment_data, 
                    values="金额", 
                    names="状态",
                    hole=0.4,
                    color="状态",
                    color_discrete_map={"已回款": "#10b981", "未回款": "#f43f5e"}
                )
                fig.update_traces(
                    textposition="inside", 
                    textinfo="percent+label",
                    hovertemplate="%{label}<br>¥%{value:,.2f}<br>占比: %{percent}"
                )
                fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # 按销售类型分布
                st.subheader("📊 销售类型分布")
                type_summary = filtered_cf.groupby("销售类型").agg({
                    "总金额": "sum",
                    "回款金额": "sum"
                }).reset_index()
                type_summary["回款率"] = (type_summary["回款金额"] / type_summary["总金额"] * 100).round(1)
                type_summary = type_summary.sort_values("总金额", ascending=True)
                
                fig = px.bar(
                    type_summary,
                    y="销售类型",
                    x="总金额",
                    orientation="h",
                    text="总金额",
                    color="回款率",
                    color_continuous_scale="RdYlGn"
                )
                fig.update_traces(texttemplate="¥%{text:,.0f}", textposition="outside")
                fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            
            # ========== 客户未回款排行 ==========
            st.subheader("🔴 未回款客户排行（TOP 10）")
            
            pending_by_customer = filtered_cf[filtered_cf["未回款金额"] > 0.01].groupby("客户名称").agg({
                "未回款金额": "sum",
                "总金额": "sum"
            }).reset_index()
            pending_by_customer["回款率"] = ((pending_by_customer["总金额"] - pending_by_customer["未回款金额"]) / pending_by_customer["总金额"] * 100).round(1)
            pending_by_customer = pending_by_customer.sort_values("未回款金额", ascending=False).head(10)
            
            if not pending_by_customer.empty:
                fig = px.bar(
                    pending_by_customer,
                    y="客户名称",
                    x="未回款金额",
                    orientation="h",
                    text="未回款金额",
                    color="回款率",
                    color_continuous_scale="RdYlGn"
                )
                fig.update_traces(texttemplate="¥%{text:,.0f}", textposition="outside")
                fig.update_layout(
                    height=max(250, len(pending_by_customer) * 35),
                    margin=dict(t=20, b=20, l=20, r=20),
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("🎉 所有订单已全部回款！")
            
            st.divider()
            
            # ========== 订单明细表 ==========
            st.subheader("📋 订单明细")
            
            # 准备显示数据
            display_cf = filtered_cf[[
                "销售收入编号", "订单确认年份", "客户名称", "销售类型", 
                "产品名称", "是否交付", "总金额", "回款金额", "未回款金额"
            ]].copy()
            
            # 计算回款率
            display_cf["回款率"] = (display_cf["回款金额"] / display_cf["总金额"] * 100).fillna(0).round(1)
            
            # 排序：未回款金额从高到低
            display_cf = display_cf.sort_values("未回款金额", ascending=False)
            
            st.dataframe(
                display_cf,
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config={
                    "总金额": st.column_config.NumberColumn("总金额", format="¥%.2f"),
                    "回款金额": st.column_config.NumberColumn("回款金额", format="¥%.2f"),
                    "未回款金额": st.column_config.NumberColumn("未回款金额", format="¥%.2f"),
                    "回款率": st.column_config.ProgressColumn(
                        "回款率",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100
                    ),
                }
            )
            
            # ========== 导出功能 ==========
            st.divider()
            col1, col2 = st.columns([1, 4])
            with col1:
                csv_data = display_cf.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 导出CSV",
                    data=csv_data,
                    file_name=f"订单现金流_{datetime.datetime.now(BEIJING_TZ).strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

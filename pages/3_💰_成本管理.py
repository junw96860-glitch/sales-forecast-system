# pages/3_💰_Cost_Management.py
"""
成本管理页面 - 优化版 v3
修复：
1. 物料成本项目数量统计问题
2. 费用支出图表与筛选器联动
"""

from utils.page_init import init_page
init_page()

import streamlit as st
from data.data_manager import data_manager
data_manager.set_state_store(st.session_state)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from dateutil.relativedelta import relativedelta
import json
from core.cost_calculator import CostCalculator
from utils.chart_formatter import inject_plotly_css
from utils.display_helper import DisplayHelper
from data.cost_data_service import cost_data_service

st.set_page_config(page_title="成本管理", layout="wide")
st.title("💰 成本管理")
st.caption("物料/人工/费用/税赋的配置、管理与分析汇总。") 
inject_plotly_css()
DisplayHelper.apply_global_styles()

cost_categories = cost_data_service.get_cost_categories()

from core.config_manager import config_manager

BUSINESS_LINES = ["光谱设备/服务", "配液设备", "自动化项目"]

material_ratios = config_manager.render_material_ratios_ui(
    BUSINESS_LINES, sidebar=True, header="⚙️ 成本配置", default_ratio=0.30)

tax_rate = config_manager.render_tax_rate_ui(sidebar=True, header="")

# 时间段选择器
st.sidebar.divider()
st.sidebar.subheader("📅 统计时间段")
default_start = datetime.date(2025, 12, 31)
default_end = datetime.date(2026, 12, 31)
analysis_start = st.sidebar.date_input("开始日期", value=default_start, key="cost_analysis_start")
analysis_end = st.sidebar.date_input("结束日期", value=default_end, key="cost_analysis_end")
analysis_months = (analysis_end.year - analysis_start.year) * 12 + (analysis_end.month - analysis_start.month) + 1
st.sidebar.caption(f"统计周期：{analysis_months} 个月")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📦 物料成本", "💼 人工成本", "🏢 费用支出", "💫 偶尔收支", "🏛️ 税赋管理", "📊 成本分析", "⚙️ 数据管理"])

# ============================================================
# Tab 1: 物料成本
# ============================================================
with tab1:
    st.header("📦 物料成本估算")
    with st.spinner("🔄 正在加载销售数据..."):
        df = data_manager.get_active_data()
        if "_final_amount" not in df.columns:
            st.error("数据缺少 _final_amount，请刷新或强制重载。")
            st.stop()
    
    if df.empty:
        st.warning("⚠️ 暂无销售数据，无法估算物料成本")
    else:
        # 处理交付时间
        if '交付时间' in df.columns:
            df['交付时间'] = pd.to_datetime(df['交付时间'], errors='coerce')
            df['_交付月份'] = df['交付时间'].dt.to_period('M').astype(str)
            df['_交付日期'] = df['交付时间'].dt.date
        elif '预计截止时间' in df.columns:
            df['预计截止时间'] = pd.to_datetime(df['预计截止时间'], errors='coerce')
            df['_交付月份'] = df['预计截止时间'].dt.to_period('M').astype(str)
            df['_交付日期'] = df['预计截止时间'].dt.date
        else:
            df['_交付月份'] = pd.Series(pd.NA, index=df.index, dtype="object")
            df['_交付日期'] = pd.NaT

        cost_calc = CostCalculator()
        df = cost_calc.apply_material_cost(df=df, material_ratios=material_ratios, revenue_column="_final_amount",
            business_line_column="业务线", output_column="物料成本", default_ratio=0.30)
        
        # 显示全部数据和筛选后数据
        total_projects_all = len(df)
        
        # 时间筛选
        df_in_period = df.copy()
        if '_交付日期' in df.columns:
            # 转换为date类型进行比较
            df_in_period['_交付日期'] = pd.to_datetime(df_in_period['_交付日期'], errors='coerce').dt.date
            mask = df_in_period['_交付日期'].notna()
            mask &= (df_in_period['_交付日期'] >= analysis_start) & (df_in_period['_交付日期'] <= analysis_end)
            df_in_period = df_in_period[mask]
        
        # 核心指标
        col1, col2, col3, col4, col5 = st.columns(5)
        total_material_cost = df_in_period['物料成本'].sum() if not df_in_period.empty else 0
        total_revenue = df_in_period['_final_amount'].sum() if not df_in_period.empty else 0
        
        col1.metric("全部项目数", total_projects_all)
        col2.metric("时段内项目数", len(df_in_period))
        col3.metric("时段内物料成本", f"¥{total_material_cost:,.2f}万")
        col4.metric("时段内收入", f"¥{total_revenue:,.2f}万")
        col5.metric("平均物料成本率", f"{(total_material_cost/total_revenue*100) if total_revenue > 0 else 0:.1f}%")

        # 显示筛选信息
        st.info(f"📅 当前筛选时段：{analysis_start} 至 {analysis_end}，共 {len(df_in_period)} 个项目在此期间交付")

        if not df_in_period.empty and '业务线' in df_in_period.columns:
            col1, col2 = st.columns(2)
            
            with col1:
                material_dist = df_in_period.groupby('业务线')['物料成本'].sum().reset_index()
                if not material_dist.empty:
                    fig = px.pie(material_dist, values='物料成本', names='业务线', title='物料成本业务线分布', hole=0.3)
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # 项目数量分布
                project_count = df_in_period.groupby('业务线').size().reset_index(name='项目数量')
                if not project_count.empty:
                    fig = px.bar(project_count, x='业务线', y='项目数量', title='各业务线项目数量', 
                                color='业务线', text='项目数量')
                    fig.update_traces(textposition='outside')
                    st.plotly_chart(fig, use_container_width=True)
        
        # 显示项目明细
        with st.expander("📋 查看时段内项目明细"):
            display_cols = ['客户', '业务线', '_final_amount', '物料成本', '_交付日期']
            display_cols = [c for c in display_cols if c in df_in_period.columns]
            if display_cols:
                show_df = df_in_period[display_cols].copy()
                show_df.columns = ['客户', '业务线', '预测收入', '物料成本', '交付日期'][:len(display_cols)]
                st.dataframe(show_df, use_container_width=True, hide_index=True)

# ============================================================
# Tab 2: 人工成本
# ============================================================
with tab2:
    st.header("💼 人工成本管理")
    labor_costs_df = cost_data_service.get_labor_costs()
    LABOR_COST_TYPES = cost_data_service.get_labor_cost_types()

    with st.expander("➕ 添加人工成本", expanded=False):
        st.markdown("##### 费用分类")
        col1, col2 = st.columns(2)
        with col1:
            cost_type = st.selectbox("成本类型", LABOR_COST_TYPES, key="labor_cost_type")
        with col2:
            expense_item = st.text_input("费用项目", "", key="labor_item", placeholder="例如：2026年全员固定薪金")
        
        st.markdown("##### 金额与时间")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            default_freq_index = 1 if cost_type in ["年终奖", "劳动关系补偿金"] else 0
            frequency = st.selectbox("付款频率", ["月度", "一次性", "季度", "年度"], index=default_freq_index, key="labor_freq")
        with col2:
            amount_label = "金额 (万元)" if frequency == "一次性" else "月度金额 (万元)"
            amount = st.number_input(amount_label, min_value=0.0, step=0.01, value=0.0, key="labor_amount")
        with col3:
            start_date = st.date_input("开始日期", value=analysis_start, key="labor_start")
        with col4:
            end_date = st.date_input("结束日期", value=analysis_end, key="labor_end")
        
        remark = st.text_input("备注（可选）", "", key="labor_remark")
        
        if amount > 0:
            if frequency == "一次性":
                st.info(f"📊 一次性支付：¥{amount:,.2f}万（支付日期：{start_date}）")
            else:
                pm = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
                st.info(f"📊 预计期间总成本：¥{amount * pm:,.2f}万（{pm}个月 × ¥{amount:,.2f}万/月）")

        if st.button("✅ 添加", key="add_labor", type="primary"):
            if expense_item and amount > 0:
                if cost_data_service.add_labor_cost(cost_type=cost_type, expense_item=expense_item, amount=amount,
                    frequency=frequency, start_date=start_date, end_date=end_date, remark=remark):
                    st.success(f"✅ 已添加：{expense_item}")
                    st.rerun()
            else:
                st.warning("⚠️ 请填写费用项目和金额")

    if not labor_costs_df.empty:
        st.markdown("---")
        col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
        with col_f1:
            all_types = ["全部"] + labor_costs_df['成本类型'].dropna().unique().tolist() if '成本类型' in labor_costs_df.columns else ["全部"]
            filter_type = st.selectbox("按类型筛选", all_types, key="filter_labor_type")
        with col_f2:
            all_freq = ["全部"] + labor_costs_df['付款频率'].dropna().unique().tolist() if '付款频率' in labor_costs_df.columns else ["全部"]
            filter_freq = st.selectbox("按频率筛选", all_freq, key="filter_labor_freq")
        with col_f3:
            search_term = st.text_input("🔍 搜索", "", key="search_labor")
        
        filtered_df = labor_costs_df.copy()
        if filter_type != "全部" and '成本类型' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['成本类型'] == filter_type]
        if filter_freq != "全部" and '付款频率' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['付款频率'] == filter_freq]
        if search_term and '费用项目' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['费用项目'].str.contains(search_term, case=False, na=False)]
        
        def calc_labor_cost(row):
            row_start = pd.to_datetime(row['开始日期']).date() if pd.notna(row['开始日期']) else analysis_start
            row_end = pd.to_datetime(row['结束日期']).date() if pd.notna(row['结束日期']) else analysis_end
            freq = row.get('付款频率', '月度') or '月度'
            amt = row.get('金额', 0)
            amt = float(amt) if pd.notna(amt) and amt is not None else 0.0
            if freq == '一次性':
                return (amt, 1) if analysis_start <= row_start <= analysis_end else (0, 0)
            eff_start, eff_end = max(row_start, analysis_start), min(row_end, analysis_end)
            if eff_start > eff_end: return (0, 0)
            months = (eff_end.year - eff_start.year) * 12 + (eff_end.month - eff_start.month) + 1
            return (amt * months, months)
        
        labor_display = filtered_df.copy()
        if not labor_display.empty:
            costs = labor_display.apply(calc_labor_cost, axis=1)
            labor_display['期间总成本'] = [x[0] for x in costs]
            labor_display['有效月/次'] = [x[1] for x in costs]
        
        st.markdown(f"##### 📋 人工成本明细（共 {len(filtered_df)} 条）")
        
        if not labor_display.empty:
            labor_display['选择'] = False
            cols = ['选择', '成本类型', '费用项目', '金额', '付款频率', '有效月/次', '期间总成本', 'id']
            cols = [c for c in cols if c in labor_display.columns or c == '选择']
            
            edited_df = st.data_editor(labor_display[cols], column_config={
                "选择": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
                "金额": st.column_config.NumberColumn("金额", format="¥%.2f万"),
                "期间总成本": st.column_config.NumberColumn("期间总成本", format="¥%.2f万"),
            }, hide_index=True, use_container_width=True, key="labor_editor")
            
            selected = edited_df[edited_df['选择'] == True]['id'].tolist() if 'id' in edited_df.columns else []
            if selected:
                if st.button(f"🗑️ 删除选中（{len(selected)}条）", key="del_labor"):
                    for sid in selected: cost_data_service.delete_labor_cost(sid)
                    st.success(f"✅ 已删除"); st.rerun()
        
        st.markdown("---")
        full_display = labor_costs_df.copy()
        if not full_display.empty:
            full_display['金额'] = full_display['金额'].apply(lambda x: float(x) if pd.notna(x) and x is not None else 0.0)
            costs = full_display.apply(calc_labor_cost, axis=1)
            full_display['期间总成本'] = [x[0] for x in costs]
        
        total_period = full_display['期间总成本'].sum() if not full_display.empty else 0
        monthly = 0
        if not full_display.empty and '付款频率' in full_display.columns:
            monthly_df = full_display[full_display['付款频率'] == '月度']
            monthly = monthly_df['金额'].sum() if not monthly_df.empty else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("月度人工成本", f"¥{monthly:,.2f}万")
        c2.metric("期间总人工成本", f"¥{total_period:,.2f}万")
        c3.metric("记录数", len(labor_costs_df))
        
        if '成本类型' in full_display.columns and not full_display.empty:
            ts = full_display.groupby('成本类型')['期间总成本'].sum().reset_index()
            ts = ts[ts['期间总成本'] > 0]
            if not ts.empty:
                fig = px.pie(ts, values='期间总成本', names='成本类型', title='人工成本分布', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📝 请添加人工成本数据")
        st.markdown("**人工成本分类：**" + "、".join(LABOR_COST_TYPES))

# ============================================================
# Tab 3: 费用支出
# ============================================================
with tab3:
    st.header("🏢 费用支出管理")
    admin_costs_df = cost_data_service.get_admin_costs()

    with st.expander("➕ 添加费用支出", expanded=False):
        st.markdown("##### 费用分类")
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_primary = st.selectbox("一级分类", list(cost_categories.keys()), key="admin_primary")
        with col2:
            sec_opts = cost_categories.get(selected_primary, [])
            expense_type = st.selectbox("二级分类", sec_opts, key="admin_secondary") if sec_opts else st.text_input("二级分类", selected_primary, key="admin_sec_text")
        with col3:
            expense_item = st.text_input("费用项目", "", key="admin_item", placeholder="例如：2026年杭州总部租金")
        
        st.markdown("##### 金额与时间")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            monthly_cost = st.number_input("月度成本 (万元)", min_value=0.0, step=0.01, value=0.0, key="admin_monthly")
        with col2:
            start_date = st.date_input("开始日期", value=analysis_start, key="admin_start")
        with col3:
            end_date = st.date_input("结束日期", value=analysis_end, key="admin_end")
        with col4:
            frequency = st.selectbox("付款频率", ["月度", "季度", "年度", "一次性"], key="admin_freq")
        
        remark = st.text_input("备注（可选）", "", key="admin_remark")
        
        if monthly_cost > 0:
            pm = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
            st.info(f"📊 预计期间总成本：¥{monthly_cost * pm:,.2f}万（{pm}个月）")

        if st.button("✅ 添加费用", key="add_admin", type="primary"):
            if expense_item and monthly_cost > 0:
                if cost_data_service.add_admin_cost(primary_category=selected_primary, expense_type=expense_type,
                    expense_item=expense_item, monthly_cost=monthly_cost, start_date=start_date,
                    end_date=end_date, frequency=frequency, remark=remark):
                    st.success(f"✅ 已添加：{expense_item}")
                    st.rerun()
            else:
                st.warning("⚠️ 请填写费用项目和月度成本")

    if not admin_costs_df.empty:
        st.markdown("---")
        
        # ========== 筛选器 ==========
        st.markdown("##### 🔍 筛选")
        col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
        with col_f1:
            all_pri = ["全部"] + sorted(admin_costs_df['一级分类'].dropna().unique().tolist()) if '一级分类' in admin_costs_df.columns else ["全部"]
            filter_pri = st.selectbox("一级分类", all_pri, key="filter_primary")
        with col_f2:
            # 二级分类根据一级分类动态变化
            if filter_pri != "全部" and '费用类型' in admin_costs_df.columns:
                filtered_for_sec = admin_costs_df[admin_costs_df['一级分类'] == filter_pri]
                all_sec = ["全部"] + sorted(filtered_for_sec['费用类型'].dropna().unique().tolist())
            else:
                all_sec = ["全部"] + sorted(admin_costs_df['费用类型'].dropna().unique().tolist()) if '费用类型' in admin_costs_df.columns else ["全部"]
            filter_sec = st.selectbox("二级分类", all_sec, key="filter_secondary")
        with col_f3:
            search = st.text_input("🔍 模糊搜索", "", key="search_admin", placeholder="搜索费用项目/分类/备注")
        
        # 应用筛选
        filtered = admin_costs_df.copy()
        if filter_pri != "全部" and '一级分类' in filtered.columns:
            filtered = filtered[filtered['一级分类'] == filter_pri]
        if filter_sec != "全部" and '费用类型' in filtered.columns:
            filtered = filtered[filtered['费用类型'] == filter_sec]
        
        # 模糊搜索：搜索费用项目、一级分类、二级分类、备注
        if search:
            search_lower = search.lower()
            mask = pd.Series([False] * len(filtered), index=filtered.index)
            for col in ['费用项目', '一级分类', '费用类型', '备注']:
                if col in filtered.columns:
                    mask |= filtered[col].astype(str).str.lower().str.contains(search_lower, na=False)
            filtered = filtered[mask]
        
        # 计算有效月数和期间成本
        def calc_admin_months(row):
            rs = pd.to_datetime(row['开始日期']).date() if pd.notna(row['开始日期']) else analysis_start
            re = pd.to_datetime(row['结束日期']).date() if pd.notna(row['结束日期']) else analysis_end
            es, ee = max(rs, analysis_start), min(re, analysis_end)
            return max(0, (ee.year - es.year) * 12 + (ee.month - es.month) + 1) if es <= ee else 0
        
        admin_display = filtered.copy()
        if not admin_display.empty:
            admin_display['月度成本'] = admin_display['月度成本'].apply(lambda x: float(x) if pd.notna(x) and x is not None else 0.0)
            admin_display['有效月数'] = admin_display.apply(calc_admin_months, axis=1)
            admin_display['期间总成本'] = admin_display['月度成本'] * admin_display['有效月数']
        
        # ========== 汇总指标 ==========
        st.markdown("---")
        total_monthly = admin_display['月度成本'].sum() if not admin_display.empty else 0
        total_period = admin_display['期间总成本'].sum() if not admin_display.empty else 0
        
        c1, c2, c3 = st.columns(3)
        filter_desc = f"【{filter_pri}】" if filter_pri != "全部" else "【全部分类】"
        c1.metric(f"{filter_desc} 月度费用", f"¥{total_monthly:,.2f}万")
        c2.metric(f"{filter_desc} 期间总费用", f"¥{total_period:,.2f}万")
        c3.metric("筛选后记录数", len(filtered))
        
        # ========== 图表（根据筛选联动）==========
        st.markdown("---")
        st.markdown("##### 📊 费用分布图表")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 一级分类分布（或二级分类分布，取决于筛选）
            if filter_pri == "全部":
                # 显示一级分类分布
                if '一级分类' in admin_display.columns and not admin_display.empty:
                    chart_data = admin_display.groupby('一级分类')['期间总成本'].sum().reset_index()
                    chart_data['期间总成本'] = chart_data['期间总成本'].round(2)  # 保留两位小数
                    chart_data = chart_data[chart_data['期间总成本'] > 0].sort_values('期间总成本', ascending=False)
                    if not chart_data.empty:
                        fig = px.pie(chart_data, values='期间总成本', names='一级分类', 
                                    title='💰 一级分类费用分布', hole=0.4)
                        fig.update_traces(textposition='inside', textinfo='percent+label',
                                         hovertemplate='%{label}<br>¥%{value:.2f}万<br>占比: %{percent}')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("暂无数据")
            else:
                # 选中了一级分类，显示该分类下的二级分类分布
                if '费用类型' in admin_display.columns and not admin_display.empty:
                    chart_data = admin_display.groupby('费用类型')['期间总成本'].sum().reset_index()
                    chart_data['期间总成本'] = chart_data['期间总成本'].round(2)  # 保留两位小数
                    chart_data = chart_data[chart_data['期间总成本'] > 0].sort_values('期间总成本', ascending=False)
                    if not chart_data.empty:
                        fig = px.pie(chart_data, values='期间总成本', names='费用类型', 
                                    title=f'💰 【{filter_pri}】二级分类分布', hole=0.4)
                        fig.update_traces(textposition='inside', textinfo='percent+label',
                                         hovertemplate='%{label}<br>¥%{value:.2f}万<br>占比: %{percent}')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info(f"【{filter_pri}】暂无数据")
        
        with col2:
            # 条形图：显示TOP费用项目
            if not admin_display.empty:
                if filter_pri == "全部":
                    # 显示各一级分类对比
                    bar_data = admin_display.groupby('一级分类')['期间总成本'].sum().reset_index()
                    bar_data['期间总成本'] = bar_data['期间总成本'].round(2)  # 保留两位小数
                    bar_data = bar_data[bar_data['期间总成本'] > 0].sort_values('期间总成本', ascending=True)
                    if not bar_data.empty:
                        fig = px.bar(bar_data, x='期间总成本', y='一级分类', orientation='h',
                                    title='📊 一级分类金额对比', color='一级分类', text='期间总成本')
                        fig.update_traces(texttemplate='¥%{text:.2f}万', textposition='outside')
                        fig.update_layout(showlegend=False)
                        fig.update_xaxes(tickformat='.2f')
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    # 选中了一级分类，显示该分类下的二级分类对比
                    bar_data = admin_display.groupby('费用类型')['期间总成本'].sum().reset_index()
                    bar_data['期间总成本'] = bar_data['期间总成本'].round(2)  # 保留两位小数
                    bar_data = bar_data[bar_data['期间总成本'] > 0].sort_values('期间总成本', ascending=True).tail(10)
                    if not bar_data.empty:
                        fig = px.bar(bar_data, x='期间总成本', y='费用类型', orientation='h',
                                    title=f'📊 【{filter_pri}】二级分类金额对比', color='费用类型', text='期间总成本')
                        fig.update_traces(texttemplate='¥%{text:.2f}万', textposition='outside')
                        fig.update_layout(showlegend=False)
                        fig.update_xaxes(tickformat='.2f')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info(f"【{filter_pri}】暂无数据")
        
        # ========== 费用明细表 ==========
        st.markdown("---")
        st.markdown(f"##### 📋 费用明细（共 {len(filtered)} 条）")
        
        if not admin_display.empty:
            admin_display['选择'] = False
            cols = ['选择', '一级分类', '费用类型', '费用项目', '月度成本', '有效月数', '期间总成本', 'id']
            cols = [c for c in cols if c in admin_display.columns or c == '选择']
            
            edited = st.data_editor(admin_display[cols], column_config={
                "选择": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
                "月度成本": st.column_config.NumberColumn("月度成本", format="¥%.2f万"),
                "期间总成本": st.column_config.NumberColumn("期间总成本", format="¥%.2f万"),
            }, hide_index=True, use_container_width=True, key="admin_editor")
            
            selected = edited[edited['选择'] == True]['id'].tolist() if 'id' in edited.columns else []
            if selected:
                if st.button(f"🗑️ 删除选中（{len(selected)}条）", key="del_admin"):
                    for sid in selected: cost_data_service.delete_admin_cost(sid)
                    st.success("✅ 已删除"); st.rerun()
    else:
        st.info("📝 请添加费用支出数据")
        with st.expander("📂 查看费用分类体系", expanded=True):
            for p, s in cost_categories.items():
                st.markdown(f"**{p}**：{', '.join(s) if s else '（无预设子类）'}")

# ============================================================
# Tab 4: 偶尔收支
# ============================================================
with tab4:
    st.header("💫 偶尔收支管理")
    st.caption("记录不定期发生的一次性收入和支出，如政府补贴、设备维修、退税等")
    
    occasional_df = cost_data_service.get_occasional_items()
    EXPENSE_TYPES = cost_data_service.get_occasional_expense_types()
    INCOME_TYPES = cost_data_service.get_occasional_income_types()

    # ========== 添加偶尔收支 ==========
    col_add1, col_add2 = st.columns(2)
    
    with col_add1:
        with st.expander("➕ 添加偶尔支出", expanded=False):
            exp_category = st.selectbox("支出分类", EXPENSE_TYPES, key="occ_exp_cat")
            exp_item = st.text_input("项目名称", "", key="occ_exp_item", placeholder="例如：空调维修费")
            col1, col2 = st.columns(2)
            with col1:
                exp_amount = st.number_input("金额 (万元)", min_value=0.0, step=0.01, value=0.0, key="occ_exp_amt")
            with col2:
                exp_date = st.date_input("发生日期", value=datetime.date.today(), key="occ_exp_date")
            exp_remark = st.text_input("备注", "", key="occ_exp_remark")
            
            if st.button("✅ 添加支出", key="add_occ_exp", type="primary"):
                if exp_item and exp_amount > 0:
                    if cost_data_service.add_occasional_item(
                        item_type="支出", category=exp_category, item_name=exp_item,
                        amount=exp_amount, occur_date=exp_date, remark=exp_remark):
                        st.success(f"✅ 已添加支出：{exp_item}")
                        st.rerun()
                else:
                    st.warning("⚠️ 请填写项目名称和金额")
    
    with col_add2:
        with st.expander("➕ 添加偶尔所得", expanded=False):
            inc_category = st.selectbox("所得分类", INCOME_TYPES, key="occ_inc_cat")
            inc_item = st.text_input("项目名称", "", key="occ_inc_item", placeholder="例如：政府创新补贴")
            col1, col2 = st.columns(2)
            with col1:
                inc_amount = st.number_input("金额 (万元)", min_value=0.0, step=0.01, value=0.0, key="occ_inc_amt")
            with col2:
                inc_date = st.date_input("发生日期", value=datetime.date.today(), key="occ_inc_date")
            inc_remark = st.text_input("备注", "", key="occ_inc_remark")
            
            if st.button("✅ 添加所得", key="add_occ_inc", type="primary"):
                if inc_item and inc_amount > 0:
                    if cost_data_service.add_occasional_item(
                        item_type="所得", category=inc_category, item_name=inc_item,
                        amount=inc_amount, occur_date=inc_date, remark=inc_remark):
                        st.success(f"✅ 已添加所得：{inc_item}")
                        st.rerun()
                else:
                    st.warning("⚠️ 请填写项目名称和金额")

    # ========== 汇总统计 ==========
    occ_summary = cost_data_service.get_occasional_summary(analysis_start, analysis_end)
    
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("期间偶尔支出", f"¥{occ_summary['支出']:,.2f}万", help=f"支出记录：{occ_summary['支出记录数']}条")
    col2.metric("期间偶尔所得", f"¥{occ_summary['所得']:,.2f}万", help=f"所得记录：{occ_summary['所得记录数']}条")
    col3.metric("期间净额", f"¥{occ_summary['净额']:,.2f}万", 
               delta=f"{'盈余' if occ_summary['净额'] >= 0 else '亏损'}")
    col4.metric("总记录数", occ_summary['支出记录数'] + occ_summary['所得记录数'])

    # ========== 收支列表 ==========
    if not occasional_df.empty:
        st.markdown("---")
        col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
        with col_f1:
            filter_type = st.selectbox("按类型筛选", ["全部", "支出", "所得"], key="filter_occ_type")
        with col_f2:
            if filter_type == "支出":
                filter_cats = ["全部"] + EXPENSE_TYPES
            elif filter_type == "所得":
                filter_cats = ["全部"] + INCOME_TYPES
            else:
                filter_cats = ["全部"] + EXPENSE_TYPES + INCOME_TYPES
            filter_cat = st.selectbox("按分类筛选", filter_cats, key="filter_occ_cat")
        with col_f3:
            search = st.text_input("🔍 搜索", "", key="search_occ")
        
        filtered = occasional_df.copy()
        if filter_type != "全部" and '类型' in filtered.columns:
            filtered = filtered[filtered['类型'] == filter_type]
        if filter_cat != "全部" and '分类' in filtered.columns:
            filtered = filtered[filtered['分类'] == filter_cat]
        if search and '项目名称' in filtered.columns:
            filtered = filtered[filtered['项目名称'].str.contains(search, case=False, na=False)]
        
        # 筛选期间内的记录
        if '发生日期' in filtered.columns:
            filtered['发生日期_dt'] = pd.to_datetime(filtered['发生日期'], errors='coerce')
            filtered = filtered[
                (filtered['发生日期_dt'].dt.date >= analysis_start) & 
                (filtered['发生日期_dt'].dt.date <= analysis_end)
            ]
        
        st.markdown(f"##### 📋 偶尔收支明细（期间内 {len(filtered)} 条）")
        
        if not filtered.empty:
            filtered['金额'] = filtered['金额'].apply(lambda x: float(x) if pd.notna(x) and x is not None else 0.0)
            filtered['选择'] = False
            cols = ['选择', '类型', '分类', '项目名称', '金额', '发生日期', '备注', 'id']
            cols = [c for c in cols if c in filtered.columns or c == '选择']
            
            edited = st.data_editor(filtered[cols], column_config={
                "选择": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
                "类型": st.column_config.TextColumn("类型", width="small"),
                "分类": st.column_config.TextColumn("分类", width="medium"),
                "项目名称": st.column_config.TextColumn("项目名称", width="large"),
                "金额": st.column_config.NumberColumn("金额", format="¥%.2f万"),
                "发生日期": st.column_config.TextColumn("发生日期", width="medium"),
            }, hide_index=True, use_container_width=True, key="occ_editor")
            
            selected = edited[edited['选择'] == True]['id'].tolist() if 'id' in edited.columns else []
            if selected:
                if st.button(f"🗑️ 删除选中（{len(selected)}条）", key="del_occ"):
                    for sid in selected: cost_data_service.delete_occasional_item(sid)
                    st.success("✅ 已删除"); st.rerun()
        
        # 图表
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if '类型' in filtered.columns and not filtered.empty:
                type_sum = filtered.groupby('类型')['金额'].sum().reset_index()
                if not type_sum.empty:
                    fig = px.pie(type_sum, values='金额', names='类型', title='收支类型分布', hole=0.4,
                                color='类型', color_discrete_map={'支出': '#ff6b6b', '所得': '#51cf66'})
                    st.plotly_chart(fig, use_container_width=True)
        with col2:
            if '分类' in filtered.columns and not filtered.empty:
                cat_sum = filtered.groupby(['类型', '分类'])['金额'].sum().reset_index()
                cat_sum = cat_sum.sort_values('金额', ascending=True).tail(10)
                if not cat_sum.empty:
                    fig = px.bar(cat_sum, x='金额', y='分类', orientation='h', color='类型',
                                title='分类金额TOP10', color_discrete_map={'支出': '#ff6b6b', '所得': '#51cf66'})
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📝 暂无偶尔收支记录")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**偶尔支出分类：**")
            for t in EXPENSE_TYPES:
                st.markdown(f"- {t}")
        with col2:
            st.markdown("**偶尔所得分类：**")
            for t in INCOME_TYPES:
                st.markdown(f"- {t}")

# ============================================================
# Tab 5: 税赋管理
# ============================================================
with tab5:
    st.header("🏛️ 税赋管理")
    df = data_manager.get_active_data()
    if df.empty:
        st.warning("⚠️ 暂无销售数据")
    else:
        if '交付时间' in df.columns:
            df['交付时间'] = pd.to_datetime(df['交付时间'], errors='coerce')
            df['_交付日期'] = df['交付时间'].dt.date
        elif '预计截止时间' in df.columns:
            df['预计截止时间'] = pd.to_datetime(df['预计截止时间'], errors='coerce')
            df['_交付日期'] = df['预计截止时间'].dt.date
        else:
            df['_交付日期'] = pd.NaT
        
        df_p = df[(df['_交付日期'] >= analysis_start) & (df['_交付日期'] <= analysis_end)] if '_交付日期' in df.columns else df
        
        if '_final_amount' in df_p.columns:
            df_p['税额'] = df_p['_final_amount'] * tax_rate
            total_tax, total_rev = df_p['税额'].sum(), df_p['_final_amount'].sum()
        else:
            total_tax, total_rev = 0, 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("期间预计收入", f"¥{total_rev:,.2f}万")
        c2.metric("期间预计税额", f"¥{total_tax:,.2f}万")
        c3.metric("税率", f"{tax_rate*100:.1f}%")

# ============================================================
# Tab 6: 成本分析
# ============================================================
with tab6:
    st.header("📊 成本分析")
    st.info(f"📅 统计期间：{analysis_start} 至 {analysis_end}（共 {analysis_months} 个月）")
    
    df = data_manager.get_active_data()
    labor_df = cost_data_service.get_labor_costs()
    admin_df = cost_data_service.get_admin_costs()
    
    if df.empty:
        st.warning("⚠️ 暂无销售数据"); st.stop()
    
    if '交付时间' in df.columns:
        df['交付时间'] = pd.to_datetime(df['交付时间'], errors='coerce')
        df['_交付日期'] = df['交付时间'].dt.date
    elif '预计截止时间' in df.columns:
        df['预计截止时间'] = pd.to_datetime(df['预计截止时间'], errors='coerce')
        df['_交付日期'] = df['预计截止时间'].dt.date
    else:
        df['_交付日期'] = pd.NaT
    
    df_p = df[(df['_交付日期'] >= analysis_start) & (df['_交付日期'] <= analysis_end)] if '_交付日期' in df.columns else df
    
    cost_calc = CostCalculator()
    df_p = cost_calc.apply_material_cost(df=df_p, material_ratios=material_ratios, revenue_column="_final_amount",
        business_line_column="业务线", output_column="物料成本", default_ratio=0.30)
    
    total_material = df_p['物料成本'].sum() if not df_p.empty else 0
    
    # 人工成本
    total_labor = 0
    if not labor_df.empty:
        for _, r in labor_df.iterrows():
            rs = pd.to_datetime(r['开始日期']).date() if pd.notna(r['开始日期']) else analysis_start
            re = pd.to_datetime(r['结束日期']).date() if pd.notna(r['结束日期']) else analysis_end
            freq = r.get('付款频率', '月度') or '月度'
            amt = r.get('金额', 0)
            amt = float(amt) if pd.notna(amt) and amt is not None else 0.0
            if freq == '一次性':
                if analysis_start <= rs <= analysis_end: total_labor += amt
            else:
                es, ee = max(rs, analysis_start), min(re, analysis_end)
                if es <= ee:
                    total_labor += amt * ((ee.year - es.year) * 12 + (ee.month - es.month) + 1)
    
    # 费用支出
    total_admin = 0
    if not admin_df.empty:
        for _, r in admin_df.iterrows():
            rs = pd.to_datetime(r['开始日期']).date() if pd.notna(r['开始日期']) else analysis_start
            re = pd.to_datetime(r['结束日期']).date() if pd.notna(r['结束日期']) else analysis_end
            es, ee = max(rs, analysis_start), min(re, analysis_end)
            if es <= ee:
                mc = r.get('月度成本', 0)
                mc = float(mc) if pd.notna(mc) and mc is not None else 0.0
                total_admin += mc * ((ee.year - es.year) * 12 + (ee.month - es.month) + 1)
    
    # 偶尔收支
    occ_summary = cost_data_service.get_occasional_summary(analysis_start, analysis_end)
    total_occ_expense = occ_summary['支出']
    total_occ_income = occ_summary['所得']
    
    df_p['税额'] = df_p['_final_amount'] * tax_rate
    total_tax = df_p['税额'].sum() if not df_p.empty else 0
    total_revenue = df_p['_final_amount'].sum() if not df_p.empty else 0
    
    # 总收入 = 销售收入 + 偶尔所得
    total_income = total_revenue + total_occ_income
    # 总成本 = 物料 + 人工 + 费用 + 税赋 + 偶尔支出
    total_cost = total_material + total_labor + total_admin + total_tax + total_occ_expense
    gross_profit = total_income - total_cost
    
    st.subheader("📈 核心指标")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("期间总收入", f"¥{total_income:,.2f}万", help=f"销售收入 ¥{total_revenue:,.2f}万 + 偶尔所得 ¥{total_occ_income:,.2f}万")
    c2.metric("期间总成本", f"¥{total_cost:,.2f}万")
    c3.metric("期间净利润", f"¥{gross_profit:,.2f}万")
    c4.metric("净利率", f"{(gross_profit/total_income*100) if total_income > 0 else 0:.1f}%")
    c5.metric("成本率", f"{(total_cost/total_income*100) if total_income > 0 else 0:.1f}%")
    
    st.divider()
    
    # 收入构成
    st.subheader("📊 收支构成明细")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**收入构成**")
        income_breakdown = pd.DataFrame({
            '收入类型': ['销售收入', '偶尔所得'],
            '金额': [total_revenue, total_occ_income]
        })
        income_breakdown['占比'] = (income_breakdown['金额'] / total_income * 100) if total_income > 0 else 0
        st.dataframe(income_breakdown.style.format({'金额': '¥{:.2f}万', '占比': '{:.1f}%'}), use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("**成本构成**")
        cost_breakdown = pd.DataFrame({
            '成本类型': ['物料成本', '人工成本', '费用支出', '税赋', '偶尔支出'],
            '金额': [total_material, total_labor, total_admin, total_tax, total_occ_expense]
        })
        cost_breakdown['占比'] = (cost_breakdown['金额'] / total_cost * 100) if total_cost > 0 else 0
        st.dataframe(cost_breakdown.style.format({'金额': '¥{:.2f}万', '占比': '{:.1f}%'}), use_container_width=True, hide_index=True)
    
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if total_cost > 0:
            fig = px.pie(cost_breakdown, values='金额', names='成本类型', title='成本结构占比', hole=0.3)
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(cost_breakdown, x='成本类型', y='金额', title='成本金额对比', color='成本类型', text='金额')
        fig.update_traces(texttemplate='¥%{text:.1f}万', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# Tab 7: 数据管理
# ============================================================
with tab7:
    st.header("⚙️ 成本数据管理")
    summary = cost_data_service.get_cost_summary()
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("人工成本记录", summary['人工成本记录数'])
    c2.metric("费用支出记录", summary['费用支出记录数'])
    c3.metric("偶尔收支记录", summary.get('偶尔收支记录数', 0))
    c4.metric("偶尔支出", f"¥{summary.get('偶尔支出', 0):,.2f}万")
    c5.metric("偶尔所得", f"¥{summary.get('偶尔所得', 0):,.2f}万")
    
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📤 数据导出")
        if st.button("导出所有成本数据", key="export"):
            data = cost_data_service.export_all_costs()
            st.download_button("下载 JSON", json.dumps(data, ensure_ascii=False, indent=2),
                f"cost_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json")
    with c2:
        st.subheader("📥 数据导入")
        f = st.file_uploader("选择 JSON 文件", type=['json'], key="import")
        if f:
            try:
                data = json.load(f)
                st.json(data)
                if st.button("确认导入", key="confirm_import"):
                    if cost_data_service.import_all_costs(data):
                        st.success("✅ 导入成功"); st.rerun()
            except Exception as e:
                st.error(f"解析失败: {e}")
    
    st.divider()
    st.subheader("📂 费用分类体系")
    with st.expander("查看费用分类"):
        st.json(cost_categories)
    
    st.divider()
    with st.expander("⚠️ 危险操作 - 清空数据"):
        st.warning("此操作将删除所有成本数据，不可恢复！")
        confirm = st.text_input("输入 'DELETE' 确认", key="confirm_del")
        if st.button("清空数据", key="clear"):
            if confirm == "DELETE":
                if cost_data_service.clear_all_costs():
                    st.success("✅ 已清空"); st.rerun()
            else:
                st.error("请输入 'DELETE' 确认")

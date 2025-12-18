# pages/5_📊_Overall_Budget_Summary.py
"""
全面预算汇总页面 - 修复版 V3

会计口径：
- 收入：交付时全额确认
- 物料成本：交付时确认
- 税额：交付时确认（基于收入）

与现金流分析的区别：
- 现金流分析是"现金口径"（按付款节奏）
- 预算汇总是"会计口径"（按交付时间）
"""

# === 认证检查（必须放在最开头）===
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
import numpy as np
from dateutil.relativedelta import relativedelta
from utils.chart_formatter import inject_plotly_css
from utils.display_helper import DisplayHelper

# === 从持久化存储读取成本数据 ===
from data.cost_data_service import cost_data_service

st.set_page_config(page_title="全面预算汇总", layout="wide")
st.title("📊 全面预算汇总")

inject_plotly_css()
DisplayHelper.apply_global_styles()

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


# ============================================================
# 成本计算辅助函数
# ============================================================
def calculate_period_labor_cost(labor_df: pd.DataFrame, start_date: datetime.date, end_date: datetime.date) -> float:
    """计算期间内的人工成本总额"""
    if labor_df.empty:
        return 0.0
    
    total = 0.0
    for _, row in labor_df.iterrows():
        row_start = pd.to_datetime(row.get('开始日期')).date() if pd.notna(row.get('开始日期')) else datetime.date(2000, 1, 1)
        row_end = pd.to_datetime(row.get('结束日期')).date() if pd.notna(row.get('结束日期')) else datetime.date(2099, 12, 31)
        
        freq = row.get('付款频率', '月度') or '月度'
        amount = row.get('金额', 0)
        if pd.isna(amount) or amount is None:
            amount = row.get('月度成本', 0)  # 兼容旧字段
        amount = float(amount) if pd.notna(amount) and amount is not None else 0.0
        
        if freq == '一次性':
            # 一次性支付：只在支付月份计入
            if start_date <= row_start <= end_date:
                total += amount
        else:
            # 月度支付：计算有效月数
            eff_start = max(row_start, start_date)
            eff_end = min(row_end, end_date)
            if eff_start <= eff_end:
                months = (eff_end.year - eff_start.year) * 12 + (eff_end.month - eff_start.month) + 1
                total += amount * months
    
    return total


def calculate_period_admin_cost(admin_df: pd.DataFrame, start_date: datetime.date, end_date: datetime.date) -> float:
    """计算期间内的费用支出总额"""
    if admin_df.empty:
        return 0.0
    
    total = 0.0
    for _, row in admin_df.iterrows():
        row_start = pd.to_datetime(row.get('开始日期')).date() if pd.notna(row.get('开始日期')) else datetime.date(2000, 1, 1)
        row_end = pd.to_datetime(row.get('结束日期')).date() if pd.notna(row.get('结束日期')) else datetime.date(2099, 12, 31)
        
        amount = row.get('月度成本', 0)
        amount = float(amount) if pd.notna(amount) and amount is not None else 0.0
        
        eff_start = max(row_start, start_date)
        eff_end = min(row_end, end_date)
        if eff_start <= eff_end:
            months = (eff_end.year - eff_start.year) * 12 + (eff_end.month - eff_start.month) + 1
            total += amount * months
    
    return total


def calculate_period_occasional(occasional_df: pd.DataFrame, start_date: datetime.date, end_date: datetime.date) -> tuple:
    """计算期间内的偶尔收支"""
    if occasional_df.empty:
        return 0.0, 0.0
    
    expense_total = 0.0
    income_total = 0.0
    
    for _, row in occasional_df.iterrows():
        occur_date = pd.to_datetime(row.get('发生日期')).date() if pd.notna(row.get('发生日期')) else None
        if occur_date is None:
            continue
        
        if start_date <= occur_date <= end_date:
            amount = row.get('金额', 0)
            amount = float(amount) if pd.notna(amount) and amount is not None else 0.0
            
            item_type = row.get('类型', '')
            if item_type == '支出':
                expense_total += amount
            elif item_type == '所得':
                income_total += amount
    
    return expense_total, income_total


def get_monthly_labor_cost(labor_df: pd.DataFrame, month_str: str) -> float:
    """计算指定月份的人工成本"""
    if labor_df.empty:
        return 0.0
    
    try:
        month_start = datetime.datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
        month_end = (month_start + relativedelta(months=1)) - datetime.timedelta(days=1)
        
        total = 0.0
        for _, row in labor_df.iterrows():
            row_start = pd.to_datetime(row.get('开始日期')).date() if pd.notna(row.get('开始日期')) else datetime.date(2000, 1, 1)
            row_end = pd.to_datetime(row.get('结束日期')).date() if pd.notna(row.get('结束日期')) else datetime.date(2099, 12, 31)
            
            freq = row.get('付款频率', '月度') or '月度'
            amount = row.get('金额', 0)
            if pd.isna(amount) or amount is None:
                amount = row.get('月度成本', 0)
            amount = float(amount) if pd.notna(amount) and amount is not None else 0.0
            
            if freq == '一次性':
                if row_start.year == month_start.year and row_start.month == month_start.month:
                    total += amount
            else:
                if row_start <= month_end and row_end >= month_start:
                    total += amount
        
        return total
    except:
        return 0.0


def get_monthly_admin_cost(admin_df: pd.DataFrame, month_str: str) -> float:
    """计算指定月份的费用支出"""
    if admin_df.empty:
        return 0.0
    
    try:
        month_start = datetime.datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
        month_end = (month_start + relativedelta(months=1)) - datetime.timedelta(days=1)
        
        total = 0.0
        for _, row in admin_df.iterrows():
            row_start = pd.to_datetime(row.get('开始日期')).date() if pd.notna(row.get('开始日期')) else datetime.date(2000, 1, 1)
            row_end = pd.to_datetime(row.get('结束日期')).date() if pd.notna(row.get('结束日期')) else datetime.date(2099, 12, 31)
            
            if row_start <= month_end and row_end >= month_start:
                amount = row.get('月度成本', 0)
                amount = float(amount) if pd.notna(amount) and amount is not None else 0.0
                total += amount
        
        return total
    except:
        return 0.0


def get_monthly_occasional(occasional_df: pd.DataFrame, month_str: str) -> tuple:
    """计算指定月份的偶尔收支"""
    if occasional_df.empty:
        return 0.0, 0.0
    
    try:
        month_start = datetime.datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
        
        expense_total = 0.0
        income_total = 0.0
        
        for _, row in occasional_df.iterrows():
            occur_date = pd.to_datetime(row.get('发生日期')).date() if pd.notna(row.get('发生日期')) else None
            if occur_date is None:
                continue
            
            if occur_date.year == month_start.year and occur_date.month == month_start.month:
                amount = row.get('金额', 0)
                amount = float(amount) if pd.notna(amount) and amount is not None else 0.0
                
                item_type = row.get('类型', '')
                if item_type == '支出':
                    expense_total += amount
                elif item_type == '所得':
                    income_total += amount
        
        return expense_total, income_total
    except:
        return 0.0, 0.0


def generate_month_list(start_date, end_date) -> list:
    """生成月份列表"""
    months = []
    current = start_date.replace(day=1)
    end = end_date.replace(day=1)
    
    while current <= end:
        months.append(current.strftime('%Y-%m'))
        current = current + relativedelta(months=1)
    
    return months


# ============================================================
# 加载销售数据
# ============================================================
with st.spinner("🔄 正在加载预算数据..."):
    df = data_manager.get_active_data()

if df is None or df.empty:
    st.warning("⚠️ 暂无销售数据")
    st.stop()

if "_final_amount" not in df.columns:
    if "人工纠偏金额" in df.columns:
        df["_final_amount"] = df["人工纠偏金额"]
    elif "金额" in df.columns:
        df["_final_amount"] = df["金额"]
    else:
        st.error("数据缺少 _final_amount，请刷新或强制重载。")
        st.stop()

df['_final_amount'] = pd.to_numeric(df['_final_amount'], errors='coerce').fillna(0)


# ============================================================
# 配置区域
# ============================================================
from core.config_manager import config_manager

BUSINESS_LINES = ["光谱设备/服务", "配液设备", "自动化项目"]

material_ratios = config_manager.render_material_ratios_ui(
    BUSINESS_LINES, sidebar=True, header="⚙️ 预算配置", default_ratio=0.30)

tax_rate = config_manager.render_tax_rate_ui(sidebar=True, header="")

# === 时间段筛选 ===
st.sidebar.divider()
st.sidebar.subheader("📅 预算时间范围")

today = datetime.datetime.now(BEIJING_TZ).date()
default_start = today.replace(day=1)
default_end = today + relativedelta(months=12)

budget_start = st.sidebar.date_input("开始日期", value=default_start, key="budget_start")
budget_end = st.sidebar.date_input("结束日期", value=default_end, key="budget_end")

if budget_start > budget_end:
    st.sidebar.error("开始日期不能晚于结束日期")
    budget_end = budget_start + relativedelta(months=12)

budget_months = generate_month_list(budget_start, budget_end)
num_months = len(budget_months)

st.info(f"📅 预算期间：**{budget_start.strftime('%Y-%m-%d')}** 至 **{budget_end.strftime('%Y-%m-%d')}**（共 {num_months} 个月）")


# ============================================================
# 加载成本数据
# ============================================================
labor_costs = cost_data_service.get_labor_costs()
admin_costs = cost_data_service.get_admin_costs()
occasional_costs = cost_data_service.get_occasional_items()


# ============================================================
# 计算物料成本和税额（会计口径：交付时确认）
# ============================================================
from core.cost_calculator import CostCalculator

cost_calc = CostCalculator()
df = cost_calc.apply_material_cost(
    df=df, material_ratios=material_ratios, revenue_column="_final_amount",
    business_line_column="业务线", output_column="物料成本", default_ratio=0.30)

# 税额基于收入（交付时确认）
df['税额'] = df['_final_amount'] * tax_rate

# 处理交付时间
if '交付时间' in df.columns:
    df['交付时间'] = pd.to_datetime(df['交付时间'], errors='coerce')
    df['_交付月份'] = df['交付时间'].dt.to_period('M').astype(str)
elif '预计截止时间' in df.columns:
    df['预计截止时间'] = pd.to_datetime(df['预计截止时间'], errors='coerce')
    df['_交付月份'] = df['预计截止时间'].dt.to_period('M').astype(str)
else:
    df['_交付月份'] = pd.NA


# ============================================================
# 预算汇总计算（会计口径）
# ============================================================

# 期间内的收入（会计口径：交付时全额确认）
budget_start_str = budget_start.strftime('%Y-%m')
budget_end_str = budget_end.strftime('%Y-%m')

period_revenue = 0
if '_交付月份' in df.columns:
    period_df = df[
        (df['_交付月份'] >= budget_start_str) &
        (df['_交付月份'] <= budget_end_str)
    ]
    period_revenue = period_df['_final_amount'].sum() if not period_df.empty else 0

# 期间内的成本
period_labor = calculate_period_labor_cost(labor_costs, budget_start, budget_end)
period_admin = calculate_period_admin_cost(admin_costs, budget_start, budget_end)
period_occ_expense, period_occ_income = calculate_period_occasional(occasional_costs, budget_start, budget_end)

# 期间内的物料成本和税额（会计口径：交付时确认）
period_material = 0
period_tax = 0
if '_交付月份' in df.columns:
    for month_str in budget_months:
        month_df = df[df['_交付月份'] == month_str]
        period_material += month_df['物料成本'].sum() if not month_df.empty else 0
        period_tax += month_df['税额'].sum() if not month_df.empty else 0

# 总收入和总成本
total_income = period_revenue + period_occ_income
total_cost = period_labor + period_admin + period_material + period_tax + period_occ_expense
gross_profit = total_income - total_cost


# ============================================================
# 预算概览
# ============================================================
st.header("📊 预算概览")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("预算总收入", f"¥{total_income:,.2f}万", 
              help=f"销售收入 ¥{period_revenue:,.2f}万 + 偶尔所得 ¥{period_occ_income:,.2f}万")
with col2:
    st.metric("预算总成本", f"¥{total_cost:,.2f}万")
with col3:
    st.metric("预算净利润", f"¥{gross_profit:,.2f}万")
with col4:
    profit_margin = (gross_profit / total_income * 100) if total_income > 0 else 0
    st.metric("净利率", f"{profit_margin:.1f}%")
with col5:
    cost_ratio = (total_cost / total_income * 100) if total_income > 0 else 0
    st.metric("成本率", f"{cost_ratio:.1f}%")

st.divider()


# ============================================================
# 成本结构分析
# ============================================================
st.header("💰 成本结构分析")

cost_breakdown = pd.DataFrame({
    '成本类型': ['人工成本', '费用支出', '物料成本', '税费', '偶尔支出'],
    '金额': [period_labor, period_admin, period_material, period_tax, period_occ_expense],
})
cost_breakdown['占比'] = (cost_breakdown['金额'] / total_cost * 100) if total_cost > 0 else 0

col1, col2 = st.columns(2)

with col1:
    if total_cost > 0:
        fig_cost = px.pie(cost_breakdown, values='金额', names='成本类型',
                         title='成本结构占比', hole=0.3)
        st.plotly_chart(fig_cost, use_container_width=True)
    else:
        st.info("暂无成本数据")

with col2:
    st.dataframe(cost_breakdown.style.format({
        '金额': '¥{:.2f}万',
        '占比': '{:.1f}%'
    }), use_container_width=True)

if period_labor == 0 and period_admin == 0:
    st.warning("⚠️ 未检测到人工成本和费用支出数据！请先在 **💰 成本管理** 页面添加。")

st.divider()


# ============================================================
# 收入分析
# ============================================================
st.header("📈 收入分析")

col1, col2 = st.columns(2)

with col1:
    st.subheader("收入构成")
    income_breakdown = pd.DataFrame({
        '收入类型': ['销售收入', '偶尔所得'],
        '金额': [period_revenue, period_occ_income]
    })
    income_breakdown['占比'] = (income_breakdown['金额'] / total_income * 100) if total_income > 0 else 0
    
    if total_income > 0:
        fig_income = px.pie(income_breakdown, values='金额', names='收入类型',
                           title='收入构成', hole=0.3,
                           color_discrete_map={'销售收入': '#2ca02c', '偶尔所得': '#17becf'})
        st.plotly_chart(fig_income, use_container_width=True)

with col2:
    st.subheader("业务线收入")
    if '_交付月份' in df.columns and '业务线' in df.columns:
        period_df = df[
            (df['_交付月份'] >= budget_start_str) &
            (df['_交付月份'] <= budget_end_str)
        ]
        if not period_df.empty:
            business_revenue = period_df.groupby('业务线')['_final_amount'].sum().reset_index()
            business_revenue = business_revenue.rename(columns={'_final_amount': '预算收入'})
            
            fig_business = px.pie(business_revenue, values='预算收入', names='业务线',
                                 title='业务线收入占比', hole=0.3)
            st.plotly_chart(fig_business, use_container_width=True)

st.divider()


# ============================================================
# 月度预算分布
# ============================================================
st.header("📅 月度预算分布")

# 构建月度汇总表
monthly_summary = pd.DataFrame({'月份': budget_months})

# 月度收入（会计口径：交付时全额确认）
monthly_revenue_list = []
monthly_material_list = []
monthly_tax_list = []

for month_str in budget_months:
    if '_交付月份' in df.columns:
        month_df = df[df['_交付月份'] == month_str]
        monthly_revenue_list.append(month_df['_final_amount'].sum() if not month_df.empty else 0)
        monthly_material_list.append(month_df['物料成本'].sum() if not month_df.empty else 0)
        monthly_tax_list.append(month_df['税额'].sum() if not month_df.empty else 0)
    else:
        monthly_revenue_list.append(0)
        monthly_material_list.append(0)
        monthly_tax_list.append(0)

monthly_summary['销售收入'] = monthly_revenue_list
monthly_summary['物料成本'] = monthly_material_list
monthly_summary['税额'] = monthly_tax_list

# 月度其他成本
monthly_labor_list = []
monthly_admin_list = []
monthly_occ_expense_list = []
monthly_occ_income_list = []

for month_str in budget_months:
    monthly_labor_list.append(get_monthly_labor_cost(labor_costs, month_str))
    monthly_admin_list.append(get_monthly_admin_cost(admin_costs, month_str))
    
    occ_exp, occ_inc = get_monthly_occasional(occasional_costs, month_str)
    monthly_occ_expense_list.append(occ_exp)
    monthly_occ_income_list.append(occ_inc)

monthly_summary['人工成本'] = monthly_labor_list
monthly_summary['费用支出'] = monthly_admin_list
monthly_summary['偶尔支出'] = monthly_occ_expense_list
monthly_summary['偶尔所得'] = monthly_occ_income_list

monthly_summary['总收入'] = monthly_summary['销售收入'] + monthly_summary['偶尔所得']
monthly_summary['总成本'] = (monthly_summary['人工成本'] + monthly_summary['费用支出'] + 
                           monthly_summary['物料成本'] + monthly_summary['税额'] + monthly_summary['偶尔支出'])
monthly_summary['净利润'] = monthly_summary['总收入'] - monthly_summary['总成本']

# 绘制月度趋势图
fig_monthly = go.Figure()

fig_monthly.add_trace(go.Bar(
    x=monthly_summary['月份'],
    y=monthly_summary['总收入'],
    name='总收入',
    marker_color='#2ca02c'
))

fig_monthly.add_trace(go.Bar(
    x=monthly_summary['月份'],
    y=-monthly_summary['总成本'],
    name='总成本',
    marker_color='#d62728'
))

fig_monthly.add_trace(go.Scatter(
    x=monthly_summary['月份'],
    y=monthly_summary['净利润'],
    name='净利润',
    mode='lines+markers',
    line=dict(color='#1f77b4', width=3)
))

fig_monthly.update_layout(
    title='月度预算收支趋势',
    xaxis_title='月份',
    yaxis_title='金额 (万元)',
    barmode='relative',
    hovermode='x unified'
)

st.plotly_chart(fig_monthly, use_container_width=True)

# 月度明细表
st.subheader("📋 月度预算明细")
display_cols = ['月份', '销售收入', '偶尔所得', '总收入', '人工成本', '费用支出', 
                '物料成本', '税额', '偶尔支出', '总成本', '净利润']
st.dataframe(monthly_summary[display_cols].style.format({
    '销售收入': '¥{:.2f}万', '偶尔所得': '¥{:.2f}万', '总收入': '¥{:.2f}万',
    '人工成本': '¥{:.2f}万', '费用支出': '¥{:.2f}万', '物料成本': '¥{:.2f}万',
    '税额': '¥{:.2f}万', '偶尔支出': '¥{:.2f}万', '总成本': '¥{:.2f}万', '净利润': '¥{:.2f}万'
}), use_container_width=True)

st.divider()


# ============================================================
# 成本明细
# ============================================================
st.header("📋 成本明细")

tab1, tab2, tab3 = st.tabs(["💼 人工成本", "🏢 费用支出", "💫 偶尔收支"])

with tab1:
    if not labor_costs.empty:
        display_cols = []
        if '成本类型' in labor_costs.columns:
            display_cols.append('成本类型')
        if '费用项目' in labor_costs.columns:
            display_cols.append('费用项目')
        if '金额' in labor_costs.columns:
            display_cols.append('金额')
        if '付款频率' in labor_costs.columns:
            display_cols.append('付款频率')
        if '开始日期' in labor_costs.columns:
            display_cols.append('开始日期')
        if '结束日期' in labor_costs.columns:
            display_cols.append('结束日期')
        
        if display_cols:
            display_labor = labor_costs[display_cols].copy()
            format_dict = {}
            if '金额' in display_cols:
                format_dict['金额'] = '¥{:.2f}万'
            st.dataframe(display_labor.style.format(format_dict), use_container_width=True)
        
        group_col = '成本类型' if '成本类型' in labor_costs.columns else None
        amount_col = '金额' if '金额' in labor_costs.columns else None
        
        if group_col and amount_col:
            labor_summary = labor_costs.groupby(group_col)[amount_col].sum().reset_index()
            fig_labor = px.pie(labor_summary, values=amount_col, names=group_col,
                              title='人工成本分布', hole=0.3)
            st.plotly_chart(fig_labor, use_container_width=True)
    else:
        st.info("暂无人工成本数据，请在 **💰 成本管理** 页面添加")

with tab2:
    if not admin_costs.empty:
        display_cols = [c for c in ['一级分类', '费用类型', '费用项目', '月度成本', '付款频率'] if c in admin_costs.columns]
        if display_cols:
            display_admin = admin_costs[display_cols].copy()
            format_dict = {'月度成本': '¥{:.2f}万'} if '月度成本' in display_cols else {}
            st.dataframe(display_admin.style.format(format_dict), use_container_width=True)
        
        if '费用类型' in admin_costs.columns and '月度成本' in admin_costs.columns:
            admin_summary = admin_costs.groupby('费用类型')['月度成本'].sum().reset_index()
            fig_admin = px.pie(admin_summary, values='月度成本', names='费用类型',
                              title='费用支出分布', hole=0.3)
            st.plotly_chart(fig_admin, use_container_width=True)
    else:
        st.info("暂无费用支出数据，请在 **💰 成本管理** 页面添加")

with tab3:
    if not occasional_costs.empty:
        display_cols = [c for c in ['类型', '分类', '项目名称', '金额', '发生日期', '备注'] if c in occasional_costs.columns]
        if display_cols:
            display_occ = occasional_costs[display_cols].copy()
            format_dict = {'金额': '¥{:.2f}万'} if '金额' in display_cols else {}
            st.dataframe(display_occ.style.format(format_dict), use_container_width=True)
        
        occ_summary = cost_data_service.get_occasional_summary(budget_start, budget_end)
        col1, col2, col3 = st.columns(3)
        col1.metric("期间偶尔支出", f"¥{occ_summary['支出']:,.2f}万")
        col2.metric("期间偶尔所得", f"¥{occ_summary['所得']:,.2f}万")
        col3.metric("期间净额", f"¥{occ_summary['净额']:,.2f}万")
    else:
        st.info("暂无偶尔收支数据，请在 **💰 成本管理** 页面添加")

st.divider()


# ============================================================
# 口径说明
# ============================================================
with st.expander("📖 数据口径说明"):
    st.markdown("""
    ### 预算汇总 - 会计口径
    
    | 项目 | 计算口径 | 说明 |
    |------|----------|------|
    | **销售收入** | 交付时间 | 项目交付时全额确认收入 |
    | **物料成本** | 交付时间 | 项目交付时确认物料成本 |
    | **税额** | 交付时间 | 基于收入计算，交付时确认 |
    | **人工成本** | 月度 | 按有效期按月计算 |
    | **费用支出** | 月度 | 按有效期按月计算 |
    | **偶尔收支** | 发生日期 | 按实际发生日期 |
    
    ### 与现金流分析的区别
    
    | 页面 | 口径 | 适用场景 |
    |------|------|----------|
    | **预算汇总** | 会计口径 | 利润预测、财务报表 |
    | **现金流分析** | 现金口径 | 现金规划、Runway分析 |
    
    - 预算汇总关注**何时确认收入/成本**（会计配比原则）
    - 现金流分析关注**何时收到/支出现金**（现金流管理）
    """)

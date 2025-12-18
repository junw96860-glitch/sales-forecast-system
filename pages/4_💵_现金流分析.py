# pages/4_💵_Cash_Flow.py
"""
现金流分析页面 - 完整修复版 V5

修复的问题：
1. 物料成本按"交付前1个月"计算（采购时间）
2. 税额跟随付款节奏（收款时产生纳税义务）
3. 核心指标随预测时间范围动态变化
4. 统一数据口径
"""

# === 认证检查（必须放在最开头）===
from utils.page_init import init_page
init_page()

# === 导入 ===
import streamlit as st
from data.data_manager import data_manager

# 设置 state store（重要！）
data_manager.set_state_store(st.session_state)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from datetime import timezone, timedelta
from dateutil.relativedelta import relativedelta
import numpy as np
from utils.chart_formatter import inject_plotly_css
from utils.display_helper import DisplayHelper

# === 从持久化存储读取成本数据 ===
from data.cost_data_service import cost_data_service

# === 飞书客户端和付款节奏服务 ===
from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_APP_TOKEN,
    PAYMENT_SCHEDULE_TABLE_ID,
)
from data.feishu_client import FeishuClient

# 导入付款模板
try:
    from payment_templates import (
        get_template,
        get_default_template_for_business,
    )
except ImportError:
    # 如果导入失败，使用内置默认值
    PAYMENT_TEMPLATES = {
        "标准三笔(5-4-1)": [
            {"name": "首付款", "ratio": 0.5, "offset_months": -1, "base": "开始时间"},
            {"name": "到货验收款", "ratio": 0.4, "offset_months": 0, "base": "交付时间"},
            {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
        ],
        "四笔分期(3-3-3-1)": [
            {"name": "首付款", "ratio": 0.3, "offset_months": 0, "base": "开始时间"},
            {"name": "到货款", "ratio": 0.3, "offset_months": 0, "base": "交付时间"},
            {"name": "验收款", "ratio": 0.3, "offset_months": 1, "base": "交付时间"},
            {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
        ],
    }
    DEFAULT_TEMPLATE_BY_BUSINESS = {
        "光谱设备/服务": "标准三笔(5-4-1)",
        "配液设备": "标准三笔(5-4-1)",
        "自动化项目": "四笔分期(3-3-3-1)",
    }
    DEFAULT_TEMPLATE = "标准三笔(5-4-1)"
    
    def get_template(name):
        return PAYMENT_TEMPLATES.get(name, PAYMENT_TEMPLATES[DEFAULT_TEMPLATE])
    
    def get_default_template_for_business(business_line):
        return DEFAULT_TEMPLATE_BY_BUSINESS.get(business_line, DEFAULT_TEMPLATE)

import json

st.set_page_config(page_title="现金流分析", layout="wide")
st.title("💵 现金流分析")

inject_plotly_css()
DisplayHelper.apply_global_styles()

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


# ============================================================
# 飞书客户端和付款节奏服务
# ============================================================
@st.cache_resource
def get_feishu_client():
    return FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN)


class PaymentScheduleService:
    """付款节奏服务（与收入预测页面保持一致）"""
    
    def __init__(self, client: FeishuClient, table_id: str):
        self.client = client
        self.table_id = table_id
        self._cache = None

    def load(self, force_refresh=False) -> pd.DataFrame:
        if self._cache is not None and not force_refresh:
            return self._cache
        try:
            records = self.client.get_records(self.table_id)
            if records is None:
                records = []
        except Exception as e:
            st.warning(f"加载付款节奏表失败: {e}")
            return pd.DataFrame()

        if not records:
            self._cache = pd.DataFrame()
            return self._cache

        rows = []
        for item in records:
            if item is None:
                continue
            fields = item.get("fields", {}) or {}
            rows.append({
                "_ps_record_id": item.get("record_id"),
                "record_id": fields.get("record_id", ""),
                "template_name": fields.get("template_name", ""),
                "payment_stages": fields.get("payment_stages", "[]"),
            })
        self._cache = pd.DataFrame(rows) if rows else pd.DataFrame()
        return self._cache

    def get_stages(self, source_record_id: str) -> tuple:
        """返回 (template_name, stages_list)"""
        df = self.load()
        if df.empty or "record_id" not in df.columns:
            return "", []
        hit = df[df["record_id"] == source_record_id]
        if hit.empty:
            return "", []
        row = hit.iloc[0]
        template_name = row.get("template_name", "")
        stages_json = row.get("payment_stages", "[]")
        try:
            stages = json.loads(stages_json) if stages_json else []
        except json.JSONDecodeError:
            stages = []
        return template_name, stages


def apply_template_with_dates(template_stages, start_date, delivery_date):
    """应用模板并计算具体日期"""
    result = []
    for stage in template_stages:
        base = stage.get("base", "交付时间")
        base_date = start_date if base == "开始时间" else delivery_date
        offset = stage.get("offset_months", 0)
        
        pay_date = None
        if base_date and pd.notna(base_date):
            try:
                base_dt = pd.to_datetime(base_date, errors="coerce")
                if pd.notna(base_dt):
                    pay_date = base_dt + relativedelta(months=offset)
            except Exception:
                pass
        
        result.append({
            "name": stage.get("name", ""),
            "ratio": stage.get("ratio", 0),
            "date": pay_date,
        })
    return result


def timestamp_to_date(ts):
    """将时间戳转换为datetime"""
    if ts is None or pd.isna(ts):
        return None
    try:
        return pd.to_datetime(ts, unit="ms")
    except:
        return None


def calculate_unified_cash_flow(df: pd.DataFrame, ps_service: PaymentScheduleService, tax_rate: float = 0.0) -> pd.DataFrame:
    """
    计算统一的现金流（与收入预测页面逻辑一致）
    
    修复：税额跟随付款节奏（收款时产生纳税义务）
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "项目名称", "业务线", "现金流类型", "金额", 
            "支付日期", "支付月份", "付款比例", "record_id", "税额"
        ])
    
    all_cash_flows = []
    
    for _, row in df.iterrows():
        record_id = row.get("record_id", "")
        revenue = row.get("_final_amount", 0)
        
        if pd.isna(revenue) or revenue <= 0:
            continue
        
        revenue = float(revenue)
        customer = row.get("客户", "")
        business_line = row.get("业务线", "")
        start_date = row.get("开始时间")
        delivery_date = row.get("交付时间") or row.get("预计截止时间")
        
        # 获取保存的付款节奏
        _, saved_stages = ps_service.get_stages(record_id)
        
        if saved_stages:
            # 使用保存的付款节奏
            stages = saved_stages
        else:
            # 使用默认模板
            default_template_name = get_default_template_for_business(business_line)
            template_def = get_template(default_template_name)
            stages = apply_template_with_dates(template_def, start_date, delivery_date)
        
        # 生成现金流条目
        for stage in stages:
            ratio = stage.get("ratio", 0)
            if ratio <= 0:
                continue
            
            # 获取付款日期
            pay_date = None
            if "date" in stage:
                if isinstance(stage["date"], (pd.Timestamp, datetime.datetime)):
                    pay_date = stage["date"]
                elif stage["date"]:
                    pay_date = timestamp_to_date(stage["date"])
            
            payment_amount = revenue * ratio
            # 税额跟随付款节奏：收款时产生纳税义务
            payment_tax = payment_amount * tax_rate
            
            payment_month = ""
            if pay_date and pd.notna(pay_date):
                payment_month = pay_date.strftime('%Y-%m')
            
            all_cash_flows.append({
                "项目名称": customer,
                "业务线": business_line,
                "现金流类型": stage.get("name", ""),
                "金额": payment_amount,
                "支付日期": pay_date,
                "支付月份": payment_month,
                "付款比例": f"{ratio * 100:.1f}%",
                "record_id": record_id,
                "税额": payment_tax,  # 新增：跟随付款的税额
            })
    
    if all_cash_flows:
        return pd.DataFrame(all_cash_flows)
    else:
        return pd.DataFrame(columns=[
            "项目名称", "业务线", "现金流类型", "金额", 
            "支付日期", "支付月份", "付款比例", "record_id", "税额"
        ])


# ============================================================
# 辅助函数（成本计算）
# ============================================================
def get_monthly_labor_cost(labor_df: pd.DataFrame, month_str: str) -> float:
    """计算指定月份的人工成本（支持新字段结构）"""
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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


def calculate_material_cost_by_month(df: pd.DataFrame, month_str: str) -> float:
    """
    计算指定月份的物料成本
    
    修复：物料成本按"交付前1个月"计算（采购时间）
    """
    if df.empty or '_物料成本月份' not in df.columns:
        return 0.0
    
    return df[df['_物料成本月份'] == month_str]['物料成本'].sum()


# ============================================================
# 加载销售数据
# ============================================================
with st.spinner("🔄 正在加载销售数据..."):
    try:
        df = data_manager.get_active_data()
    except Exception as e:
        st.error(f"加载数据失败: {e}")
        st.stop()

if df is None or df.empty:
    st.warning("⚠️ 暂无销售数据，无法进行现金流分析")
    st.stop()

if "_final_amount" not in df.columns:
    if "人工纠偏金额" in df.columns:
        df["_final_amount"] = df["人工纠偏金额"]
    elif "金额" in df.columns:
        df["_final_amount"] = df["金额"]
    else:
        st.error("数据缺少 _final_amount 或金额列，请刷新或强制重载。")
        st.stop()


# ============================================================
# 配置区域
# ============================================================
from core.config_manager import config_manager

BUSINESS_LINES = ["光谱设备/服务", "配液设备", "自动化项目"]

cash_cfg = config_manager.render_cashflow_base_ui(sidebar=True, header="⚙️ 现金流配置")
current_cash = cash_cfg["current_cash"]

tax_rate = config_manager.render_tax_rate_ui(sidebar=True, header="")

material_ratios = config_manager.render_material_ratios_ui(
    BUSINESS_LINES, sidebar=True, header="", default_ratio=0.30)

st.sidebar.divider()
st.sidebar.subheader("📅 预测时间范围")

today = datetime.datetime.now(BEIJING_TZ).date()
default_start = today.replace(day=1)
default_end = today + relativedelta(months=12)

forecast_start = st.sidebar.date_input("开始月份", value=default_start, key="forecast_start")
forecast_end = st.sidebar.date_input("结束月份", value=default_end, key="forecast_end")

if forecast_start > forecast_end:
    st.sidebar.error("开始月份不能晚于结束月份")
    forecast_end = forecast_start + relativedelta(months=12)

# 显示预测范围
forecast_months_count = (forecast_end.year - forecast_start.year) * 12 + (forecast_end.month - forecast_start.month) + 1
st.sidebar.caption(f"预测周期：{forecast_months_count} 个月")


# ============================================================
# 数据准备
# ============================================================
df['_final_amount'] = pd.to_numeric(df['_final_amount'], errors='coerce').fillna(0)

# 处理交付时间
if '交付时间' in df.columns:
    df['交付时间'] = pd.to_datetime(df['交付时间'], errors='coerce')
    df['_交付月份'] = df['交付时间'].dt.to_period('M').astype(str)
    # 物料成本月份 = 交付前1个月
    df['_物料成本月份'] = (df['交付时间'] - pd.DateOffset(months=1)).dt.to_period('M').astype(str)
elif '预计截止时间' in df.columns:
    df['预计截止时间'] = pd.to_datetime(df['预计截止时间'], errors='coerce')
    df['_交付月份'] = df['预计截止时间'].dt.to_period('M').astype(str)
    # 物料成本月份 = 交付前1个月
    df['_物料成本月份'] = (df['预计截止时间'] - pd.DateOffset(months=1)).dt.to_period('M').astype(str)
else:
    df['_交付月份'] = pd.NA
    df['_物料成本月份'] = pd.NA

# 计算物料成本
from core.cost_calculator import CostCalculator
cost_calc = CostCalculator()
df = cost_calc.apply_material_cost(
    df=df, material_ratios=material_ratios, revenue_column="_final_amount",
    business_line_column="业务线", output_column="物料成本", default_ratio=0.30)

# 注意：税额不再按交付时间计算，而是跟随付款节奏（在 calculate_unified_cash_flow 中处理）


# ============================================================
# 现金流计算（使用统一服务，包含税额）
# ============================================================
ps_service = PaymentScheduleService(get_feishu_client(), PAYMENT_SCHEDULE_TABLE_ID)
cash_flow_df = calculate_unified_cash_flow(df, ps_service, tax_rate=tax_rate)


# ============================================================
# 筛选预测时间范围内的数据
# ============================================================
forecast_start_str = forecast_start.strftime('%Y-%m')
forecast_end_str = forecast_end.strftime('%Y-%m')

# 筛选时间范围内的现金流
cash_flow_in_range = cash_flow_df[
    (cash_flow_df['支付月份'] >= forecast_start_str) & 
    (cash_flow_df['支付月份'] <= forecast_end_str)
].copy() if not cash_flow_df.empty else pd.DataFrame()

# 筛选时间范围内的项目（按交付时间）
df_in_range = df[
    (df['_交付月份'] >= forecast_start_str) & 
    (df['_交付月份'] <= forecast_end_str)
].copy() if '_交付月份' in df.columns else df.copy()


# ============================================================
# 核心指标展示（随预测时间范围变动）
# ============================================================
st.subheader("📊 核心指标")
st.info(f"📅 预测时间范围：**{forecast_start_str}** 至 **{forecast_end_str}**（共 {forecast_months_count} 个月）")

# 计算时间范围内的指标
total_project_revenue_in_range = df_in_range['_final_amount'].sum() if not df_in_range.empty else 0
project_count_in_range = len(df_in_range[df_in_range['_final_amount'] > 0]) if not df_in_range.empty else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("期间交付项目数", f"{project_count_in_range}", 
              help=f"在 {forecast_start_str} 至 {forecast_end_str} 期间交付的项目")
with col2:
    st.metric("期间项目收入", f"¥{total_project_revenue_in_range:,.2f}万", 
              help="期间交付项目的预期收入总和")
with col3:
    total_cash_in_range = cash_flow_in_range['金额'].sum() if not cash_flow_in_range.empty else 0
    st.metric("期间预计回款", f"¥{total_cash_in_range:,.2f}万",
              help="期间内根据付款节奏预计收到的款项")
with col4:
    total_tax_in_range = cash_flow_in_range['税额'].sum() if not cash_flow_in_range.empty and '税额' in cash_flow_in_range.columns else 0
    st.metric("期间预计税额", f"¥{total_tax_in_range:,.2f}万",
              help="跟随付款节奏产生的税额")

if not cash_flow_in_range.empty:
    # 按类型统计（期间内）
    type_summary = cash_flow_in_range.groupby('现金流类型')['金额'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        first_payment = type_summary.get('首付款', 0) + type_summary.get('预付款', 0)
        st.metric("首付/预付款", f"¥{first_payment:,.2f}万")
    with col2:
        delivery_payment = type_summary.get('到货验收款', 0) + type_summary.get('到货款', 0) + type_summary.get('验收款', 0)
        st.metric("到货/验收款", f"¥{delivery_payment:,.2f}万")
    with col3:
        retention = type_summary.get('质保金', 0)
        st.metric("质保金", f"¥{retention:,.2f}万")
    with col4:
        # 期间物料成本
        material_in_range = df[
            (df['_物料成本月份'] >= forecast_start_str) & 
            (df['_物料成本月份'] <= forecast_end_str)
        ]['物料成本'].sum() if '_物料成本月份' in df.columns else 0
        st.metric("期间物料成本", f"¥{material_in_range:,.2f}万",
                  help="按交付前1个月计算的物料采购成本")

    st.divider()

    # ============================================================
    # 现金流分布分析
    # ============================================================
    tab1, tab2, tab3, tab4 = st.tabs(["📊 现金流分布", "📈 月度趋势", "🏢 业务线分析", "📋 现金流明细"])

    with tab1:
        st.subheader("📈 现金流类型分布")
        type_summary_df = cash_flow_in_range.groupby('现金流类型')['金额'].sum().reset_index()
        if not type_summary_df.empty:
            fig_type = px.pie(type_summary_df, values='金额', names='现金流类型', 
                             title='现金流类型分布（期间内）', hole=0.3)
            st.plotly_chart(fig_type, use_container_width=True)
        
        cash_flow_summary = cash_flow_in_range.groupby('现金流类型').agg({
            '金额': 'sum',
            '项目名称': 'count'
        }).reset_index()
        cash_flow_summary['占比'] = cash_flow_summary['金额'] / cash_flow_summary['金额'].sum() * 100
        cash_flow_summary = cash_flow_summary.rename(columns={'项目名称': '笔数'})
        
        st.subheader("📊 现金流汇总")
        st.dataframe(cash_flow_summary.style.format({
            '金额': '¥{:.2f}万',
            '占比': '{:.1f}%',
        }), use_container_width=True)

    with tab2:
        st.subheader("📈 月度现金流趋势")
        valid_monthly = cash_flow_in_range[
            cash_flow_in_range['支付月份'].notna() & 
            (cash_flow_in_range['支付月份'] != '') &
            (cash_flow_in_range['支付月份'].astype(str).str.match(r'^\d{4}-\d{2}$', na=False))
        ].copy()
        
        if not valid_monthly.empty:
            monthly_summary_chart = valid_monthly.groupby('支付月份')['金额'].sum().reset_index()
            monthly_summary_chart = monthly_summary_chart.sort_values('支付月份')
            
            if not monthly_summary_chart.empty:
                fig_monthly = px.bar(monthly_summary_chart, x='支付月份', y='金额', 
                                    title='月度现金流汇总（期间内）')
                fig_monthly.update_layout(yaxis_title='现金流 (万元)', xaxis_title='月份')
                st.plotly_chart(fig_monthly, use_container_width=True)
            
            monthly_by_type = valid_monthly.groupby(['支付月份', '现金流类型'])['金额'].sum().reset_index()
            monthly_by_type = monthly_by_type.sort_values('支付月份')
            
            if not monthly_by_type.empty:
                fig_type_monthly = px.line(monthly_by_type, x='支付月份', y='金额', 
                                          color='现金流类型', 
                                          title='按类型分组的月度现金流趋势', 
                                          markers=True)
                fig_type_monthly.update_layout(yaxis_title='现金流 (万元)')
                st.plotly_chart(fig_type_monthly, use_container_width=True)
        else:
            st.info("暂无有效的月度现金流数据")

    with tab3:
        st.subheader("🏢 业务线现金流分析")
        if '业务线' in cash_flow_in_range.columns and not cash_flow_in_range.empty:
            business_cash_flow = cash_flow_in_range.groupby('业务线').agg({
                '金额': 'sum',
                '项目名称': 'nunique'
            }).reset_index()
            business_cash_flow['平均项目现金流'] = business_cash_flow['金额'] / business_cash_flow['项目名称']
            business_cash_flow = business_cash_flow.sort_values('金额', ascending=False)
            
            col1, col2 = st.columns(2)
            with col1:
                fig_business = px.bar(business_cash_flow, x='业务线', y='金额', 
                                     title='各业务线现金流分布', color='业务线')
                st.plotly_chart(fig_business, use_container_width=True)
            with col2:
                fig_business_pie = px.pie(business_cash_flow, values='金额', names='业务线', 
                                         title='业务线现金流占比', hole=0.3)
                st.plotly_chart(fig_business_pie, use_container_width=True)

    with tab4:
        st.subheader("📋 详细现金流记录（期间内）")
        display_cols = ['项目名称', '业务线', '现金流类型', '支付月份', '金额', '税额', '付款比例']
        available_cols = [col for col in display_cols if col in cash_flow_in_range.columns]
        
        if available_cols:
            cash_flow_display = cash_flow_in_range[available_cols].copy()
            cash_flow_display = cash_flow_display.sort_values(['支付月份', '现金流类型'], na_position='last')
            st.dataframe(cash_flow_display, use_container_width=True, height=400)

    st.divider()

    # ============================================================
    # Runway 分析
    # ============================================================
    st.header("📉 Runway 分析")
    
    # 获取成本数据
    st.subheader("💰 成本数据来源")
    
    labor_costs_df = cost_data_service.get_labor_costs()
    admin_costs_df = cost_data_service.get_admin_costs()
    occasional_df = cost_data_service.get_occasional_items()
    
    current_month_str = today.strftime('%Y-%m')
    current_labor_monthly = get_monthly_labor_cost(labor_costs_df, current_month_str)
    current_admin_monthly = get_monthly_admin_cost(admin_costs_df, current_month_str)
    current_occ_expense, current_occ_income = get_monthly_occasional(occasional_df, current_month_str)
    
    labor_count = len(labor_costs_df)
    admin_count = len(admin_costs_df)
    occasional_count = len(occasional_df)
    
    # 期间内的物料成本总和
    total_material_in_range = df[
        (df['_物料成本月份'] >= forecast_start_str) & 
        (df['_物料成本月份'] <= forecast_end_str)
    ]['物料成本'].sum() if '_物料成本月份' in df.columns else 0
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("人工成本(当月)", f"¥{current_labor_monthly:,.2f}万", 
                  help=f"当月有效的人工成本，共 {labor_count} 条记录")
    with col2:
        st.metric("费用支出(当月)", f"¥{current_admin_monthly:,.2f}万",
                  help=f"当月有效的费用支出，共 {admin_count} 条记录")
    with col3:
        st.metric("偶尔支出(当月)", f"¥{current_occ_expense:,.2f}万",
                  help=f"当月偶尔支出，共 {occasional_count} 条记录")
    with col4:
        st.metric("偶尔所得(当月)", f"¥{current_occ_income:,.2f}万", help="当月偶尔所得")
    with col5:
        st.metric("物料成本(期间)", f"¥{total_material_in_range:,.2f}万", 
                  help="期间内的物料成本（按交付前1个月）")
    
    if current_labor_monthly == 0 and current_admin_monthly == 0:
        st.warning("⚠️ 未检测到当月有效的成本数据！请先在 **💰 成本管理** 页面添加人工成本和费用支出。")
    
    st.divider()
    st.subheader("📊 现金余额预测")
    
    all_months_list = generate_month_list(forecast_start, forecast_end)
    
    if not all_months_list:
        st.error("预测时间范围无效")
        st.stop()
    
    monthly_summary = pd.DataFrame({'月份': all_months_list})
    
    # 合并收入数据（来自统一现金流服务）
    valid_for_runway = cash_flow_df[
        cash_flow_df['支付月份'].notna() & 
        (cash_flow_df['支付月份'] != '')
    ].copy()
    
    if not valid_for_runway.empty:
        monthly_income = valid_for_runway.groupby('支付月份')['金额'].sum().reset_index()
        monthly_income = monthly_income.rename(columns={'支付月份': '月份', '金额': '销售收入'})
        monthly_summary = monthly_summary.merge(monthly_income, on='月份', how='left')
        
        # 税额跟随付款节奏
        monthly_tax_from_payment = valid_for_runway.groupby('支付月份')['税额'].sum().reset_index()
        monthly_tax_from_payment = monthly_tax_from_payment.rename(columns={'支付月份': '月份', '税额': '税额'})
        monthly_summary = monthly_summary.merge(monthly_tax_from_payment, on='月份', how='left')
    
    monthly_summary['销售收入'] = monthly_summary.get('销售收入', 0).fillna(0)
    monthly_summary['税额'] = monthly_summary.get('税额', 0).fillna(0)
    
    # 计算每月的成本和偶尔收支
    monthly_labor_list = []
    monthly_admin_list = []
    monthly_material_list = []
    monthly_occ_expense_list = []
    monthly_occ_income_list = []
    
    for month_str in all_months_list:
        month_labor = get_monthly_labor_cost(labor_costs_df, month_str)
        monthly_labor_list.append(month_labor)
        
        month_admin = get_monthly_admin_cost(admin_costs_df, month_str)
        monthly_admin_list.append(month_admin)
        
        # 物料成本按"交付前1个月"计算
        month_material = calculate_material_cost_by_month(df, month_str)
        monthly_material_list.append(month_material)
        
        month_occ_expense, month_occ_income = get_monthly_occasional(occasional_df, month_str)
        monthly_occ_expense_list.append(month_occ_expense)
        monthly_occ_income_list.append(month_occ_income)
    
    monthly_summary['人工成本'] = monthly_labor_list
    monthly_summary['费用支出'] = monthly_admin_list
    monthly_summary['物料成本'] = monthly_material_list
    monthly_summary['偶尔支出'] = monthly_occ_expense_list
    monthly_summary['偶尔所得'] = monthly_occ_income_list
    
    monthly_summary['总收入'] = monthly_summary['销售收入'] + monthly_summary['偶尔所得']
    monthly_summary['总支出'] = (
        monthly_summary['人工成本'] + 
        monthly_summary['费用支出'] + 
        monthly_summary['物料成本'] + 
        monthly_summary['税额'] +
        monthly_summary['偶尔支出']
    )
    monthly_summary['净现金流'] = monthly_summary['总收入'] - monthly_summary['总支出']
    
    cumulative_balance = []
    balance = current_cash
    for net_flow in monthly_summary['净现金流']:
        balance += net_flow
        cumulative_balance.append(balance)
    monthly_summary['累计现金余额'] = cumulative_balance
    
    runway_months = 0
    for balance in cumulative_balance:
        if balance <= 0:
            break
        runway_months += 1
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("当前现金余额", f"¥{current_cash:,.2f}万")
    with col2:
        avg_monthly_expense = monthly_summary['总支出'].mean()
        st.metric("平均月度支出", f"¥{avg_monthly_expense:,.2f}万")
    with col3:
        if runway_months >= len(all_months_list):
            st.metric("预计 Runway", f">{runway_months} 个月", delta="充足", delta_color="normal")
        else:
            delta_text = "警告" if runway_months < 6 else "正常"
            delta_color = "inverse" if runway_months < 6 else "normal"
            st.metric("预计 Runway", f"{runway_months} 个月", delta=delta_text, delta_color=delta_color)
    with col4:
        min_balance = min(cumulative_balance) if cumulative_balance else current_cash
        st.metric("最低现金余额", f"¥{min_balance:,.2f}万",
                  delta="危险" if min_balance < 0 else None,
                  delta_color="inverse" if min_balance < 0 else "normal")
    
    # 现金余额趋势图
    fig_runway = go.Figure()
    
    fig_runway.add_trace(go.Scatter(
        x=monthly_summary['月份'], 
        y=monthly_summary['累计现金余额'], 
        mode='lines+markers', 
        name='累计现金余额',
        line=dict(color='#1a2a6c', width=3),
        marker=dict(size=8)
    ))
    
    fig_runway.add_trace(go.Bar(
        x=monthly_summary['月份'],
        y=monthly_summary['总收入'],
        name='总收入',
        marker_color='#2ca02c',
        opacity=0.6
    ))
    
    fig_runway.add_trace(go.Bar(
        x=monthly_summary['月份'],
        y=-monthly_summary['总支出'],
        name='总支出',
        marker_color='#d62728',
        opacity=0.6
    ))
    
    fig_runway.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="现金枯竭警戒线")
    
    fig_runway.update_layout(
        title='现金流与余额趋势预测',
        xaxis_title='月份',
        yaxis_title='金额 (万元)',
        hovermode='x unified',
        barmode='relative'
    )
    st.plotly_chart(fig_runway, use_container_width=True)
    
    # 详细 Runway 数据表
    st.subheader("📊 Runway 详细数据")
    
    display_cols = ['月份', '销售收入', '偶尔所得', '总收入', '人工成本', '费用支出', 
                    '物料成本', '税额', '偶尔支出', '总支出', '净现金流', '累计现金余额']
    runway_display = monthly_summary[display_cols].copy()
    
    format_dict = {col: '¥{:.2f}万' for col in display_cols if col != '月份'}
    st.dataframe(runway_display.style.format(format_dict), use_container_width=True)
    
    # 成本结构分析
    st.subheader("📊 成本结构分析（期间内）")
    
    total_expense = monthly_summary['总支出'].sum()
    if total_expense > 0:
        cost_structure = pd.DataFrame({
            '成本类型': ['人工成本', '费用支出', '物料成本', '税额', '偶尔支出'],
            '金额': [
                monthly_summary['人工成本'].sum(),
                monthly_summary['费用支出'].sum(),
                monthly_summary['物料成本'].sum(),
                monthly_summary['税额'].sum(),
                monthly_summary['偶尔支出'].sum()
            ]
        })
        cost_structure['占比'] = cost_structure['金额'] / total_expense * 100
        
        col1, col2 = st.columns(2)
        with col1:
            fig_cost = px.pie(cost_structure, values='金额', names='成本类型', 
                             title='成本结构占比', hole=0.3)
            st.plotly_chart(fig_cost, use_container_width=True)
        with col2:
            st.dataframe(cost_structure.style.format({
                '金额': '¥{:.2f}万',
                '占比': '{:.1f}%'
            }), use_container_width=True)
    
    # 口径说明
    st.divider()
    with st.expander("📖 数据口径说明"):
        st.markdown("""
        ### 现金流口径说明
        
        | 项目 | 计算口径 | 说明 |
        |------|----------|------|
        | **销售收入** | 付款节奏 | 根据每个项目的付款节奏（首付款、到货款、质保金等）分配到各月 |
        | **税额** | 付款节奏 | 跟随收款节奏，收款时产生纳税义务 |
        | **物料成本** | 交付前1个月 | 假设在项目交付前1个月采购物料 |
        | **人工成本** | 月度 | 根据成本管理中配置的有效期按月计算 |
        | **费用支出** | 月度 | 根据成本管理中配置的有效期按月计算 |
        | **偶尔收支** | 发生日期 | 按实际发生日期所在月份计算 |
        """)

else:
    st.warning("⚠️ 计算出的现金流数据为空，请检查销售数据和付款配置")
    st.info("💡 提示：请确保在 **📈 收入预测** 页面配置了项目的付款节奏")

# pages/8_⚙️_System_Settings.py
"""
系统设置页面 - 统一配置入口

框架要求：
- 系统设置页是"唯一配置入口"
- 负责写入 config/app_config.json
- 其他页面只负责读取配置，不再重复 slider/selectbox
- 调用 config_manager 的 render_xxx_ui() 系列函数
"""
from utils.page_init import init_page
init_page()
import streamlit as st
from utils.display_helper import DisplayHelper
from utils.chart_formatter import inject_plotly_css
from core.config_manager import config_manager
from data.data_manager import data_manager

# 设置 state_store 确保数据管理器能访问 session_state
data_manager.set_state_store(st.session_state)

st.set_page_config(page_title="系统设置", layout="wide")
st.title("⚙️ 系统设置")

inject_plotly_css()
DisplayHelper.apply_global_styles()
st.markdown("""
> 这是系统的**统一配置入口**。所有配置项在此页面修改后会自动保存到 `config/app_config.json`，
> 其他页面会自动读取这些配置。
""")

# 业务线列表（后续可考虑也放入配置）
BUSINESS_LINES = ["光谱设备/服务", "配液设备", "自动化项目"]

# ============================================================
# Tab 布局
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 预测配置", 
    "💰 成本配置", 
    "💵 现金流配置", 
    "🎨 显示配置",
    "🔧 飞书API配置"
])

# ============================================================
# Tab 1: 预测配置
# ============================================================
with tab1:
    st.header("📈 预测配置")
    st.markdown("""
    控制收入预测的核心参数：
    - **时间衰减系数 λ**：越大则远期项目折扣越大
    - **基准日期偏移**：调整预测的基准日期
    - **预测月份数**：影响预测展开的月份跨度
    """)
    
    forecast_cfg = config_manager.render_forecast_config_ui(sidebar=False)
    
    # 显示配置影响说明
    with st.expander("💡 配置影响说明"):
        st.markdown(f"""
        **当前配置**:
        - λ = {forecast_cfg['decay_lambda']:.4f}
        - 基准偏移 = {forecast_cfg['base_date_offset']} 天
        - 预测月数 = {forecast_cfg['months_ahead']} 个月
        
        **系统预测公式**:
        ```
        _system_pred_amount = 金额 × 成单率% × exp(-λ × 月数差)
        ```
        
        **影响页面**:
        - 📊 Dashboard
        - 📈 收入预测
        - 💵 现金流分析
        """)

# ============================================================
# Tab 2: 成本配置
# ============================================================
with tab2:
    st.header("💰 成本配置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦 按业务线物料比例")
        st.markdown("这是成本计算的**主口径**，各页面的物料成本计算都基于此配置。")
        
        material_ratios = config_manager.render_material_ratios_ui(
            BUSINESS_LINES,
            sidebar=False,
            header="",
            default_ratio=0.30,
        )
        
        st.info(f"""
        **当前物料比例**:
        - 光谱设备/服务: {material_ratios.get('光谱设备/服务', 0.30)*100:.0f}%
        - 配液设备: {material_ratios.get('配液设备', 0.35)*100:.0f}%
        - 自动化项目: {material_ratios.get('自动化项目', 0.40)*100:.0f}%
        """)
    
    with col2:
        st.subheader("🏛️ 税率配置")
        tax_rate = config_manager.render_tax_rate_ui(
            sidebar=False,
            header="",
        )
        st.info(f"当前税率: {tax_rate*100:.0f}%")
    
    st.divider()
    
    st.subheader("💳 默认付款比例配置")
    st.markdown("项目付款节奏的默认配置，新项目会使用这些默认值。")
    
    payment_cfg = config_manager.render_default_payment_stages_ui(
        sidebar=False,
        header="",
    )
    
    total_ratio = sum(payment_cfg.values())
    if abs(total_ratio - 100) < 0.1:
        st.success(f"✅ 付款比例总和: {total_ratio:.0f}%")
    else:
        st.error(f"❌ 付款比例总和: {total_ratio:.0f}%（应为 100%）")

# ============================================================
# Tab 3: 现金流配置
# ============================================================
with tab3:
    st.header("💵 现金流配置")
    st.markdown("""
    控制现金流预测的参数：
    - **当前现金余额**：Runway 计算的起点
    - **预测月份数**：现金流预测的时间跨度
    """)
    
    cashflow_cfg = config_manager.render_cashflow_base_ui(
        sidebar=False,
        header="",
    )
    
    st.info(f"""
    **当前配置**:
    - 现金余额: ¥{cashflow_cfg['current_cash']:,.2f}万
    - 预测月数: {cashflow_cfg['months_ahead']} 个月
    """)
    
    with st.expander("💡 配置影响说明"):
        st.markdown("""
        **影响页面**:
        - 💵 现金流分析 - Runway 计算
        - 📊 全面预算汇总
        """)

# ============================================================
# Tab 4: 显示配置
# ============================================================
with tab4:
    st.header("🎨 显示配置")
    st.markdown("控制图表和表格的显示样式。")
    
    display_cfg = config_manager.render_display_config_ui(sidebar=False)
    
    st.info(f"""
    **当前配置**:
    - 图表高度: {display_cfg['chart_height']}px
    - 表格分页: {display_cfg['table_page_size']} 行
    - 显示空分类: {'是' if display_cfg['show_empty_categories'] else '否'}
    - 配色方案: {display_cfg['color_palette']}
    """)

# ============================================================
# Tab 5: 飞书API配置
# ============================================================
with tab5:
    st.header("🔧 飞书API配置")
    st.markdown("""
    配置飞书多维表格的 API 访问凭证。
    
    ⚠️ **注意**: APP SECRET 是敏感信息，请妥善保管。
    """)
    
    feishu_config = config_manager.get_config("feishu") or {}
    
    with st.form("feishu_config_form"):
        feishu_app_id = st.text_input(
            "APP ID", 
            value=feishu_config.get('app_id', ''),
            help="飞书开放平台的 App ID"
        )
        feishu_app_secret = st.text_input(
            "APP SECRET", 
            value=feishu_config.get('app_secret', ''),
            type="password",
            help="飞书开放平台的 App Secret"
        )
        
        if st.form_submit_button("💾 保存飞书配置"):
            # 使用正确的 set_config 调用方式
            config_manager.set_config("feishu", "app_id", feishu_app_id)
            config_manager.set_config("feishu", "app_secret", feishu_app_secret)
            st.success("✅ 飞书配置已保存！")

# ============================================================
# 配置摘要与操作
# ============================================================
st.divider()
st.header("📋 配置摘要")

col1, col2 = st.columns([2, 1])

with col1:
    with st.expander("📄 查看完整配置 (JSON)", expanded=False):
        # 隐藏敏感信息
        display_config = config_manager.current_config.copy()
        if "feishu" in display_config and "app_secret" in display_config["feishu"]:
            display_config["feishu"]["app_secret"] = "******"
        st.json(display_config)

with col2:
    st.subheader("⚡ 快捷操作")
    
    if st.button("🔄 重置为默认配置", type="secondary"):
        if st.session_state.get("confirm_reset"):
            config_manager.reset_to_default()
            st.success("✅ 已重置为默认配置！")
            st.session_state.confirm_reset = False
            st.rerun()
        else:
            st.session_state.confirm_reset = True
            st.warning("⚠️ 再次点击确认重置")
    
    if st.button("💾 强制保存配置"):
        config_manager.save_config()
        st.success("✅ 配置已保存到 config/app_config.json")

# 显示配置文件路径
st.caption(f"📁 配置文件路径: `{config_manager.config_file}`")

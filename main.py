# main.py - 销售预测系统主入口
"""
简洁高端版首页 - UI 增强版
修复：时区问题，使用北京时间（UTC+8）
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
import re

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

# ============================================================
# 0. 基础配置与检查 (保持逻辑不变)
# ============================================================
st.set_page_config(
    page_title="销售预测系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 引入自定义模块
try:
    from config import is_configured, get_config_status
    from utils.auth import check_password, show_user_info
    from data.data_manager import data_manager
except ImportError:
    st.error("❌ 模块导入失败，请确保 config.py, utils/, data/ 目录存在且完整。")
    st.stop()

# 检查配置
if not is_configured():
    st.error("⚠️ 系统配置不完整！")
    with st.expander("🔧 查看配置状态"):
        st.json(get_config_status())
    st.stop()

# 检查权限
if not check_password():
    st.stop()

# 初始化数据
data_manager.set_state_store(st.session_state)

# ============================================================
# 1. 高端 UI 样式定义 (CSS)
# ============================================================
st.markdown("""
<style>
    /* ================================
       Global tokens
       ================================ */
    :root {
        --bg: #f8fafc;
        --bg-2: #f1f5f9;
        --card: #ffffff;
        --text: #0f172a;
        --muted: #64748b;
        --border: rgba(15, 23, 42, 0.10);
        --shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
        --shadow-soft: 0 2px 10px rgba(15, 23, 42, 0.06);
        --radius: 14px;
        --radius-sm: 10px;
        --accent-1: #2563eb;
        --accent-2: #9333ea;
    }

    /* 字体（保持原有 Inter，但提供稳健降级） */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--text);
    }

    /* App 背景 */
    .stApp {
        background:
            radial-gradient(900px 380px at 15% -10%, rgba(37, 99, 235, 0.12), transparent 60%),
            radial-gradient(820px 360px at 95% 0%, rgba(147, 51, 234, 0.10), transparent 55%),
            linear-gradient(180deg, var(--bg) 0%, var(--bg-2) 100%);
    }

    /* 主内容区边距与宽度 */
    .main .block-container {
        padding-top: 1.75rem;
        padding-bottom: 2rem;
        max-width: 1360px;
    }

    /* 顶部标题 */
    .hero-title {
        font-size: 2.1rem;
        font-weight: 850;
        letter-spacing: -0.02em;
        background: linear-gradient(120deg, var(--accent-1), var(--accent-2));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.45rem;
        line-height: 1.12;
    }
    .hero-subtitle {
        color: var(--muted);
        font-size: 1rem;
        margin-bottom: 1.6rem;
    }

    /* KPI 卡片（保留你的 class 名，统一细节） */
    .kpi-card {
        background: var(--card);
        border-radius: var(--radius);
        padding: 1.25rem 1.25rem;
        border: 1px solid var(--border);
        box-shadow: var(--shadow-soft);
        transition: transform 0.14s ease, box-shadow 0.14s ease, border-color 0.14s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow);
        border-color: rgba(37, 99, 235, 0.22);
    }
    .kpi-label {
        color: var(--muted);
        font-size: 0.80rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.55rem;
    }
    .kpi-value {
        color: var(--text);
        font-size: 1.9rem;
        font-weight: 800;
        letter-spacing: -0.01em;
    }
    .kpi-sub {
        font-size: 0.85rem;
        margin-top: 0.65rem;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .trend-up {
        color: #047857;
        background: rgba(16, 185, 129, 0.12);
        padding: 2px 8px;
        border-radius: 999px;
        font-weight: 700;
    }
    .trend-neutral {
        color: #3730a3;
        background: rgba(99, 102, 241, 0.12);
        padding: 2px 8px;
        border-radius: 999px;
        font-weight: 700;
    }

    /* Section header（更紧凑，更像模块标题） */
    .section-header {
        font-size: 1.05rem;
        font-weight: 820;
        color: rgba(15, 23, 42, 0.92);
        margin: 0.15rem 0 0.75rem 0;
        display: flex;
        align-items: center;
        gap: 0.55rem;
        letter-spacing: -0.01em;
    }

    /* 自动把 Plotly / DataFrame 包装成“卡片” */
    div[data-testid="stPlotlyChart"] > div,
    div[data-testid="stDataFrame"] > div {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 0.75rem;
        box-shadow: var(--shadow-soft);
    }

    /* DataFrame 顶部留白略调 */
    div[data-testid="stDataFrame"] > div {
        padding: 0.65rem 0.65rem 0.35rem 0.65rem;
    }

    /* 侧边栏：沿用你现有的品牌样式，但细节更统一 */
    footer {visibility: hidden;}

    [data-testid="stSidebarNav"] > ul > li:first-child {
        display: none;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        border-right: 1px solid rgba(15, 23, 42, 0.06);
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    .sidebar-brand-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.15rem 1rem;
        border-radius: 12px;
        margin: 0.25rem 0 0.75rem 0;
        text-align: center;
        box-shadow: var(--shadow-soft);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }
    .sidebar-brand-icon {
        font-size: 2rem;
        margin-bottom: 0.35rem;
        line-height: 1;
        filter: drop-shadow(0 2px 6px rgba(0,0,0,0.20));
    }
    .sidebar-brand-title {
        color: white;
        font-size: 1.08rem;
        font-weight: 800;
        margin: 0;
    }
    .sidebar-brand-subtitle {
        color: rgba(255,255,255,0.84);
        font-size: 0.75rem;
        margin-top: 0.25rem;
    }

    /* st.page_link 的链接统一胶囊样式 */
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
        border-radius: 10px !important;
        padding: 0.55rem 0.75rem !important;
        margin: 0.15rem 0 !important;
        border: 1px solid rgba(15, 23, 42, 0.08) !important;
        background: rgba(255, 255, 255, 0.55) !important;
        font-weight: 650 !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        transition: transform 0.12s ease, background 0.12s ease, border-color 0.12s ease, box-shadow 0.12s ease;
    }
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {
        background: rgba(255, 255, 255, 0.85) !important;
        border-color: rgba(37, 99, 235, 0.22) !important;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
        transform: translateY(-1px);
    }
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:first-of-type {
        background: linear-gradient(90deg, #f0f9ff 0%, #e0f2fe 100%) !important;
        border: 2px solid #7dd3fc !important;
        color: #0369a1 !important;
        font-weight: 750 !important;
    }

    .sidebar-section-label {
        color: #94a3b8;
        font-size: 0.7rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin: 1rem 0 0.5rem 0;
        padding-left: 0.35rem;
    }

    /* 调整列间距（更像仪表盘栅格） */
    div[data-testid="column"] {
        padding: 0.35rem 0.5rem;
    }

    /* 小屏幕优化 */
    @media (max-width: 900px) {
        .main .block-container {
            padding-top: 1.25rem;
        }
        .hero-title {
            font-size: 1.75rem;
        }
        .kpi-value {
            font-size: 1.6rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. 侧边栏
# ============================================================
with st.sidebar:
    # === 品牌区域 ===
    st.markdown("""
    <div class="sidebar-brand-card">
        <div class="sidebar-brand-icon">📊</div>
        <div class="sidebar-brand-title">销售预测系统</div>
        <div class="sidebar-brand-subtitle">Digital Salt · 数据驱动决策</div>
    </div>
    """, unsafe_allow_html=True)
    
    # === 首页入口（突出显示）===
    st.page_link("main.py", label="🏠 首页总览", icon=None)
    
    # === 功能模块标签 ===
    st.markdown("""
    <div class="sidebar-section-label">📁 功能模块</div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === 用户信息区域 ===
    show_user_info()
    
    st.markdown("---")
    
    # === 底部操作区 ===
    st.caption(f"🕐 上次更新: {datetime.now(BEIJING_TZ).strftime('%H:%M')}")
    
    if st.button("🔄 刷新全量数据", use_container_width=True):
        with st.spinner("正在同步飞书数据..."):
            data_manager.refresh_data()
        st.success("数据已更新")
        st.rerun()

# ============================================================
# 3. 数据处理逻辑
# ============================================================
df = pd.DataFrame()
try:
    df = data_manager.get_active_data()
    
    # 统一字段名处理，防止报错
    if "_final_amount" not in df.columns and "金额" in df.columns:
        df["_final_amount"] = df["金额"]
    if "_final_amount" not in df.columns:
        df["_final_amount"] = 0
        
    # 处理成单率解析
    def parse_rate(r):
        if isinstance(r, (int, float)): return r
        if isinstance(r, str):
            nums = re.findall(r'\d+', r)
            return sum(int(n) for n in nums) / len(nums) if nums else 0
        return 0
    
    if "成单率" in df.columns:
        df["_rate"] = df["成单率"].apply(parse_rate)
    else:
        df["_rate"] = 0

except Exception as e:
    st.error(f"数据加载异常: {e}")
    st.stop()

# ============================================================
# 4. 顶部 Hero 区域
# ============================================================
col_hero, col_action = st.columns([3, 1])

with col_hero:
    # 使用北京时间
    now_beijing = datetime.now(BEIJING_TZ)
    hour = now_beijing.hour
    greeting = "早安" if hour < 12 else "午安" if hour < 18 else "晚上好"
    
    st.markdown(f'<div class="hero-title">{greeting}，咸蛋们</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-subtitle">今天是 {now_beijing.strftime("%Y年%m月%d日")} · 让我们查看今日的业绩预测</div>', unsafe_allow_html=True)

# ============================================================
# 5. 自定义 KPI 卡片区域
# ============================================================
total_projects = len(df)
total_revenue = df["_final_amount"].sum()
high_prob_count = len(df[df["_rate"] >= 50])
avg_rate = df["_rate"].mean() if not df.empty else 0

# 定义卡片 HTML 生成函数
def kpi_card_html(label, value, sub_text, sub_class="trend-neutral"):
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub"><span class="{sub_class}">{sub_text}</span></div>
    </div>
    """

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(kpi_card_html("在跟项目总数", f"{total_projects}", "活跃项目", "trend-neutral"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card_html("预测总营收 (万)", f"¥{total_revenue:,.1f}", "基于加权计算", "trend-up"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card_html("高优项目 (>50%)", f"{high_prob_count}", "重点跟进", "trend-up"), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card_html("平均成单率", f"{avg_rate:.1f}%", "整体健康度", "trend-neutral"), unsafe_allow_html=True)

st.markdown("###") # 增加间距

# ============================================================
# 6. 核心图表与表格 (Card Layout)
# ============================================================

col_left, col_right = st.columns([1, 1.5], gap="large")

# --- 左侧：业务线分布 ---
with col_left:
    st.markdown('<div class="section-header">📊 业务营收占比</div>', unsafe_allow_html=True)
    with st.container(): # 这里其实可以用自定义CSS包裹，但Streamlit原生容器+Plotly透明背景已足够好
        if "业务线" in df.columns:
            biz_data = df.groupby("业务线")["_final_amount"].sum().reset_index()
            
            # 更加高级的配色
            colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#10b981', '#3b82f6']
            
            fig = px.pie(biz_data, values="_final_amount", names="业务线",
                         color_discrete_sequence=colors,
                         hole=0.6) # 甜甜圈图看起来更现代
            
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                margin=dict(t=20, b=20, l=20, r=20),
                height=350,
                paper_bgcolor='rgba(0,0,0,0)', # 透明背景融入
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Inter", size=13)
            )
            fig.update_traces(textposition='outside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("暂无业务线数据")

# --- 右侧：重点项目 TOP 表格 ---
with col_right:
    st.markdown('<div class="section-header">🎯 重点关注项目 (TOP 8)</div>', unsafe_allow_html=True)
    
    if not df.empty:
        # 准备表格数据
        table_cols = []
        if "客户" in df.columns: table_cols.append("客户")
        if "业务线" in df.columns: table_cols.append("业务线")
        
        # 构造用于显示的数据
        display_df = df.copy()
        
        # 【修复点 1】：直接使用 _rate (0-100的数值)，不要除以 100
        display_df["成单概率"] = display_df["_rate"] 
        display_df["预测金额"] = display_df["_final_amount"]
        
        final_cols = table_cols + ["成单概率", "预测金额"]
        
        # 排序取前8
        display_df = display_df.nlargest(8, "预测金额")[final_cols]
        
        st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True,
            height=350,
            column_config={
                "成单概率": st.column_config.ProgressColumn(
                    "成单率",
                    format="%d%%",   # 【修复点 2】：直接显示整数百分比
                    min_value=0,
                    max_value=100,   # 【修复点 3】：最大值设为 100，适配 0-100 的数值
                ),
                "预测金额": st.column_config.NumberColumn(
                    "预测金额 (万)",
                    format="¥ %.1f",
                ),
                "客户": st.column_config.TextColumn("客户名称", width="medium"),
                "业务线": st.column_config.TextColumn("业务线", width="small")
            }
        )
    else:
        st.info("暂无项目数据")

st.markdown("###") 

# ============================================================
# 7. 漏斗/概率分布 (底部通栏)
# ============================================================
st.markdown('<div class="section-header">📈 项目概率分布概览</div>', unsafe_allow_html=True)

if not df.empty:
    # 统计各区间的数量
    bins = [0, 30, 50, 80, 101]
    labels = ['低概率 (<30%)', '中概率 (30-50%)', '高概率 (50-80%)', '准成交 (≥80%)']
    df['prob_cat'] = pd.cut(df['_rate'], bins=bins, labels=labels, right=False)
    prob_counts = df['prob_cat'].value_counts().reindex(labels).reset_index()
    prob_counts.columns = ['类型', '数量']
    
    # 颜色映射
    color_map = {
        '低概率 (<30%)': '#94a3b8',
        '中概率 (30-50%)': '#60a5fa',
        '高概率 (50-80%)': '#818cf8',
        '准成交 (≥80%)': '#34d399'
    }

    fig_bar = px.bar(
        prob_counts, 
        x='数量', 
        y='类型', 
        orientation='h',
        text='数量',
        color='类型',
        color_discrete_map=color_map
    )
    
    fig_bar.update_layout(
        height=250,
        xaxis_title="",
        yaxis_title="",
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showgrid=False, showticklabels=False), # 隐藏X轴，追求极简
    )
    fig_bar.update_traces(textposition='auto', textfont_size=14)
    
    st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

# 页脚
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: #94a3b8; font-size: 0.8rem;'>
        Sales Forecast System &copy; 2025 · Powered by Feishu & Streamlit
    </div>
    """, 
    unsafe_allow_html=True
)

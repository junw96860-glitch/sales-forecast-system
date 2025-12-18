# main.py - 销售预测系统主入口
"""
简洁高端版首页 - UI 增强版
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re

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
    /* 全局字体与背景 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    
    .stApp {
        background-color: #f8f9fa; /* 极浅的灰背景，减少视觉疲劳 */
    }

    /* 顶部导航与边距调整 */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1280px;
    }

    /* 标题样式 */
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: -webkit-linear-gradient(120deg, #2563eb, #9333ea);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .hero-subtitle {
        color: #64748b;
        font-size: 1rem;
        margin-bottom: 2rem;
    }

    /* 自定义 KPI 卡片 */
    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #e2e8f0;
        transition: transform 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .kpi-label {
        color: #64748b;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    .kpi-value {
        color: #1e293b;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .kpi-sub {
        font-size: 0.85rem;
        margin-top: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }
    .trend-up { color: #10b981; background: #ecfdf5; padding: 2px 6px; border-radius: 4px; }
    .trend-neutral { color: #6366f1; background: #eef2ff; padding: 2px 6px; border-radius: 4px; }

    /* 图表容器容器 */
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        height: 100%;
    }
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #334155;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* 去除 Streamlit 默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 调整 Metric 间距 */
    div[data-testid="column"] {
        padding: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. 侧边栏
# ============================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3094/3094918.png", width=50) # 示例Logo
    st.title("Sales Force")
    st.markdown("---")
    show_user_info()
    st.markdown("---")
    from datetime import timezone, timedelta
    beijing_tz = timezone(timedelta(hours=8))
    st.caption(f"上次更新: {datetime.now(beijing_tz).strftime('%H:%M')}")
    
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
    hour = datetime.now().hour
    greeting = "早安" if hour < 12 else "午安" if hour < 18 else "晚上好"
    
    st.markdown(f'<div class="hero-title">{greeting}，咸蛋们</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-subtitle">今天是 {datetime.now().strftime("%Y年%m月%d日")} · 让我们查看今日的业绩预测</div>', unsafe_allow_html=True)

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
    """
    <div style='text-align: center; color: #94a3b8; font-size: 0.8rem;'>
        Sales Forecast System &copy; 2025 · Powered by Feishu & Streamlit
    </div>
    """, 
    unsafe_allow_html=True

)

# utils/page_init.py
"""
页面初始化模块

在每个页面开头调用 init_page() 进行：
1. 认证检查
2. 权限检查
3. 统一侧边栏样式
"""

import streamlit as st
import os
from datetime import datetime, timezone, timedelta

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))


def get_current_page_name() -> str:
    """
    获取当前页面名称
    
    从文件名推断，如 "3_💰_成本管理.py" -> "3_💰_成本管理"
    """
    try:
        # 尝试从 Streamlit 内部获取
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx and hasattr(ctx, 'page_script_hash'):
            # 这个方法在某些版本可能不可用
            pass
    except:
        pass
    
    # 从环境或调用栈推断
    try:
        import inspect
        for frame_info in inspect.stack():
            filename = frame_info.filename
            if "/pages/" in filename or "\\pages\\" in filename:
                basename = os.path.basename(filename)
                # 去掉 .py 后缀
                page_name = basename.replace(".py", "")
                return page_name
    except:
        pass
    
    return "unknown"


def apply_sidebar_styles():
    """
    应用统一的侧边栏样式
    """
    st.markdown("""
    <style>
    /* ============================================================
       强制显示侧边栏和展开按钮（覆盖登录页面的隐藏样式）
       使用更高优先级的选择器
       ============================================================ */
    html body [data-testid="stSidebar"],
    [data-testid="stSidebar"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        transform: none !important;
    }
    
    html body [data-testid="collapsedControl"],
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        z-index: 999999 !important;
        position: fixed !important;
    }
    
    /* ============================================================
       侧边栏样式
       ============================================================ */
    :root {
        --sb-bg-1: #f8fafc;
        --sb-bg-2: #f1f5f9;
        --sb-text: #0f172a;
        --sb-muted: #64748b;
        --sb-border: rgba(15, 23, 42, 0.10);
        --sb-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        --sb-radius: 12px;
    }

    /* 隐藏默认的 main 标签（保留中文导航） */
    [data-testid="stSidebarNav"] > ul > li:first-child {
        display: none;
    }

    /* Sidebar 背景与整体边界 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--sb-bg-1) 0%, var(--sb-bg-2) 100%) !important;
        border-right: 1px solid rgba(15, 23, 42, 0.06);
    }

    /* Sidebar 内容上边距（让品牌卡片更贴合） */
    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    /* 品牌卡片 */
    .sidebar-brand-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.15rem 1rem;
        border-radius: var(--sb-radius);
        margin: 0.25rem 0 0.75rem 0;
        text-align: center;
        box-shadow: var(--sb-shadow);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }
    .sidebar-brand-icon {
        font-size: 2rem;
        line-height: 1;
        margin-bottom: 0.35rem;
        filter: drop-shadow(0 2px 6px rgba(0,0,0,0.20));
    }
    .sidebar-brand-title {
        color: white;
        font-size: 1.08rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: 0.02em;
    }
    .sidebar-brand-subtitle {
        color: rgba(255,255,255,0.84);
        font-size: 0.75rem;
        margin-top: 0.25rem;
    }

    /* 导航链接：统一胶囊式按钮风格 */
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
        border-radius: 10px !important;
        padding: 0.55rem 0.75rem !important;
        margin: 0.15rem 0 !important;
        border: 1px solid rgba(15, 23, 42, 0.08) !important;
        background: rgba(255, 255, 255, 0.55) !important;
        color: var(--sb-text) !important;
        font-weight: 650 !important;
        transition: transform 0.12s ease, background 0.12s ease, border-color 0.12s ease, box-shadow 0.12s ease;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }

    [data-testid="stSidebarNav"] a:hover,
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {
        background: rgba(255, 255, 255, 0.85) !important;
        border-color: rgba(37, 99, 235, 0.22) !important;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
        transform: translateY(-1px);
    }

    /* 当前页面高亮（Streamlit 导航一般会带 aria-current="page"） */
    [data-testid="stSidebarNav"] a[aria-current="page"],
    [data-testid="stSidebar"] a[aria-current="page"] {
        background: linear-gradient(90deg, rgba(37, 99, 235, 0.10) 0%, rgba(147, 51, 234, 0.08) 100%) !important;
        border-color: rgba(37, 99, 235, 0.30) !important;
        color: #1d4ed8 !important;
        box-shadow: 0 10px 24px rgba(37, 99, 235, 0.10);
    }

    /* 首页按钮额外突出（保留你原先的 first-of-type 策略） */
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:first-of-type {
        background: linear-gradient(90deg, #f0f9ff 0%, #e0f2fe 100%) !important;
        border: 2px solid #7dd3fc !important;
        color: #0369a1 !important;
        font-weight: 750 !important;
    }

    /* 功能模块标签 */
    .sidebar-section-label {
        color: #94a3b8;
        font-size: 0.7rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin: 1rem 0 0.5rem 0;
        padding-left: 0.35rem;
    }

    /* Sidebar 内的按钮（如刷新数据）视觉统一 */
    [data-testid="stSidebar"] button[kind="secondary"],
    [data-testid="stSidebar"] button[kind="primary"] {
        border-radius: 10px !important;
        padding: 0.55rem 0.85rem !important;
        font-weight: 700 !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar_header():
    """
    渲染统一的侧边栏头部
    """
    with st.sidebar:
        # === 品牌区域 ===
        st.markdown("""
        <div class="sidebar-brand-card">
            <div class="sidebar-brand-icon">📊</div>
            <div class="sidebar-brand-title">销售预测系统</div>
            <div class="sidebar-brand-subtitle">Digital Salt · 数据驱动决策</div>
        </div>
        """, unsafe_allow_html=True)
        
        # === 首页入口（使用st.page_link避免状态丢失）===
        st.page_link("main.py", label="🏠 首页总览", icon=None)
        
        # === 功能模块标签 ===
        st.markdown("""
        <div class="sidebar-section-label">📁 功能模块</div>
        """, unsafe_allow_html=True)


def render_sidebar_footer():
    """
    渲染统一的侧边栏底部
    """
    from utils.auth import show_user_info
    from data.data_manager import data_manager
    
    with st.sidebar:
        st.markdown("---")
        
        # === 用户信息 ===
        show_user_info()
        
        st.markdown("---")
        
        # === 底部操作区 ===
        st.caption(f"🕐 上次更新: {datetime.now(BEIJING_TZ).strftime('%H:%M')}")
        
        if st.button("🔄 刷新全量数据", use_container_width=True, key="sidebar_refresh_btn"):
            with st.spinner("正在同步飞书数据..."):
                data_manager.set_state_store(st.session_state)
                data_manager.clear_cache()  # 清除缓存
                data_manager.get_active_data(force_reload=True)  # 强制重新加载
            st.success("数据已更新")
            st.rerun()


def init_page(page_name: str = None, show_sidebar: bool = True):
    """
    页面初始化
    
    Args:
        page_name: 页面名称，如果不提供则自动检测
        show_sidebar: 是否显示统一侧边栏（默认True）
    """
    from utils.auth import check_password, require_permission
    
    # 1. 认证检查
    if not check_password():
        st.stop()
    
    # 2. 权限检查
    if page_name is None:
        page_name = get_current_page_name()
    
    require_permission(page_name)
    
    # 3. 应用统一侧边栏样式
    if show_sidebar:
        apply_sidebar_styles()
        render_sidebar_header()
        render_sidebar_footer()

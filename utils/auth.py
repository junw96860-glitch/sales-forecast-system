# utils/auth.py
"""
权限管理模块

支持多角色权限控制：
- admin: 管理员，可访问所有页面
- sales: 销售负责人，只能访问指定页面
- viewer: 只读用户（可扩展）
"""

import streamlit as st
from typing import Optional, List, Dict

# ============================================================
# 角色配置
# ============================================================
ROLE_CONFIG: Dict[str, Dict] = {
    "admin": {
        "name": "管理员",
        "pages": "*",  # * 表示所有页面
        "description": "可访问所有功能"
    },
    "sales": {
        "name": "销售负责人",
        "pages": [
            "main",  # 首页
            "1_📊_数据看板",
            "2_📈_收入预测",
            "7_📋_项目明细",
            "9_📣_市场推广",
        ],
        "description": "可访问数据看板、收入预测、项目明细、市场推广"
    },
    # 可以继续扩展其他角色
    # "viewer": {
    #     "name": "只读用户",
    #     "pages": ["main", "1_📊_数据看板"],
    #     "description": "只能查看数据看板"
    # },
}


def _get_passwords() -> Dict[str, str]:
    """
    获取密码配置
    
    优先从 st.secrets["passwords"] 读取，格式：
    [passwords]
    admin = "111222"
    sales = "123456"
    """
    try:
        # 尝试从 secrets 的 [passwords] 节读取
        passwords = dict(st.secrets.get("passwords", {}))
        if passwords:
            return passwords
    except Exception:
        pass
    
    # 回退到单密码模式（兼容旧配置）
    try:
        single_pwd = st.secrets.get("APP_PASSWORD", "")
        if single_pwd:
            return {"admin": single_pwd}
    except Exception:
        pass
    
    return {}


def get_user_role(password: str) -> Optional[str]:
    """
    根据密码返回用户角色
    
    Returns:
        角色名称（如 "admin", "sales"）或 None
    """
    passwords = _get_passwords()
    
    for role, pwd in passwords.items():
        if password == pwd:
            return role
    
    return None


def check_password() -> bool:
    """
    显示登录界面并验证密码
    
    Returns:
        True 如果已登录，False 如果未登录
    """
    # 已登录
    if st.session_state.get("authenticated", False):
        return True
    
    # 显示登录界面

    st.markdown(
        """
        <style>
        /* =========================================================
           Login UI (DS Pro) - UI only
           ========================================================= */
        :root{
          --ds-bg:#f6f8fb;
          --ds-card:#ffffff;
          --ds-border:#e5e7eb;
          --ds-text:#0f172a;
          --ds-muted:#64748b;
          --ds-primary:#0ea5e9;
          --ds-primary-600:#0284c7;
          --ds-primary-100:rgba(14,165,233,.12);
          --ds-radius:16px;
          --ds-shadow:0 18px 55px rgba(2, 8, 23, .14);
          --ds-shadow-sm:0 6px 18px rgba(2, 8, 23, .08);
        }

        /* Hide sidebar during login (UI only) */
        [data-testid="stSidebar"], [data-testid="collapsedControl"]{
          display:none !important;
        }

        html, body, [data-testid="stAppViewContainer"]{
          background:
            radial-gradient(1200px 700px at 20% 0%, rgba(14,165,233,.14), transparent 55%),
            radial-gradient(900px 600px at 95% 10%, rgba(59,130,246,.10), transparent 60%),
            linear-gradient(180deg, #f8fafc 0%, var(--ds-bg) 100%);
          color: var(--ds-text);
        }

        section.main .block-container{
          padding-top: 2.5rem;
          max-width: 1100px;
        }

        /* Login card wrapper (works across widgets) */
        .login-shell:before{
        display: none;  /* 直接隐藏这个装饰 */
        }
        .login-shell:before{
          content:"";
          position:absolute;
          top:-120px; right:-120px;
          width: 240px; height: 240px;
          background: radial-gradient(circle at 30% 30%, rgba(14,165,233,.26), rgba(14,165,233,0));
        }
        .login-brand{ margin-bottom: 18px; position:relative; z-index:1; }
        .login-title{
          font-size: 2.1rem;
          font-weight: 850;
          letter-spacing: -0.02em;
          margin: 0;
          color: var(--ds-text);
        }
        .login-subtitle{
          margin-top: .35rem;
          font-size: .82rem;
          color: var(--ds-muted);
        }

        /* Inputs */
        div[data-baseweb="input"] input{
          border-radius: 12px !important;
          border: 1px solid rgba(148,163,184,.60) !important;
          background: #ffffff !important;
        }
        div[data-baseweb="input"] input:focus{
          box-shadow: 0 0 0 3px var(--ds-primary-100) !important;
          border-color: rgba(14,165,233,.7) !important;
        }

        /* Buttons */
        button[kind="primary"]{
          background: linear-gradient(180deg, var(--ds-primary) 0%, var(--ds-primary-600) 100%) !important;
          border: 1px solid rgba(2,132,199,.25) !important;
        }
        button[kind="primary"]:hover{
          box-shadow: var(--ds-shadow-sm) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="login-shell">', unsafe_allow_html=True)
        st.markdown('<div class="login-brand"><div class="login-title">咸数销售预测系统</div><div class="login-subtitle">现金流预测 · 收入预测 · 全面预算</div></div>', unsafe_allow_html=True)
        
        password = st.text_input("请输入访问密码", type="password", key="login_password")
        
        if st.button("登录", use_container_width=True, type="primary"):
            role = get_user_role(password)
            
            if role:
                st.session_state["authenticated"] = True
                st.session_state["user_role"] = role
                st.session_state["role_name"] = ROLE_CONFIG.get(role, {}).get("name", role)
                st.success(f"✅ 登录成功！欢迎，{st.session_state['role_name']}")
                st.rerun()
            else:
                st.error("❌ 密码错误，请重试")
        
        st.markdown("---")
        st.caption("如需帮助，请联系管理员")
        st.markdown("</div>", unsafe_allow_html=True)
    
    return False


def get_current_role() -> Optional[str]:
    """获取当前登录用户的角色"""
    return st.session_state.get("user_role")


def get_allowed_pages() -> List[str]:
    """获取当前用户可访问的页面列表"""
    role = get_current_role()
    if not role:
        return []
    
    config = ROLE_CONFIG.get(role, {})
    pages = config.get("pages", [])
    
    if pages == "*":
        return ["*"]  # 表示所有页面
    
    return pages


def can_access_page(page_name: str) -> bool:
    """
    检查当前用户是否可以访问指定页面
    
    Args:
        page_name: 页面名称，如 "3_💰_成本管理" 或 "成本管理"
    
    Returns:
        True 如果可以访问
    """
    allowed = get_allowed_pages()
    
    # 管理员可访问所有
    if "*" in allowed:
        return True
    
    # 检查页面名称是否在允许列表中
    for allowed_page in allowed:
        # 完全匹配
        if page_name == allowed_page:
            return True
        # 部分匹配（去掉序号和emoji后匹配）
        page_clean = page_name.split("_")[-1] if "_" in page_name else page_name
        allowed_clean = allowed_page.split("_")[-1] if "_" in allowed_page else allowed_page
        if page_clean == allowed_clean:
            return True
    
    return False


def require_permission(page_name: str):
    """
    页面权限装饰器 - 在页面开头调用
    
    如果用户无权访问，显示提示并停止执行
    
    Args:
        page_name: 当前页面名称
    """
    if not st.session_state.get("authenticated", False):
        st.warning("⚠️ 请先登录")
        st.stop()
    
    if not can_access_page(page_name):
        st.error("🚫 您没有权限访问此页面")
        st.info(f"当前角色：{st.session_state.get('role_name', '未知')}")
        
        # 显示可访问的页面
        allowed = get_allowed_pages()
        if allowed and "*" not in allowed:
            st.markdown("**您可以访问的页面：**")
            for page in allowed:
                if page != "main":
                    st.markdown(f"- {page}")
        
        st.stop()


def show_user_info():
    """在侧边栏显示用户信息和切换账号功能"""
    if st.session_state.get("authenticated", False):
        role = st.session_state.get("user_role", "")
        role_name = st.session_state.get("role_name", "用户")
        
        # 用户信息卡片
        st.markdown(
            f"""
            <div class="ds-card" style="
                padding: 14px 14px;
                border-left: 4px solid #0ea5e9;
                border-radius: 14px;
                margin-bottom: 10px;
            ">
                <div style="font-size: 12px; color: #64748b; font-weight: 750;">当前登录</div>
                <div style="font-size: 16px; color: #0f172a; font-weight: 850; margin-top: 2px;">{role_name}</div>
                <div style="font-size: 12px; color: #64748b; margin-top: 2px;">角色：{role}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
# 显示权限范围
        config = ROLE_CONFIG.get(role, {})
        description = config.get("description", "")
        if description:
            st.caption(f"📋 {description}")
        
        # 切换账号/退出登录
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 切换", use_container_width=True, help="切换到其他账号"):
                st.session_state["authenticated"] = False
                st.session_state["user_role"] = None
                st.session_state["role_name"] = None
                st.rerun()
        with col2:
            if st.button("🚪 退出", use_container_width=True, help="退出登录"):
                st.session_state["authenticated"] = False
                st.session_state["user_role"] = None
                st.session_state["role_name"] = None
                st.rerun()


def logout():
    """登出"""
    st.session_state["authenticated"] = False
    st.session_state["user_role"] = None
    st.session_state["role_name"] = None

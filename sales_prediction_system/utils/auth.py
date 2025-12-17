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
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 40px;
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    .login-title {
        text-align: center;
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 30px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="login-title">🔐 销售预测系统</div>', unsafe_allow_html=True)
        
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
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 15px;
            border-radius: 10px;
            color: white;
            margin-bottom: 10px;
        ">
            <div style="font-size: 14px; opacity: 0.9;">当前登录</div>
            <div style="font-size: 18px; font-weight: bold;">👤 {role_name}</div>
        </div>
        """, unsafe_allow_html=True)
        
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
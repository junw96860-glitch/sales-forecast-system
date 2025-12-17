# utils/page_init.py
"""
页面初始化模块

在每个页面开头调用 init_page() 进行：
1. 认证检查
2. 权限检查
"""

import streamlit as st
import os


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


def init_page(page_name: str = None):
    """
    页面初始化
    
    Args:
        page_name: 页面名称，如果不提供则自动检测
    """
    from utils.auth import check_password, require_permission
    
    # 1. 认证检查
    if not check_password():
        st.stop()
    
    # 2. 权限检查
    if page_name is None:
        page_name = get_current_page_name()
    
    require_permission(page_name)
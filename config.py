# config.py - 适配 Streamlit Cloud 的配置文件
"""
配置管理模块

在 Streamlit Cloud 部署时，从 st.secrets 读取配置
在本地开发时，从 .streamlit/secrets.toml 读取
"""

import streamlit as st
from typing import Optional


def _get_secret(key: str, default: str = "") -> str:
    """
    从 Streamlit Secrets 获取配置
    
    优先级：
    1. st.secrets（Streamlit Cloud 或本地 .streamlit/secrets.toml）
    2. 默认值
    """
    try:
        # 尝试从 secrets 读取
        value = st.secrets.get(key, None)
        if value is not None:
            return str(value)
        return default
    except Exception:
        # secrets 未配置时返回默认值
        return default


def _get_secret_nested(section: str, key: str, default: str = "") -> str:
    """获取嵌套的 secret 配置，如 [passwords] 下的值"""
    try:
        return str(st.secrets[section][key])
    except Exception:
        return default


# ========================================
# 飞书 API 配置
# ========================================
FEISHU_APP_ID: str = _get_secret("FEISHU_APP_ID")
FEISHU_APP_SECRET: str = _get_secret("FEISHU_APP_SECRET")
FEISHU_APP_TOKEN: str = _get_secret("FEISHU_APP_TOKEN")

# ========================================
# 销售台账表 ID
# ========================================
SALES_TABLES = {
    "光谱设备/服务": _get_secret("TABLE_ID_SPECTRUM"),
    "配液设备": _get_secret("TABLE_ID_LIQUID"),
    "自动化项目": _get_secret("TABLE_ID_AUTO"),
}

OVERRIDES_TABLE_ID: str = _get_secret("TABLE_ID_OVERRIDES")
PAYMENT_SCHEDULE_TABLE_ID: str = _get_secret("TABLE_ID_PAYMENT")

# ========================================
# 工时统计表 ID
# ========================================
WORKTIME_TABLE_ID: str = _get_secret("WORKTIME_TABLE_ID")

# ========================================
# 订单现金流表 ID
# ========================================
ORDER_CASHFLOW_TABLE_ID: str = _get_secret("ORDER_CASHFLOW_TABLE_ID")

# ========================================
# 市场推广表 ID
# ========================================
MARKETING_TABLES = {
    "content": _get_secret("TABLE_ID_MARKETING_CONTENT"),    # 市场内容记录
    "leads": _get_secret("TABLE_ID_MARKETING_LEADS"),        # 市场线索池
    "budget": _get_secret("TABLE_ID_MARKETING_BUDGET"),      # 市场推广预算
    "accounts": _get_secret("TABLE_ID_MARKETING_ACCOUNTS"),  # 市场账号运营
}

# 便捷访问
TABLE_ID_MARKETING_CONTENT: str = MARKETING_TABLES["content"]
TABLE_ID_MARKETING_LEADS: str = MARKETING_TABLES["leads"]
TABLE_ID_MARKETING_BUDGET: str = MARKETING_TABLES["budget"]
TABLE_ID_MARKETING_ACCOUNTS: str = MARKETING_TABLES["accounts"]

# 产品到业务线的映射（用于线索同步）
PRODUCT_TO_BUSINESS_LINE = {
    "在线光谱仪": "光谱设备/服务",
    "配液设备": "配液设备",
    "自动化系统": "自动化项目",
}

# 产品到销售表的映射（用于线索同步）
PRODUCT_TO_SALES_TABLE = {
    "在线光谱仪": _get_secret("TABLE_ID_SPECTRUM"),
    "配液设备": _get_secret("TABLE_ID_LIQUID"),
    "自动化系统": _get_secret("TABLE_ID_AUTO"),
}

# ========================================
# 访问控制
# ========================================
APP_PASSWORD: str = _get_secret("APP_PASSWORD")


def get_user_role(password: str) -> Optional[str]:
    """
    根据密码返回用户角色
    
    Returns:
        "admin" / "editor" / "viewer" / None
    """
    try:
        passwords = st.secrets.get("passwords", {})
        for role, pwd in passwords.items():
            if password == pwd:
                return role
    except Exception:
        pass
    
    # 单密码模式
    if APP_PASSWORD and password == APP_PASSWORD:
        return "admin"
    
    return None


# ========================================
# 配置验证
# ========================================
def is_configured() -> bool:
    """检查是否已完成基本配置"""
    return bool(FEISHU_APP_ID and FEISHU_APP_SECRET and FEISHU_APP_TOKEN)


def is_marketing_configured() -> bool:
    """检查市场推广模块是否已配置"""
    return bool(
        TABLE_ID_MARKETING_CONTENT and
        TABLE_ID_MARKETING_LEADS and
        TABLE_ID_MARKETING_BUDGET and
        TABLE_ID_MARKETING_ACCOUNTS
    )


def get_config_status() -> dict:
    """获取配置状态（用于调试）"""
    return {
        "feishu_app_id": "✅" if FEISHU_APP_ID else "❌",
        "feishu_app_secret": "✅" if FEISHU_APP_SECRET else "❌",
        "feishu_app_token": "✅" if FEISHU_APP_TOKEN else "❌",
        "sales_tables": {
            name: "✅" if table_id else "❌"
            for name, table_id in SALES_TABLES.items()
        },
        "overrides_table": "✅" if OVERRIDES_TABLE_ID else "❌",
        "payment_table": "✅" if PAYMENT_SCHEDULE_TABLE_ID else "❌",
        "worktime_table": "✅" if WORKTIME_TABLE_ID else "❌",
        "order_cashflow_table": "✅" if ORDER_CASHFLOW_TABLE_ID else "❌",
        "marketing_tables": {
            name: "✅" if table_id else "❌"
            for name, table_id in MARKETING_TABLES.items()
        },
        "password_enabled": "✅" if APP_PASSWORD else "❌ (无密码保护)",
    }


# ========================================
# 调试模式
# ========================================
DEBUG: bool = _get_secret("DEBUG", "false").lower() == "true"

# config/payment_templates.py
"""
付款节奏模板配置

每个模板定义了：
- name: 付款节点名称
- ratio: 付款比例（所有节点比例之和应为 1.0）
- offset_months: 相对于基准日期（交付时间）的月数偏移
  - 0 = 交付时间
  - -1 = 交付前1个月
  - 1 = 交付后1个月
  - 12 = 交付后12个月（通常用于质保金）
"""

PAYMENT_TEMPLATES = {
    "标准三笔(5-4-1)": [
        {"name": "首付款", "ratio": 0.5, "offset_months": -1, "base": "开始时间"},
        {"name": "到货验收款", "ratio": 0.4, "offset_months": 0, "base": "交付时间"},
        {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
    ],
    "标准三笔(3-6-1)": [
        {"name": "首付款", "ratio": 0.3, "offset_months": -1, "base": "开始时间"},
        {"name": "到货验收款", "ratio": 0.6, "offset_months": 0, "base": "交付时间"},
        {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
    ],
    "四笔分期(3-3-3-1)": [
        {"name": "首付款", "ratio": 0.3, "offset_months": 0, "base": "开始时间"},
        {"name": "到货款", "ratio": 0.3, "offset_months": 0, "base": "交付时间"},
        {"name": "验收款", "ratio": 0.3, "offset_months": 1, "base": "交付时间"},
        {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
    ],
    "四笔分期(2-3-4-1)": [
        {"name": "预付款", "ratio": 0.2, "offset_months": 0, "base": "开始时间"},
        {"name": "发货款", "ratio": 0.3, "offset_months": -1, "base": "交付时间"},
        {"name": "验收款", "ratio": 0.4, "offset_months": 0, "base": "交付时间"},
        {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
    ],
    "五笔分期(2-2-3-2-1)": [
        {"name": "预付款", "ratio": 0.2, "offset_months": 0, "base": "开始时间"},
        {"name": "发货款", "ratio": 0.2, "offset_months": -1, "base": "交付时间"},
        {"name": "到货款", "ratio": 0.3, "offset_months": 0, "base": "交付时间"},
        {"name": "验收款", "ratio": 0.2, "offset_months": 1, "base": "交付时间"},
        {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
    ],
    "设备租赁(等额分期)": [
        {"name": "首付款", "ratio": 0.2, "offset_months": 0, "base": "开始时间"},
        {"name": "季付1", "ratio": 0.2, "offset_months": 3, "base": "开始时间"},
        {"name": "季付2", "ratio": 0.2, "offset_months": 6, "base": "开始时间"},
        {"name": "季付3", "ratio": 0.2, "offset_months": 9, "base": "开始时间"},
        {"name": "尾款", "ratio": 0.2, "offset_months": 12, "base": "开始时间"},
    ],
    "全款": [
        {"name": "全款", "ratio": 1.0, "offset_months": 0, "base": "开始时间"},
    ],
    "货到付款": [
        {"name": "全款", "ratio": 1.0, "offset_months": 0, "base": "交付时间"},
    ],
}

# 默认模板（按业务线）
DEFAULT_TEMPLATE_BY_BUSINESS = {
    "光谱设备/服务": "标准三笔(5-4-1)",
    "配液设备": "标准三笔(5-4-1)",
    "自动化项目": "四笔分期(3-3-3-1)",
}

# 默认模板（通用）
DEFAULT_TEMPLATE = "标准三笔(5-4-1)"


def get_template(template_name: str) -> list:
    """获取模板配置"""
    return PAYMENT_TEMPLATES.get(template_name, PAYMENT_TEMPLATES[DEFAULT_TEMPLATE])


def get_default_template_for_business(business_line: str) -> str:
    """根据业务线获取默认模板名称"""
    return DEFAULT_TEMPLATE_BY_BUSINESS.get(business_line, DEFAULT_TEMPLATE)


def get_all_template_names() -> list:
    """获取所有模板名称"""
    return list(PAYMENT_TEMPLATES.keys())


def validate_template(stages: list) -> tuple:
    """
    验证付款节点配置
    
    Returns:
        (is_valid, error_message)
    """
    if not stages:
        return False, "付款节点不能为空"
    
    total_ratio = sum(s.get("ratio", 0) for s in stages)
    if abs(total_ratio - 1.0) > 0.01:
        return False, f"付款比例之和应为 100%，当前为 {total_ratio * 100:.1f}%"
    
    for i, stage in enumerate(stages):
        if not stage.get("name"):
            return False, f"第 {i+1} 个节点缺少名称"
        if stage.get("ratio", 0) <= 0:
            return False, f"第 {i+1} 个节点比例必须大于 0"
    
    return True, ""
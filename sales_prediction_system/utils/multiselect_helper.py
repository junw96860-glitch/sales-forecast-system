# utils/multiselect_helper.py
"""
飞书多选字段处理工具

飞书多维表格的多选字段返回格式为 list，如 ['产品', '服务']
本模块提供：
1. 解析和显示（去掉方括号）
2. 多选筛选功能
3. 写回飞书时的格式转换
"""

import pandas as pd
import streamlit as st
from typing import List, Set, Optional, Union, Any


def parse_multiselect_value(value: Any) -> List[str]:
    """
    解析飞书多选字段的值，统一返回列表
    
    Args:
        value: 可能是 list, str, 或 None
        
    Returns:
        字符串列表
        
    Examples:
        >>> parse_multiselect_value(['产品', '服务'])
        ['产品', '服务']
        >>> parse_multiselect_value('产品')
        ['产品']
        >>> parse_multiselect_value("['产品', '服务']")  # 字符串化的列表
        ['产品', '服务']
        >>> parse_multiselect_value(None)
        []
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    
    if isinstance(value, str):
        value = value.strip()
        # 处理字符串化的列表 "['a', 'b']"
        if value.startswith('[') and value.endswith(']'):
            try:
                import ast
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if v]
            except (ValueError, SyntaxError):
                pass
        # 普通字符串
        if value:
            return [value]
    
    return []


def format_multiselect_display(value: Any, separator: str = ", ") -> str:
    """
    将多选值格式化为显示字符串（去掉方括号）
    
    Args:
        value: 多选字段值
        separator: 分隔符，默认逗号+空格
        
    Returns:
        格式化后的字符串
        
    Examples:
        >>> format_multiselect_display(['产品', '服务'])
        '产品, 服务'
        >>> format_multiselect_display(['产品'])
        '产品'
        >>> format_multiselect_display(None)
        ''
    """
    items = parse_multiselect_value(value)
    return separator.join(items)


def get_all_multiselect_options(df: pd.DataFrame, column: str) -> List[str]:
    """
    获取 DataFrame 中某多选列的所有唯一选项
    
    Args:
        df: DataFrame
        column: 列名
        
    Returns:
        去重并排序后的选项列表
    """
    if column not in df.columns:
        return []
    
    all_options: Set[str] = set()
    
    for value in df[column].dropna():
        items = parse_multiselect_value(value)
        all_options.update(items)
    
    return sorted(list(all_options))


def convert_column_for_display(df: pd.DataFrame, column: str, separator: str = ", ") -> pd.DataFrame:
    """
    将 DataFrame 中的多选列转换为显示友好的格式
    
    Args:
        df: DataFrame
        column: 要转换的列名
        separator: 分隔符
        
    Returns:
        转换后的 DataFrame（原地修改）
    """
    if column in df.columns:
        df[column] = df[column].apply(lambda x: format_multiselect_display(x, separator))
    return df


def filter_by_multiselect(
    df: pd.DataFrame, 
    column: str, 
    selected_values: List[str],
    match_mode: str = "any"
) -> pd.DataFrame:
    """
    根据多选字段筛选 DataFrame
    
    Args:
        df: DataFrame
        column: 多选列名
        selected_values: 用户选择的筛选值列表
        match_mode: 
            - "any": 包含任意一个选中值即匹配（OR 逻辑）
            - "all": 必须包含所有选中值才匹配（AND 逻辑）
            
    Returns:
        筛选后的 DataFrame
    """
    if not selected_values or column not in df.columns:
        return df
    
    selected_set = set(selected_values)
    
    def match_row(value):
        items = set(parse_multiselect_value(value))
        if match_mode == "all":
            return selected_set.issubset(items)
        else:  # "any"
            return bool(items & selected_set)
    
    mask = df[column].apply(match_row)
    return df[mask]


def render_multiselect_filter(
    df: pd.DataFrame,
    column: str,
    label: Optional[str] = None,
    key: Optional[str] = None,
    default_all: bool = True,
    help_text: Optional[str] = None
) -> List[str]:
    """
    渲染多选筛选器 UI 组件
    
    Args:
        df: DataFrame
        column: 多选列名
        label: 显示标签（默认使用列名）
        key: Streamlit 组件的 key
        default_all: 是否默认选择全部
        help_text: 帮助文本
        
    Returns:
        用户选择的值列表（空列表表示"全部"）
    """
    options = get_all_multiselect_options(df, column)
    
    if not options:
        return []
    
    display_label = label or f"{column}筛选"
    widget_key = key or f"filter_{column}"
    
    # 添加"全部"选项
    all_option = "全部"
    
    selected = st.multiselect(
        display_label,
        options=[all_option] + options,
        default=[all_option] if default_all else [],
        key=widget_key,
        help=help_text
    )
    
    # 如果选择了"全部"或者没有选择，返回空列表（表示不筛选）
    if all_option in selected or not selected:
        return []
    
    return selected


def render_selectbox_filter(
    df: pd.DataFrame,
    column: str,
    label: Optional[str] = None,
    key: Optional[str] = None,
    include_all: bool = True
) -> Optional[str]:
    """
    渲染单选下拉筛选器（适用于只想选一个值的场景）
    
    Args:
        df: DataFrame
        column: 多选列名
        label: 显示标签
        key: Streamlit 组件的 key
        include_all: 是否包含"全部"选项
        
    Returns:
        选择的值，或 None 表示"全部"
    """
    options = get_all_multiselect_options(df, column)
    
    if not options:
        return None
    
    display_label = label or f"{column}筛选"
    widget_key = key or f"selectbox_{column}"
    
    if include_all:
        options = ["全部"] + options
    
    selected = st.selectbox(
        display_label,
        options=options,
        key=widget_key
    )
    
    if selected == "全部":
        return None
    
    return selected


def prepare_for_feishu_write(value: Union[str, List[str]]) -> List[str]:
    """
    准备写回飞书的多选值格式
    
    飞书多选字段需要 list 格式
    
    Args:
        value: 字符串或列表
        
    Returns:
        列表格式
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # 如果是逗号分隔的字符串，拆分
        if ',' in value:
            return [v.strip() for v in value.split(',') if v.strip()]
        return [value] if value.strip() else []
    return []
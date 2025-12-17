# utils/display_helper.py - 显示优化工具
import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from typing import Callable
import time
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
    _AGGRID_AVAILABLE = True
except ImportError:
    _AGGRID_AVAILABLE = False


class DisplayHelper:
    """显示优化助手 - 提供高性能的数据展示组件"""

    @staticmethod
    def apply_global_styles() -> None:
        """
        全局 UI 样式（公用视觉）。
        说明：在 Streamlit 多页面切换时，建议每次页面运行都注入一次，避免切页样式丢失。
        """
        st.markdown(
            """
    <style>
    /* ========== Metrics ========== */
    div[data-testid="stMetric"]{
        background-color:#f0f2f6;
        border-radius:10px;
        padding:15px;
        text-align:center;
        box-shadow:0 2px 4px rgba(0,0,0,0.1);
    }
    .stMetric{
        background-color:#f0f2f6;
        border-radius:10px;
        padding:15px;
        text-align:center;
        box-shadow:0 2px 4px rgba(0,0,0,0.1);
    }

    div[data-testid="stMetricLabel"], .stMetric .stMetric-label{
        font-size:14px;
        font-weight:700;
        color:#4a4a4a;
    }
    div[data-testid="stMetricValue"], .stMetric .stMetric-value{
        font-size:24px;
        font-weight:800;
        color:#1f77b4;
    }
    .stMetric .stMetric-delta{
        font-size:16px;
        color:#2ca02c;
    }

    /* ========== DataFrame container ========== */
    div[data-testid="stDataFrame"], .stDataFrame{
        border:1px solid #e0e0e0;
        border-radius:8px;
        overflow:hidden;
    }

    /* ========== Tabs ========== */
    .stTabs [data-baseweb="tab-list"]{ gap:0px; }
    .stTabs [data-baseweb="tab"]{
        height:50px;
        white-space:pre-wrap;
        background-color:#f0f2f6;
        border-radius:8px 8px 0px 0px;
        padding:10px 20px;
        line-height:1.2;
    }
    .stTabs [aria-selected="true"]{
        background-color:#1f77b4;
        color:white;
        border-radius:8px 8px 0px 0px;
    }

    /* ========== Callout boxes ========== */
    .info-box{
        background-color:#e8f4fd;
        border-left:5px solid #2196F3;
        padding:15px;
        margin:10px 0;
        border-radius:5px;
    }
    .warning-box{
        background-color:#fff3e0;
        border-left:5px solid #FF9800;
        padding:15px;
        margin:10px 0;
        border-radius:5px;
    }
    .success-box{
        background-color:#e8f5e9;
        border-left:5px solid #4CAF50;
        padding:15px;
        margin:10px 0;
        border-radius:5px;
    }
    .error-box{
        background-color:#ffebee;
        border-left:5px solid #f44336;
        padding:15px;
        margin:10px 0;
        border-radius:5px;
    }
    </style>
            """,
            unsafe_allow_html=True,
        )


    @staticmethod
    def render_aggrid_table(
        dataframe: pd.DataFrame,
        key: str,
        page_size: int = 10,
        height: int = 400,
        enable_selection: bool = True,
        enable_filtering: bool = True,
        enable_sorting: bool = True,
        custom_columns: Optional[Dict[str, Any]] = None,
        theme: str = "alpine",
        use_container_width: bool = True,
        return_mode: str = "filtered"  # "filtered", "selected", "all"
    ) -> Any:
        """使用AgGrid渲染高性能表格

        Args:
            dataframe: 要显示的DataFrame
            key: 唯一的key，用于Streamlit状态管理
            page_size: 每页显示行数
            height: 表格高度
            enable_selection: 启用行选择
            enable_filtering: 启用过滤
            enable_sorting: 启用排序
            custom_columns: 自定义列配置
            theme: 主题名称
            use_container_width: 使用容器宽度
            return_mode: 返回模式
        """
        if not _AGGRID_AVAILABLE:
            st.warning("⚠️ AgGrid未安装，使用标准表格渲染")
            return DisplayHelper.render_paginated_table(
                dataframe, page_size, height
            )

        try:
            # 构建Grid配置
            gb = GridOptionsBuilder.from_dataframe(dataframe)

            # 配置默认选项
            gb.configure_selection(
                'multiple' if enable_selection else 'single',
                use_checkbox=enable_selection
            )

            gb.configure_default_column(
                groupable=False,
                value=True,
                enableRowGroup=True,
                aggFunc='sum',
                editable=False
            )

            # 配置分页
            gb.configure_pagination(enabled=True, paginationPageSize=page_size)

            # 配置过滤
            if enable_filtering:
                gb.configure_side_bar()

            # 自定义列配置
            if custom_columns:
                for col_name, col_config in custom_columns.items():
                    if col_name in dataframe.columns:
                        gb.configure_column(col_name, **col_config)

            # 特定类型的列优化
            for col in dataframe.columns:
                if "日期" in col or "时间" in col:
                    gb.configure_column(col, filter="agDateColumnFilter")
                elif pd.api.types.is_numeric_dtype(dataframe[col]):
                    gb.configure_column(col, filter="agNumberColumnFilter")
                else:
                    gb.configure_column(col, filter="agTextColumnFilter")

            # 构建选项
            gridOptions = gb.build()

            # 渲染表格
            grid_response = AgGrid(
                dataframe,
                gridOptions=gridOptions,
                height=height,
                theme=theme,
                enable_enterprise_modules=True,
                key=key,
                update_mode="MODEL_CHANGED" if enable_selection else "NO_UPDATE",
                data_return_mode="FILTERED_AND_SORTED" if return_mode == "filtered" else "AS_INPUT",
                fit_columns_on_grid_load=True,
                use_container_width=use_container_width
            )

            return grid_response

        except Exception as e:
            st.error(f"AgGrid渲染失败: {str(e)}")
            return DisplayHelper.render_paginated_table(
                dataframe, page_size, height
            )

    @staticmethod
    def render_paginated_table(
        dataframe: pd.DataFrame,
        page_size: int = 10,
        height: int = 400,
        key: Optional[str] = None
    ) -> pd.DataFrame:
        """标准的分页表格渲染

        Args:
            dataframe: 要显示的DataFrame
            page_size: 每页显示行数
            height: 表格高度
            key: 分页控件的唯一key
        """
        if dataframe.empty:
            st.info("📊 暂无数据")
            return dataframe

        # 计算总页数
        total_rows = len(dataframe)
        total_pages = (total_rows + page_size - 1) // page_size

        # 分页控件
        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            if key is None:
                key = "paginated_table"
            current_page = st.session_state.get(f"{key}_page", 1)

        with col2:
            page_options = list(range(1, total_pages + 1))
            current_page = st.selectbox(
                "选择页码",
                options=page_options,
                index=current_page - 1,
                key=f"{key}_page_selector"
            )

        with col3:
            st.metric("总记录数", total_rows)

        # 计算当前页数据
        start_idx = (current_page - 1) * page_size
        end_idx = min(start_idx + page_size, total_rows)
        current_data = dataframe.iloc[start_idx:end_idx]

        # 显示当前页数据
        st.dataframe(
            current_data,
            use_container_width=True,
            height=min(height, page_size * 35 + 50)
        )

        # 翻页按钮
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            if current_page > 1:
                if st.button("⬅️ 上一页", key=f"{key}_prev"):
                    st.session_state[f"{key}_page"] = current_page - 1
                    st.rerun()

        with col3:
            if current_page < total_pages:
                if st.button("下一页 ➡️", key=f"{key}_next"):
                    st.session_state[f"{key}_page"] = current_page + 1
                    st.rerun()

        return current_data

    @staticmethod
    def create_download_button(
        dataframe: pd.DataFrame,
        filename: str,
        label: str = "📥 下载数据",
        file_format: str = "csv",
        include_index: bool = False,
        mime: str = "text/csv"
    ) -> bool:
        """创建数据下载按钮

        Args:
            dataframe: 要下载的DataFrame
            filename: 文件名（不含扩展名）
            label: 按钮标签
            file_format: 文件格式 ('csv', 'excel', 'json')
            include_index: 是否包含索引
            mime: MIME类型

        Returns:
            是否下载成功
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            if file_format.lower() == "csv":
                csv = dataframe.to_csv(index=include_index).encode('utf-8')
                st.download_button(
                    label=f"{filename}_{timestamp}.csv",
                    data=csv,
                    file_name=f"{filename}_{timestamp}.csv",
                    mime=mime
                )

            elif file_format.lower() == "excel":
                # 创建Excel文件
                import io
                buffer = io.BytesIO()
                dataframe.to_excel(buffer, index=include_index, engine='openpyxl')
                buffer.seek(0)

                st.download_button(
                    label=f"{label} ({filename}_{timestamp}.xlsx)",
                    data=buffer,
                    file_name=f"{filename}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            elif file_format.lower() == "json":
                json_data = dataframe.to_json(orient='records', force_ascii=False, indent=2)
                st.download_button(
                    label=f"{label} ({filename}_{timestamp}.json)",
                    data=json_data,
                    file_name=f"{filename}_{timestamp}.json",
                    mime="application/json"
                )

            return True

        except Exception as e:
            st.error(f"文件生成失败: {str(e)}")
            return False

    @staticmethod
    def create_metric_card(
        title: str,
        value: Union[int, float, str],
        delta: Optional[str] = None,
        delta_color: str = "normal",
        help_text: Optional[str] = None,
        col_width: int = 1
    ):
        """创建美观的指标卡片

        Args:
            title: 标题
            value: 值
            delta: 变化值
            delta_color: 变化值颜色
            help_text: 帮助文本
            col_width: 列宽
        """
        with st.container():
            # delta HTML 单独组装，避免在 f""" """ 里嵌套复杂 f-string
            delta_html = ""
            if delta:
                color = "#28a745" if "+" in str(delta) else "#dc3545"
                delta_html = f'<p style="margin: 0; color: {color};">{delta}</p>'

            st.markdown(
                f"""
                <div class="metric-card" style="
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                    border-left: 4px solid #1f77b4;
                    margin: 5px 0;
                ">
                    <h4 style="margin: 0; color: #495057; font-size: 14px;">{title}</h4>
                    <h2 style="margin: 5px 0; color: #343a40;">{value}</h2>
                    {delta_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if help_text:
                st.caption(help_text)

    @staticmethod
    def create_expander_section(
        title: str,
        content_func: Callable,
        is_open: bool = False,
        section_key: str = None,
        help_text: str = None
    ):
        """创建可折叠的内容区域

        Args:
            title: 标题
            content_func: 内容函数
            is_open: 初始状态
            section_key: 状态key
            help_text: 帮助文本
        """
        if section_key is None:
            section_key = title.replace(" ", "_").lower()

        # 获取缓存的状态
        expanded = st.session_state.get(f"{section_key}_expanded", is_open)

        # 使用expander
        with st.expander(
            f"{title} {'〜' if expanded else '» '}",
            expanded=expanded,
        ):
            # 帮助文本（如果有）
            if help_text:
                st.caption(help_text)

            # 执行内容函数
            content_func()

            # 更新状态
            if st.button(f"收起 {title}", key=f"{section_key}_close", use_container_width=True):
                st.session_state[f"{section_key}_expanded"] = False
                st.rerun()

    @staticmethod
    def render_data_quality_indicator(
        df: pd.DataFrame,
        show_details: bool = True
    ) -> Dict[str, Any]:
        """渲染数据质量指标

        Args:
            df: DataFrame
            show_details: 是否显示详情

        Returns:
            质量指标字典
        """
        if df.empty:
            st.warning("⚠️ 数据为空")
            return {"quality_score": 0, "warnings": []}

        quality_checks = []
        warnings = []
        warnings_count = 0

        # 1. 完整性检查
        missing_percentages = {}
        for col in df.columns:
            missing_pct = df[col].isna().mean() * 100
            missing_percentages[col] = missing_pct

            if missing_pct > 50:
                warnings.append(f"{col} 缺失率 {missing_pct:.1f}%")
                warnings_count += 1

        # 2. 数据质量得分
        avg_missing = np.mean(list(missing_percentages.values()))
        quality_score = max(0, 100 - avg_missing - warnings_count * 5)

        # 3. 渲染指标
        col1, col2, col3 = st.columns(3)

        with col1:
            quality_color = (
                "#28a745" if quality_score >= 90 else
                "#ffc107" if quality_score >= 70 else
                "#dc3545"
            )
            st.metric(
                "数据质量",
                f"{quality_score:.0f}%",
                delta_color="off"
            )

        with col2:
            st.metric("记录数", len(df))

        with col3:
            st.metric("字段数", len(df.columns))

        # 4. 详细信息
        if show_details and warnings:
            with st.expander("📋 数据质量详情"):
                for warning in warnings:
                    st.warning(warning)

                # 显示缺失率图表
                missing_df = pd.DataFrame(
                    list(missing_percentages.items()),
                    columns=['字段', '缺失率']
                )

                fig = px.bar(
                    missing_df[missing_df['缺失率'] > 0],
                    x='字段',
                    y='缺失率'
                )
                st.plotly_chart(fig, use_container_width=True)

        return {
            "quality_score": quality_score,
            "warnings": warnings,
            "missing_percentages": missing_percentages
        }

    @staticmethod
    def create_loading_spinner(
        text: str = "正在加载数据..."
    ):
        """创建加载动画
        Args:
            text: 加载文本
        """
        with st.spinner(text):
            # 显示加载状态
            progress_bar = st.progress(0)
            for i in range(100):
                time.sleep(0.01)
                progress_bar.progress(i + 1)
            progress_bar.empty()

    @staticmethod
    def format_number_with_unit(
        value: Union[int, float],
        unit: str = "万",
        precision: int = 2,
        show_plus: bool = False
    ) -> str:
        """格式化数字和单位

        Args:
            value: 数值
            unit: 单位
            precision: 精度
            show_plus: 是否显示正号
        """
        if value is None:
            return "--"

        formatted_value = f"{value:.{precision}f}"

        # 移除不必要的.0
        if precision > 0:
            formatted_value = formatted_value.rstrip('0').rstrip('.')

        # 添加符号
        if show_plus and value > 0:
            formatted_value = f"+{formatted_value}"

        return f"{formatted_value}{unit}"

    @staticmethod
    def create_download_zip_button(
        file_dict: Dict[str, pd.DataFrame],
        zip_filename: str,
        label: str = "📦 批量下载"
    ):
        """创建批量下载Zip文件

        Args:
            file_dict: {文件名: DataFrame} 字典
            zip_filename: zip文件名
            label: 按钮标签
        """
        try:
            import zipfile
            import io

            # 创建内存中的zip文件
            buffer = io.BytesIO()

            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                for filename, df in file_dict.items():
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, index=False)
                    csv_buffer.seek(0)

                    # 添加CSV到zip
                    zip_file.writestr(
                        f"{filename}_{timestamp}.csv",
                        csv_buffer.getvalue()
                    )

            # 用户下载
            buffer.seek(0)
            st.download_button(
                label=label,
                data=buffer,
                file_name=f"{zip_filename}_{timestamp}.zip",
                mime="application/zip"
            )

        except ImportError:
            st.error("⚠️ 需要安装 zipfile 模块")
        except Exception as e:
            st.error(f"文件压缩失败: {str(e)}")

    @staticmethod
    def create_data_summary_tooltip(
        df: pd.DataFrame,
        summary_type: str = "quick"
    ) -> str:
        """创建数据摘要工具提示

        Args:
            df: DataFrame
            summary_type: 摘要类型 ('quick', 'full')

        Returns:
            摘要字符串
        """
        if df.empty:
            return "暂无数据"

        if summary_type == "quick":
            return f"📊 {len(df)} 条记录 · {len(df.columns)} 个字段"
        else:
            numeric_cols = len(df.select_dtypes(include=['number']).columns)
            date_cols = len(df.select_dtypes(include=['datetime64']).columns)
            text_cols = len(df.select_dtypes(include=['object']).columns)

            return f"📊 {len(df)} 条 · {len(df.columns)} 字段 | 📈 数值{numeric_cols} | 📅 日期{date_cols} | 📝 文本{text_cols}"


# 使用示例
if __name__ == "__main__":
    # 创建示例数据
    sample_data = pd.DataFrame({
        '客户': ['客户A', '客户B', '客户C'] * 100,
        '收入': np.random.randint(10, 1000, 300),
        '日期': pd.date_range('2024-01-01', periods=300, freq='D')
    })

    # 测试 AgGrid
    DisplayHelper.render_aggrid_table(sample_data, key="test")
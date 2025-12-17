# data/schema.py - 数据架构标准
import pandas as pd
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date


class DataSchema:
    """数据架构标准

    定义销售预测系统的标准数据结构和字段约束
    """

    # 必需列定义
    REQUIRED_COLUMNS = {
        "客户": {
            "data_type": "string",
            "nullable": False,
            "description": "客户名称",
            "max_length": 255
        },
        "业务线": {
            "data_type": "category",
            "nullable": False,
            "categories": ["光谱设备/服务", "配液设备", "自动化项目"],
            "description": "业务线分类"
        },
        "金额": {
            "data_type": "numeric",
            "nullable": False,
            "description": "合同金额（万元）",
            "min_value": 0
        }
    }

    # 业务逻辑列定义
    BUSINESS_COLUMNS = {
        "成单率": {
            "data_type": "numeric",
            "nullable": True,
            "description": "预计成单概率（%）",
            "min_value": 0,
            "max_value": 100,
            "default": 50.0
        },
        "人工纠偏金额": {
            "data_type": "numeric",
            "nullable": True,
            "description": "人工调整后的预期收入",
            "min_value": 0
        },
        "开始时间": {
            "data_type": "datetime64[ns]",
            "nullable": True,
            "description": "项目开始时间"
        },
        "预计截止时间": {
            "data_type": "datetime64[ns]",
            "nullable": True,
            "description": "项目预计完成时间"
        },
        "交付月份": {
            "data_type": "datetime64[ns]",
            "nullable": True,
            "description": "预期交付月份"
        },
        "当前进展": {
            "data_type": "string",
            "nullable": True,
            "description": "项目当前进展状态"
        },
        "主要描述": {
            "data_type": "string",
            "nullable": True,
            "max_length": 1000,
            "description": "项目主要描述"
        },
        "交付内容": {
            "data_type": "string",
            "nullable": True,
            "description": "交付内容说明"
        },
        "数量": {
            "data_type": "numeric",
            "nullable": True,
            "description": "数量",
            "min_value": 0
        }
    }

    # 付款配置列定义
    PAYMENT_COLUMNS = {
        "首付款比例": {
            "data_type": "numeric",
            "nullable": False,
            "min_value": 0,
            "max_value": 100,
            "default": 50.0,
            "description": "首付款占收入比例"
        },
        "次付款比例": {
            "data_type": "numeric",
            "nullable": False,
            "min_value": 0,
            "max_value": 100,
            "default": 40.0,
            "description": "第二次付款占收入比例"
        },
        "尾款比例": {
            "data_type": "numeric",
            "nullable": False,
            "min_value": 0,
            "max_value": 100,
            "default": 0.0,
            "description": "尾款占收入比例"
        },
        "质保金比例": {
            "data_type": "numeric",
            "nullable": False,
            "min_value": 0,
            "max_value": 100,
            "default": 10.0,
            "description": "质保金占收入比例"
        },
        "首付款时间": {
            "data_type": "datetime64[ns]",
            "nullable": True,
            "description": "首付款预计时间"
        },
        "次付款时间": {
            "data_type": "datetime64[ns]",
            "nullable": True,
            "description": "第二次付款预计时间"
        },
        "尾款时间": {
            "data_type": "datetime64[ns]",
            "nullable": True,
            "description": "尾款预计时间"
        },
        "质保金时间": {
            "data_type": "datetime64[ns]",
            "nullable": True,
            "description": "质保金预计时间"
        }
    }

    # 技术列定义（用于内部处理）
    TECHNICAL_COLUMNS = {
        "record_id": {
            "data_type": "string",
            "nullable": True,
            "description": "飞书记录ID"
        },
        "更新时间": {
            "data_type": "datetime64[ns]",
            "nullable": True,
            "description": "记录更新时间"
        }
    }

    # 所有列的合并字典
    @classmethod
    def get_all_columns(cls):
        """获取所有列定义"""
        columns = {}
        columns.update(cls.REQUIRED_COLUMNS)
        columns.update(cls.BUSINESS_COLUMNS)
        columns.update(cls.PAYMENT_COLUMNS)
        columns.update(cls.TECHNICAL_COLUMNS)
        return columns

    @classmethod
    def ensure_required_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        """确保DataFrame包含所有必需列"""
        result_df = df.copy()

        for col_name, col_def in cls.REQUIRED_COLUMNS.items():
            if col_name not in result_df.columns:
                # 获取默认值
                default_value = col_def.get("default", "")

                # 设置默认值
                result_df[col_name] = default_value

                # 特殊处理人工纠偏金额
                if col_name == "人工纠偏金额" and (result_df.empty or
                                              result_df[col_name].isna().all() or
                                              (result_df[col_name] == 0).all()):
                    result_df[col_name] = result_df["金额"]

        return result_df

    @classmethod
    def cast_column_types(cls, df: pd.DataFrame) -> pd.DataFrame:
        """转换列类型为标准格式"""
        result_df = df.copy()
        all_columns = cls.get_all_columns()

        for col_name, col_def in all_columns.items():
            if col_name in result_df.columns:
                try:
                    data_type = col_def["data_type"]

                    # 根据数据类型进行转换
                    if data_type in ["numeric", "float64"]:
                        result_df[col_name] = pd.to_numeric(result_df[col_name], errors='coerce')
                        if "min_value" in col_def:
                            min_val = col_def["min_value"]
                            result_df.loc[result_df[col_name] < min_val, col_name] = min_val
                        if "max_value" in col_def:
                            max_val = col_def["max_value"]
                            result_df.loc[result_df[col_name] > max_val, col_name] = max_val

                    elif data_type == "int64":
                        result_df[col_name] = pd.to_numeric(result_df[col_name], errors='coerce').astype("Int64")

                    elif data_type == "string":
                        if result_df[col_name].dtype.name in ['object', 'category']:
                            result_df[col_name] = result_df[col_name].astype(str)
                            # 处理特定值
                            result_df.loc[result_df[col_name].str.lower().isin(['nan', 'none', '']), col_name] = ""
                        else:
                            result_df[col_name] = result_df[col_name].astype(str)

                    elif data_type == "datetime64[ns]":
                        # 首先尝试标准日期格式
                        result_df[col_name] = pd.to_datetime(result_df[col_name], errors='coerce')

                    elif data_type == "category":
                        if "categories" in col_def:
                            categories = col_def["categories"]
                            # 确保值在有效分类中
                            invalid_mask = ~result_df[col_name].isin(categories) & result_df[col_name].notna()
                            result_df.loc[invalid_mask, col_name] = ""  # 或第一个有效分类

                            result_df[col_name] = result_df[col_name].astype("category")
                            result_df[col_name] = result_df[col_name].cat.set_categories(categories, ordered=False)

                except Exception as e:
                    # 如果转换失败，记录警告
                    print(f"警告: 转换列 {col_name} 失败: {str(e)}")
                    continue

        return result_df

    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame) -> Dict[str, List[str]]:
        """验证DataFrame是否符合架构标准

        Returns:
            包含错误和警告的字典
        """
        errors = []
        warnings = []

        if df.empty:
            errors.append("DataFrame为空")
            return {"errors": errors, "warnings": warnings}

        # 检查必需列
        missing_columns = []
        for col_name in cls.REQUIRED_COLUMNS.keys():
            if col_name not in df.columns:
                missing_columns.append(col_name)

        if missing_columns:
            errors.append(f"缺失必需列: {', '.join(missing_columns)}")

        # 检查列类型
        all_columns = cls.get_all_columns()
        for col_name in df.columns:
            if col_name in all_columns:
                col_def = all_columns[col_name]

                # 数据类型检查
                expected_type = col_def["data_type"]
                actual_type = str(df[col_name].dtype)

                # 检查数值范围
                if col_def.get("data_type") in ("numeric", "float64", "int64"):
                    min_val = col_def.get("min_value", float('-inf'))
                    max_val = col_def.get("max_value", float('inf'))

                    if df[col_name].dtype.kind in 'if':  # 检查是否为数值类型
                        invalid_values = df[(df[col_name] < min_val)
                                          | (df[col_name] > max_val)][col_name]

                        if not invalid_values.empty:
                            warnings.append(f"列 {col_name} 包含超出范围的值: {min_val} ~ {max_val}")

            else:
                # 存在未定义的列
                warnings.append(f"存在未定义的列: {col_name}")

        # 特殊逻辑验证
        if all(col in df.columns for col in ['首付款比例', '次付款比例', '尾款比例', '质保金比例']):
            # 检查付款比例总和
            total_ratio = df['首付款比例'] + df['次付款比例'] + df['尾款比例'] + df['质保金比例']
            invalid_ratios = df[abs(total_ratio - 100) > 0.1].index

            if len(invalid_ratios) > 0:
                errors.append(f"{len(invalid_ratios)} 行记录付款比例总和不等于100%")

        return {"errors": errors, "warnings": warnings}

    @classmethod
    def get_standard_dataframe(
        cls,
        data: Optional[List[Dict[str, Any]]] = None,
        fill_defaults: bool = True
    ) -> pd.DataFrame:
        """获取标准的空DataFrame结构

        Args:
            data: 可选的初始数据
            fill_defaults: 是否填充默认值

        Returns:
            标准的DataFrame
        """
        all_columns = cls.get_all_columns()
        column_names = list(all_columns.keys())

        if data:
            df = pd.DataFrame(data, columns=column_names)
        else:
            # 创建空的DataFrame
            df = pd.DataFrame(columns=column_names)

        # 确保所有列存在
        for col_name, col_def in all_columns.items():
            if col_name not in df.columns:
                if fill_defaults and "default" in col_def:
                    df[col_name] = col_def["default"]
                else:
                    # 创建空列，保持数据类型
                    if col_def["data_type"] == "numeric":
                        df[col_name] = pd.to_numeric([], errors='coerce')
                    elif col_def["data_type"] == "datetime64[ns]":
                        df[col_name] = pd.to_datetime([])
                    elif col_def["data_type"] == "string":
                        df[col_name] = ""
                    elif col_def["data_type"] == "category":
                        categories = col_def.get("categories", [])
                        df[col_name] = pd.Categorical([], categories=categories)

        return df

    @classmethod
    def get_field_descriptions(cls) -> Dict[str, str]:
        """获取所有字段的描述"""
        all_columns = cls.get_all_columns()
        descriptions = {}
        for col_name, col_def in all_columns.items():
            if "description" in col_def:
                descriptions[col_name] = col_def["description"]
        return descriptions

    @classmethod
    def get_sample_data(cls) -> pd.DataFrame:
        """获取示例数据"""
        sample_data = [
            {
                "客户": "示例客户1",
                "业务线": "光谱设备/服务",
                "金额": 100.0,
                "成单率": 80.0,
                "人工纠偏金额": 80.0,
                "预计截止时间": datetime(2024, 6, 30),
                "当前进展": "谈判中",
                "首付款比例": 50.0,
                "次付款比例": 40.0,
                "尾款比例": 0.0,
                "质款金比例": 10.0,
                "主要描述": "合同设备采购"
            },
            {
                "客户": "示例客户2",
                "业务线": "配液设备",
                "金额": 200.0,
                "成单率": 60.0,
                "人工纠偏金额": 120.0,
                "预计截止时间": datetime(2024, 9, 15),
                "当前进展": "需求确认",
                "首付款比例": 30.0,
                "次付款比例": 50.0,
                "尾款比例": 10.0,
                "质保金比例": 10.0,
                "主要描述": "自动化改造"
            }
        ]

        return pd.DataFrame(sample_data)

    @classmethod
    def get_column_data_types(cls) -> Dict[str, str]:
        """获取列数据类型映射"""
        all_columns = cls.get_all_columns()
        return {col_name: col_def["data_type"]
                for col_name, col_def in all_columns.items()}

    @classmethod
    def get_business_categories(cls) -> List[str]:
        """获取业务线分类列表"""
        return cls.REQUIRED_COLUMNS["业务线"]["categories"]

    @classmethod
    def validate_business_category(cls, category: str) -> bool:
        """验证业务线分类是否有效"""
        valid_categories = cls.get_business_categories()
        return category in valid_categories

    @classmethod
    def get_payment_stages(cls) -> List[str]:
        """获取付款阶段列表"""
        payment_cols = [col for col in cls.PAYMENT_COLUMNS.keys()
                       if col.endswith("比例")]
        return [col.replace("比例", "") for col in payment_cols]

    @classmethod
    def get_payment_columns(cls) -> Dict[str, Dict[str, Any]]:
        """获取付款相关列"""
        return cls.PAYMENT_COLUMNS.copy()
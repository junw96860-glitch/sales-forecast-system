# utils/validators.py - 数据验证器
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple, Optional, Union
from datetime import datetime
from data.schema import DataSchema


class DataValidator:
    """数据验证器

    提供全面的数据验证功能，确保数据质量
    """

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.schema = DataSchema()

    def validate_all(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """执行所有验证

        Returns:
            包含errors和warnings的字典
        """
        self.errors = []
        self.warnings = []

        # 1. 基础验证
        self.validate_basic(df)

        # 2. 业务逻辑验证
        self.validate_business_logic(df)

        # 3. 数据一致性验证
        self.validate_consistency(df)

        # 4. 数值范围验证
        self.validate_numeric_ranges(df)

        # 5. 日期逻辑验证
        self.validate_date_logic(df)

        # 6. 付款配置验证
        self.validate_payment_config(df)

        return {
            "has_errors": len(self.errors) > 0,
            "has_warnings": len(self.warnings) > 0,
            "errors": self.errors,
            "warnings": self.warnings
        }

    def validate_basic(self, df: pd.DataFrame):
        """基础验证"""
        if df.empty:
            self.errors.append("数据表为空")
            return

        # 检查必需列
        required_cols = set(self.schema.REQUIRED_COLUMNS.keys())
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            self.errors.append(f"缺失必需列: {', '.join(missing_cols)}")

        # 检查空值
        for col in self.schema.REQUIRED_COLUMNS:
            if col in df.columns and df[col].isna().all():
                self.warnings.append(f"列 '{col}' 所有值均为空")

    def validate_business_logic(self, df: pd.DataFrame):
        """业务逻辑验证"""
        # 1. 检查业务线分类
        if '业务线' in df.columns:
            valid_categories = self.schema.get_business_categories()
            invalid_business_lines = df[~df['业务线'].isin(valid_categories) &
                                      df['业务线'].notna()]["业务线"].unique()
            if len(invalid_business_lines) > 0:
                self.warnings.append(f"发现无效的业务线: {', '.join(invalid_business_lines)}")

        # 2. 金额合理性检查
        if '金额' in df.columns:
            # 负值检查
            negative_amounts = df[df['金额'] < 0]
            if not negative_amounts.empty:
                self.warnings.append(f"发现 {len(negative_amounts)} 条记录的金额为负值")

            # 异常大金额检查
            if len(df) > 1000:  # 有足够样本时
                # 计算金额分布
                amount_q95 = df['金额'].quantile(0.95)
                amount_q99 = df['金额'].quantile(0.99)
                extreme_amounts = df[df['金额'] > amount_q99 * 2]
                if not extreme_amounts.empty:
                    self.warnings.append(
                        f"发现 {len(extreme_amounts)} 条记录的金额超过99分位数的2倍，请确认是否录入错误"
                    )

        # 3. 成单率检查
        if '成单率' in df.columns:
            invalid_rates = df[(df['成单率'] < 0) | (df['成单率'] > 100)]
            if not invalid_rates.empty:
                self.warnings.append(f"发现 {len(invalid_rates)} 条记录的成单率不在0-100范围内")

        # 4. 人工纠偏检查
        if '人工纠偏金额' in df.columns and '金额' in df.columns:
            # 检查调整幅度
            adjustment_ratio = df['人工纠偏金额'] / df['金额']
            extreme_adjustments = df[(adjustment_ratio < 0.1) | (adjustment_ratio > 5)]
            if not extreme_adjustments.empty:
                self.warnings.append(
                    f"发现 {len(extreme_adjustments)} 条记录的人工纠偏金额与原始金额差异过大（超过10倍或低于10%）"
                )

    def validate_consistency(self, df: pd.DataFrame):
        """数据一致性验证"""
        # 1. 重复客户检查
        if '客户' in df.columns:
            duplicate_clients = df[df.duplicated('客户', keep=False)]['客户'].unique()
            if len(duplicate_clients) > 0:
                self.warnings.append(
                    f"发现重复的客户名称，可能导致数据覆盖: {', '.join(duplicate_clients[:5])}"
                )

        # 2. 业务线与金额的匹配关系
        if all(col in df.columns for col in ['业务线', '金额']):
            # 检查不同业务线的金额分布
            business_line_stats = df.groupby('业务线')['金额'].agg(['mean', 'median', 'std'])
            for business_line, stats in business_line_stats.iterrows():
                if stats['mean'] > 0 and stats['std'] / stats['mean'] > 5:
                    self.warnings.append(f"业务线 '{business_line}' 的金额分布差异过大（变异系数 > 500%）")

        # 3. 时间一致性
        date_columns = ['开始时间', '预计截止时间', '首付款时间', '次付款时间', '尾款时间', '质保金时间']
        if all(col in df.columns for col in ['开始时间', '预计截止时间']):
            # 顺序验证
            invalid_orders = df[df['开始时间'] > df['预计截止时间']]
            if not invalid_orders.empty:
                self.errors.append(f"发现 {len(invalid_orders)} 条记录的开始时间晚于截止时间")

    def validate_numeric_ranges(self, df: pd.DataFrame):
        """数值范围验证"""
        payment_cols = [col for col in df.columns if col.endswith('比例')]

        for col in payment_cols:
            if col in df.columns:
                invalid_values = df[(df[col] < 0) | (df[col] > 100)]
                if not invalid_values.empty:
                    self.errors.append(f"列 '{col}' 包含不在0-100范围内的值")

        # 付款比例总和验证
        payment_ratio_cols = ['首付款比例', '次付款比例', '尾款比例', '质保金比例']
        if all(col in df.columns for col in payment_ratio_cols):
            total_ratio = df[payment_ratio_cols].sum(axis=1)
            invalid_ratios = df[abs(total_ratio - 100) > 0.1]
            if not invalid_ratios.empty:
                self.errors.append(f"发现 {len(invalid_ratios)} 条记录的付款比例总和不为100%")

        # 最小金额检查
        if '金额' in df.columns:
            very_small_amounts = df[df['金额'] < 0.1]
            if not very_small_amounts.empty:
                self.warnings.append(f"发现 {len(very_small_amounts)} 条记录的金额小于0.1万，请确认")

    def validate_date_logic(self, df: pd.DataFrame):
        """日期逻辑验证"""
        # 1. 日期格式检查
        date_columns = ['开始时间', '预计截止时间', '首付款时间', '次付款时间', '尾款时间', '质保金时间']

        for col in date_columns:
            if col in df.columns:
                # 检查非日期值
                non_date_values = df[df[col].notna() & (df[col].astype(str).str.match(r'\d{4}-\d{2}-\d{2}') == False)]
                if not non_date_values.empty:
                    self.warnings.append(f"列 '{col}' 包含非法日期格式: {', '.join(non_date_values[col].astype(str).unique()[:3])}")

                # 检查过去日期
                if col == '预计截止时间':
                    past_dates = df[df[col] < datetime.now()].dropna()
                    if not past_dates.empty:
                        self.warnings.append(f"列 '{col}' 包含 {len(past_dates)} 个过去日期")

        # 2. 付款时间顺序验证
        payment_times = ['首付款时间', '次付款时间', '尾款时间', '质保金时间']
        if all(col in df.columns for col in payment_times):
            for i in range(len(payment_times) - 1):
                current_col = payment_times[i]
                next_col = payment_times[i + 1]

                current_valid = df[current_col].notna() & df[next_col].notna()
                invalid_times = df[current_valid & (df[current_col] > df[next_col])]

                if not invalid_times.empty:
                    self.warnings.append(f"发现 {len(invalid_times)} 条记录中 {next_col} 早于 {current_col}")

    def validate_payment_config(self, df: pd.DataFrame):
        """付款配置验证"""
        payment_cols = ['首付款比例', '次付款比例', '尾款比例', '质保金比例']
        payment_time_cols = ['首付款时间', '次付款时间', '尾款时间', '质保金时间']

        # 检查配置完整性
        has_ratio = all(col in df.columns for col in payment_cols)
        has_time = all(col in df.columns for col in payment_time_cols)

        if has_ratio:
            # 零比例检查 - 如果为0，则相应的时间不应设置
            zero_ratios = {}  # 列名 -> 零比例的行索引
            for ratio_col, time_col in zip(['首付款比例', '次付款比例', '尾款比例', '质保金比例'],
                                          ['首付款时间', '次付款时间', '尾款时间', '质保金时间']):
                zero_rows = df[df[ratio_col] == 0]
                if not zero_rows.empty:
                    zero_ratios[ratio_col] = zero_rows.index.tolist()

            # 组合配置检查 - 检查是否同时配置了比例和时间
            if has_time:
                for ratio_col, time_col in zip(payment_cols, payment_time_cols):
                    # 有比例但无时间
                    has_ratio_no_time = df[(df[ratio_col] > 0) & df[time_col].isna()]
                    if not has_ratio_no_time.empty:
                        self.warnings.append(f"列 '{ratio_col}' 设置了比例对应的时间为空")

                    # 有时间但无比例
                    has_time_no_ratio = df[df[ratio_col] == 0 & df[time_col].notna()]
                    if not has_time_no_ratio.empty:
                        self.warnings.append(f"列 '{ratio_col}' 未设置比例但配置了时间")

    def get_summary_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """获取数据摘要统计信息"""
        stats = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "missing_data": {},
            "numeric_stats": {},
            "categorical_stats": {}
        }

        # 缺失数据统计
        for col in df.columns:
            missing_count = df[col].isna().sum()
            missing_ratio = missing_count / len(df) if len(df) > 0 else 0
            if missing_count > 0:
                stats["missing_data"][col] = {
                    "count": missing_count,
                    "ratio": missing_ratio
                }

        # 数值统计
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            stats["numeric_stats"][col] = {
                "mean": df[col].mean(),
                "median": df[col].median(),
                "min": df[col].min(),
                "max": df[col].max(),
                "std": df[col].std()
            }

        # 分类统计
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols:
            stats["categorical_stats"][col] = {
                "unique_count": df[col].nunique(),
                "most_frequent": df[col].mode().iloc[0] if not df[col].mode().empty else None,
                "frequent_values": df[col].value_counts().head(5).to_dict()
            }

        return stats

    def generate_validation_report(self, df: pd.DataFrame) -> str:
        """生成验证报告"""
        result = self.validate_all(df)
        stats = self.get_summary_stats(df)

        report = f"""
# 数据验证报告

## 基础统计信息
- 总记录数: {stats['total_rows']}
- 总列数: {stats['total_columns']}

## 验证结果
- 严重错误: {len(result['errors'])}
- 警告信息: {len(result['warnings'])}

## 详细错误
"""

        if result['errors']:
            report += "\n### 严重错误:\n"
            for i, error in enumerate(result['errors'], 1):
                report += f"{i}. {error}\n"

        if result['warnings']:
            report += "\n### 警告信息:\n"
            for i, warning in enumerate(result['warnings'], 1):
                report += f"{i}. {warning}\n"

        # 添加缺失数据统计
        if stats['missing_data']:
            report += "\n### 数据缺失统计:\n"
            for col, info in stats['missing_data'].items():
                if info['ratio'] > 0.1:  # 缺失率大于10%
                    report += f"- {col}: 缺失 {info['count']} 条 ({info['ratio']*100:.1f}%)\n"

        return report.strip()

    @staticmethod
    def validate_single_value(column_name: str, value: Any,
                            expected_type: str) -> Tuple[bool, str]:
        """验证单个值"""
        if pd.isna(value):
            return True, ""  # 空值是允许的

        if expected_type == "numeric":
            try:
                float(value)
                return True, ""
            except:
                return False, f"{column_name} 必须为数值"

        elif expected_type == "datetime64[ns]":
            try:
                pd.to_datetime(value)
                return True, ""
            except:
                return False, f"{column_name} 必须为有效日期"

        elif expected_type == "string":
            return True, f" 必须为字符串"

        return True, ""


class ValidationRule:
    """单个验证规则"""

    def __init__(self, name: str, description: str, severity: str = "error"):
        self.name = name
        self.description = description
        self.severity = severity  # error or warning

    def check(self, df: pd.DataFrame, **kwargs) -> Optional[str]:
        """执行检查，返回错误信息或None"""
        raise NotImplementedError("子类必须实现check方法")


class DuplicateClientRule(ValidationRule):
    """重复客户检查规则"""

    def __init__(self, client_column: str = "客户"):
        super().__init__("duplicate_client", "检查重复客户名称", "warning")
        self.client_column = client_column

    def check(self, df: pd.DataFrame, **kwargs) -> Optional[str]:
        if self.client_column not in df.columns:
            return f"缺少必需列 '{self.client_column}'"

        duplicate_clients = df[df.duplicated(self.client_column, keep=False)][self.client_column].unique()
        if len(duplicate_clients) > 0:
            return f"发现重复的客户名称可能导致数据覆盖: {', '.join(duplicate_clients[:5])}"

        return None


class PaymentRatioRule(ValidationRule):
    """付款比例检查规则"""

    def __init__(self):
        super().__init__("payment_ratio", "检查付款比例总和", "error")

    def check(self, df: pd.DataFrame, **kwargs) -> Optional[str]:
        payment_cols = ['首付款比例', '次付款比例', '尾款比例', '质保金比例']
        if not all(col in df.columns for col in payment_cols):
            return None  # 缺少相关列，跳过检查

        # 计算每行的付款比例总和
        total_ratio = df[payment_cols].sum(axis=1)

        # 找出总和不为100%的行
        invalid_rows = df[abs(total_ratio - 100) > 0.1]

        if not invalid_rows.empty:
            return f"发现 {len(invalid_rows)} 条记录付款比例总和不等于100%"

        return None


class DateLogicRule(ValidationRule):
    """日期逻辑检查规则"""

    def __init__(self, compare_cols: List[Tuple[str, str]] = None):
        super().__init__("date_logic", "检查日期逻辑关系", "error")
        self.compare_cols = compare_cols or [("开始时间", "预计截止时间")]

    def check(self, df: pd.DataFrame, **kwargs) -> Optional[str]:
        for start_col, end_col in self.compare_cols:
            if all(col in df.columns for col in [start_col, end_col]):
                invalid_dates = df[df[start_col].notna() &
                                 df[end_col].notna() &
                                 (df[start_col] > df[end_col])]
                if not invalid_dates.empty:
                    return f"发现 {len(invalid_dates)} 条记录的 {start_col} 晚于 {end_col}"

        return None


class CustomValidator:
    """自定义验证器"""

    def __init__(self):
        self.rules = []

    def add_rule(self, rule: ValidationRule):
        """添加验证规则"""
        self.rules.append(rule)

    def validate(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """执行所有自定义验证规则"""
        errors = []
        warnings = []

        for rule in self.rules:
            result = rule.check(df)
            if result:
                if rule.severity == "error":
                    errors.append(result)
                else:
                    warnings.append(result)

        return {
            "has_errors": len(errors) > 0,
            "has_warnings": len(warnings) > 0,
            "errors": errors,
            "warnings": warnings
        }

# 创建默认验证器
def get_default_validator() -> CustomValidator:
    """获取默认的验证器配置"""
    validator = CustomValidator()

    # 添加常用规则
    validator.add_rule(DuplicateClientRule())
    validator.add_rule(PaymentRatioRule())
    validator.add_rule(DateLogicRule())

    return validator

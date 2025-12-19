# utils/date_utils.py - 日期工具类
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Union, Optional, List
import calendar
from typing import Dict, List, Optional, Any, Tuple

class DateUtils:
    """日期工具类，提供统一的日期处理功能"""

    _month_names = [
        "1月", "2月", "3月", "4月", "5月", "6月",
        "7月", "8月", "9月", "10月", "11月", "12月"
    ]

    @staticmethod
    def to_datetime(date_str: Union[str, datetime, date, pd.Timestamp],
                   format: Optional[str] = None) -> Optional[datetime]:
        """将各种格式的输入转换为datetime对象

        Args:
            date_str: 日期字符串或其他日期格式
            format: 日期格式，如果提供则按此格式解析

        Returns:
            datetime对象或None
        """
        if date_str is None or pd.isna(date_str):
            return None

        if isinstance(date_str, datetime):
            return date_str

        if isinstance(date_str, date):
            return datetime.combine(date_str, datetime.min.time())

        if isinstance(date_str, pd.Timestamp):
            return date_str.to_pydatetime()

        if isinstance(date_str, str):
            try:
                if format:
                    return datetime.strptime(date_str, format)
                else:
                    # 尝试多种常见格式
                    formats = [
                        '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%d-%m-%Y',
                        '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S',
                        '%Y%m%d', '%Y%m'
                    ]
                    for fmt in formats:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                    # 如果都失败，尝试pandas解析
                    pd_date = pd.to_datetime(date_str, errors='coerce')
                    return pd_date.to_pydatetime() if pd.notna(pd_date) else None
            except:
                return None

        return None

    @staticmethod
    def format_month_display(month_str: str) -> str:
        """将月份格式化为显示格式

        Args:
            month_str: 月份字符串，格式为'2024-01'或'2024/01'等

        Returns:
            格式化后的显示字符串，如'2024年1月'
        """
        if not month_str or not isinstance(month_str, str):
            return ""

        try:
            # 提取年和月
            if '-' in month_str:
                year, month = month_str.split('-', 1)
            elif '/' in month_str:
                year, month = month_str.split('/', 1)
            else:
                # 假设是纯数字格式
                if len(month_str) == 6:  # YYYYMM
                    year = month_str[:4]
                    month = month_str[4:]
                else:
                    return month_str

            # 去除前导零并转换为数字
            month_num = int(month.lstrip('0'))

            return f"{year}年{month_num}月"
        except:
            return month_str

    @staticmethod
    def format_quarter_display(month_str: str) -> str:
        """将月份转换为季度显示格式

        Args:
            month_str: 月份字符串，格式为'2024-01'

        Returns:
            季度格式，如'2024年Q1'
        """
        if not month_str or not isinstance(month_str, str):
            return ""

        try:
            year, month = month_str.split('-', 1)
            month_num = int(month.lstrip('0'))
            quarter = (month_num - 1) // 3 + 1
            return f"{year}年Q{quarter}"
        except:
            return month_str

    @staticmethod
    def format_date_range(start_date: Union[str, datetime],
                         end_date: Union[str, datetime],
                         format: str = "%Y-%m-%d") -> str:
        """格式化日期范围

        Args:
            start_date: 开始日期
            end_date: 结束日期
            format: 日期格式

        Returns:
            日期范围字符串
        """
        start = DateUtils.to_datetime(start_date)
        end = DateUtils.to_datetime(end_date)

        if start is None or end is None:
            return ""

        if start.year == end.year:
            if start.month == end.month:
                return f"{start.year}年{start.month}月{start.day}日-{end.day}日"
            else:
                return f"{start.year}年{start.month}月{start.day}日-{end.month}月{end.day}日"
        else:
            return f"{start.strftime('%Y年%m月%d日')}-{end.strftime('%Y年%m月%d日')}"

    @staticmethod
    def get_month_range(start_month: str, end_month: str) -> List[str]:
        """获取两个月份之间的所有月份

        Args:
            start_month: 开始月份，格式'2024-01'
            end_month: 结束月份，格式'2024-01'

        Returns:
            月份列表
        """
        try:
            start_year, start_month_num = [int(x) for x in start_month.split('-')]
            end_year, end_month_num = [int(x) for x in end_month.split('-')]

            months = []
            for year in range(start_year, end_year + 1):
                start_m = start_month_num if year == start_year else 1
                end_m = end_month_num if year == end_year else 12

                for month in range(start_m, end_m + 1):
                    months.append(f"{year}-{month:02d}")

            return months
        except:
            return []

    @staticmethod
    def format_month_list(months: List[str], separator: str = ", ",
                         show_year_first: bool = True) -> str:
        """格式化月份列表

        Args:
            months: 月份列表，格式['2024-01', '2024-02']
            separator: 分隔符
            show_year_first: 是否显示每个年份

        Returns:
            格式化字符串
        """
        if not months:
            return ""

        # 按年月排序
        months = sorted(set(months))

        # 提取所有年份
        years = {}
        for month in months:
            year, month_num = month.split('-')
            if year not in years:
                years[year] = []
            years[year].append(int(month_num))

        result_parts = []
        for year, month_nums in years.items():
            if show_year_first and len(years) > 1:
                month_str = f"{year}年: "
            else:
                month_str = ""

            month_names = [DateUtils._month_names[m - 1] for m in month_nums]
            month_str += separator.join(month_names)
            result_parts.append(month_str)

        return separator.join(result_parts)

    @staticmethod
    def get_quarter(month_str: str) -> str:
        """获取月份所属季度

        Args:
            month_str: 月份字符串，如'2024-03'

        Returns:
            季度字符串，如'2024-Q1'
        """
        try:
            year, month = month_str.split('-')
            month_num = int(month.lstrip('0'))
            quarter = (month_num - 1) // 3 + 1
            return f"{year}-Q{quarter}"
        except:
            return month_str

    @staticmethod
    def get_quarter_start_month(quarter: str) -> str:
        """获取季度的起始月份

        Args:
            quarter: 季度字符串，如'2024-Q3'

        Returns:
            起始月份，如'2024-07'
        """
        try:
            year, q = quarter.split('-Q')
            quarter_num = int(q)
            start_month = (quarter_num - 1) * 3 + 1
            return f"{year}-{start_month:02d}"
        except:
            return quarter

    @staticmethod
    def format_datetime_with_timezone(dt: datetime,
                                   timezone: str = None) -> str:
        """格式化带时区的日期时间

        Args:
            dt: datetime对象
            timezone: 时区（如'Asia/Shanghai'）

        Returns:
            格式化字符串
        """
        try:
            if timezone:
                # 简化的时区处理
                if "Beijing" in timezone or "China" in timezone or "Shanghai" in timezone:
                    return dt.strftime('%Y-%m-%d %H:%M:%S 北京时间')
                else:
                    return dt.strftime(f'%Y-%m-%d %H:%M:%S {timezone}')
            else:
                return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(dt)

    @staticmethod
    def is_valid_month_format(month_str: str) -> bool:
        """验证月份格式是否正确

        Args:
            month_str: 月份字符串

        Returns:
            是否有效
        """
        if not month_str or len(month_str) < 7:
            return False

        try:
            # 检查格式是否为YYYY-MM
            year, month = month_str.split('-', 1)
            year = int(year)
            month = int(month)

            return 1 <= month <= 12 and year >= 2000
        except:
            return False

    @staticmethod
    def add_months(date_str: str, months: int) -> str:
        """在月份字符串上添加月份数

        Args:
            date_str: 月份字符串，如'2024-01'
            months: 要添加的月份数（可以是负数）

        Returns:
            新月份字符串
        """
        try:
            year, month = map(int, date_str.split('-'))
            new_month = month + months
            new_year = year + (new_month - 1) // 12
            new_month = (new_month - 1) % 12 + 1
            return f"{new_year}-{new_month:02d}"
        except:
            return date_str

    @staticmethod
    def diff_months(start_month: str, end_month: str) -> int:
        """计算两个月份之间的月份差

        Args:
            start_month: 开始月份
            end_month: 结束月份

        Returns:
            月份差（整数）
        """
        try:
            start_year, start_month_num = map(int, start_month.split('-'))
            end_year, end_month_num = map(int, end_month.split('-'))

            return (end_year - start_year) * 12 + (end_month_num - start_month_num)
        except:
            return 0

    @staticmethod
    def get_previous_month(month_str: str) -> str:
        """获取上一个月

        Args:
            month_str: 月份字符串

        Returns:
            上一个月份字符串
        """
        return DateUtils.add_months(month_str, -1)

    @staticmethod
    def get_next_month(month_str: str) -> str:
        """获取下一个月

        Args:
            month_str: 月份字符串

        Returns:
            下一个月份字符串
        """
        return DateUtils.add_months(month_str, 1)

    @staticmethod
    def is_last_day_of_month(date_str: Union[str, datetime, date]) -> bool:
        """判断是否为月份最后一天

        Args:
            date_str: 日期

        Returns:
            是否为最后一天
        """
        dt = DateUtils.to_datetime(date_str)
        if dt is None:
            return False

        last_day = calendar.monthrange(dt.year, dt.month)[1]
        return dt.day == last_day

    @staticmethod
    def get_days_in_month(month_str: str) -> int:
        """获取指定月份的天数

        Args:
            month_str: 月份字符串

        Returns:
            天数
        """
        try:
            year, month = map(int, month_str.split('-'))
            return calendar.monthrange(year, month)[1]
        except:
            return 30

    @staticmethod
    def is_future_month(month_str: str, current_date: datetime = None) -> bool:
        """判断是否为未来月份

        Args:
            month_str: 月份字符串
            current_date: 当前日期，默认为今天

        Returns:
            是否为未来月份
        """
        if current_date is None:
            current_date = datetime.now()

        current_month = current_date.strftime('%Y-%m')
        return month_str > current_month

    @staticmethod
    def group_months_by_year(months: List[str]) -> Dict[str, List[str]]:
        """按年份分组月份

        Args:
            months: 月份列表

        Returns:
            按年份分组的字典
        """
        result = {}
        for month in months:
            try:
                year = month.split('-')[0]
                if year not in result:
                    result[year] = []
                result[year].append(month)
            except:
                continue
        return result

    @staticmethod
    def to_chinese_date(date: Union[str, datetime]) -> str:
        """转换为中文日期格式

        Args:
            date: 日期

        Returns:
            中文日期格式，如"2024年3月15日"
        """
        dt = DateUtils.to_datetime(date)
        if dt is None:
            return ""
        return f"{dt.year}年{dt.month}月{dt.day}日"

    @staticmethod
    def to_short_date(date: Union[str, datetime]) -> str:
        """转换为短日期格式（M月d日）

        Args:
            date: 日期

        Returns:
            短日期格式，如"3月15日"
        """
        dt = DateUtils.to_datetime(date)
        if dt is None:
            return ""
        return f"{dt.month}月{dt.day}日"

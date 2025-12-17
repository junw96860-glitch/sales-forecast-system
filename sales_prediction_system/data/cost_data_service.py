# data/cost_data_service.py
"""
成本数据服务模块

负责人工成本、费用支出等成本数据的持久化存储。
支持：
1. 本地 JSON 文件存储（适合 Streamlit Cloud）
2. 未来可扩展到飞书多维表格

设计原则：
- 数据存储在 data/cost_data/ 目录下
- 每种成本类型一个 JSON 文件
- 提供统一的 CRUD 接口
"""

import os
import json
import pandas as pd
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pathlib import Path


class CostDataService:
    """成本数据服务"""
    
    # 人工成本分类
    LABOR_COST_TYPES = [
        "固定薪金",
        "年终奖",
        "社保&公积金",
        "人力福利费",
        "劳动关系补偿金",
        "其他"
    ]
    
    # 付款频率选项
    PAYMENT_FREQUENCIES = ["月度", "一次性", "季度", "年度"]
    
    # 偶尔支出分类
    OCCASIONAL_EXPENSE_TYPES = [
        "设备维修",
        "突发采购",
        "罚款/赔偿",
        "意外损失",
        "临时用工",
        "其他支出"
    ]
    
    # 偶尔所得分类
    OCCASIONAL_INCOME_TYPES = [
        "政府补贴",
        "退税",
        "资产处置收入",
        "赔偿收入",
        "利息收入",
        "其他收入"
    ]
    
    def __init__(self, data_dir: str = "data/cost_data"):
        """
        初始化成本数据服务
        
        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据文件路径
        self.labor_costs_file = self.data_dir / "labor_costs.json"
        self.admin_costs_file = self.data_dir / "admin_costs.json"
        self.cost_categories_file = self.data_dir / "cost_categories.json"
        self.occasional_file = self.data_dir / "occasional_items.json"  # 新增：偶尔收支
        
        # 如果分类文件不存在，自动创建默认分类文件
        if not self.cost_categories_file.exists():
            self.save_cost_categories(self._get_default_categories())
    
    # ========================================
    # 人工成本
    # ========================================
    def get_labor_costs(self) -> pd.DataFrame:
        """获取人工成本数据"""
        return self._load_dataframe(self.labor_costs_file, columns=[
            'id', '成本类型', '费用项目', '金额', '付款频率',
            '开始日期', '结束日期', '备注', '创建时间'
        ])
    
    def save_labor_costs(self, df: pd.DataFrame) -> bool:
        """保存人工成本数据"""
        return self._save_dataframe(df, self.labor_costs_file)
    
    def add_labor_cost(self, cost_type: str, expense_item: str, amount: float,
                       frequency: str, start_date: date, end_date: date, 
                       remark: str = "") -> bool:
        """
        添加人工成本记录
        
        Args:
            cost_type: 成本类型（固定薪金/年终奖/社保&公积金等）
            expense_item: 费用项目名称
            amount: 金额（月度成本或一次性金额）
            frequency: 付款频率（月度/一次性/季度/年度）
            start_date: 开始日期
            end_date: 结束日期
            remark: 备注
        """
        df = self.get_labor_costs()
        
        new_id = self._generate_id(df, prefix="LABOR")
        new_row = pd.DataFrame([{
            'id': new_id,
            '成本类型': cost_type,
            '费用项目': expense_item,
            '金额': amount,
            '付款频率': frequency,
            '开始日期': start_date.isoformat() if isinstance(start_date, date) else str(start_date),
            '结束日期': end_date.isoformat() if isinstance(end_date, date) else str(end_date),
            '备注': remark,
            '创建时间': datetime.now().isoformat()
        }])
        
        df = pd.concat([df, new_row], ignore_index=True)
        return self.save_labor_costs(df)
    
    def delete_labor_cost(self, cost_id: str) -> bool:
        """删除人工成本记录"""
        df = self.get_labor_costs()
        df = df[df['id'] != cost_id]
        return self.save_labor_costs(df)
    
    def update_labor_cost(self, cost_id: str, **kwargs) -> bool:
        """更新人工成本记录"""
        df = self.get_labor_costs()
        mask = df['id'] == cost_id
        if not mask.any():
            return False
        
        for key, value in kwargs.items():
            if key in df.columns:
                if isinstance(value, date):
                    value = value.isoformat()
                df.loc[mask, key] = value
        
        return self.save_labor_costs(df)
    
    def get_labor_cost_types(self) -> List[str]:
        """获取人工成本分类列表"""
        return self.LABOR_COST_TYPES.copy()
    
    # ========================================
    # 费用支出
    # ========================================
    def get_admin_costs(self) -> pd.DataFrame:
        """获取费用支出数据"""
        return self._load_dataframe(self.admin_costs_file, columns=[
            'id', '一级分类', '费用类型', '费用项目', '月度成本', 
            '开始日期', '结束日期', '付款频率', '备注', '创建时间'
        ])
    
    def save_admin_costs(self, df: pd.DataFrame) -> bool:
        """保存费用支出数据"""
        return self._save_dataframe(df, self.admin_costs_file)
    
    def add_admin_cost(self, primary_category: str, expense_type: str, expense_item: str,
                       monthly_cost: float, start_date: date, end_date: date,
                       frequency: str = "月度", remark: str = "") -> bool:
        """添加费用支出记录"""
        df = self.get_admin_costs()
        
        new_id = self._generate_id(df, prefix="ADMIN")
        new_row = pd.DataFrame([{
            'id': new_id,
            '一级分类': primary_category,
            '费用类型': expense_type,
            '费用项目': expense_item,
            '月度成本': monthly_cost,
            '开始日期': start_date.isoformat() if isinstance(start_date, date) else str(start_date),
            '结束日期': end_date.isoformat() if isinstance(end_date, date) else str(end_date),
            '付款频率': frequency,
            '备注': remark,
            '创建时间': datetime.now().isoformat()
        }])
        
        df = pd.concat([df, new_row], ignore_index=True)
        return self.save_admin_costs(df)
    
    def delete_admin_cost(self, cost_id: str) -> bool:
        """删除费用支出记录"""
        df = self.get_admin_costs()
        df = df[df['id'] != cost_id]
        return self.save_admin_costs(df)
    
    def update_admin_cost(self, cost_id: str, **kwargs) -> bool:
        """更新费用支出记录"""
        df = self.get_admin_costs()
        mask = df['id'] == cost_id
        if not mask.any():
            return False
        
        for key, value in kwargs.items():
            if key in df.columns:
                if isinstance(value, date):
                    value = value.isoformat()
                df.loc[mask, key] = value
        
        return self.save_admin_costs(df)
    
    # ========================================
    # 费用分类
    # ========================================
    def get_cost_categories(self) -> Dict[str, List[str]]:
        """获取费用分类结构"""
        if not self.cost_categories_file.exists():
            # 返回默认分类
            return self._get_default_categories()
        
        try:
            with open(self.cost_categories_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return self._get_default_categories()
    
    def save_cost_categories(self, categories: Dict[str, List[str]]) -> bool:
        """保存费用分类结构"""
        try:
            with open(self.cost_categories_file, 'w', encoding='utf-8') as f:
                json.dump(categories, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存费用分类失败: {e}")
            return False
    
    def add_category(self, primary: str, secondary: Optional[str] = None) -> bool:
        """添加费用分类"""
        categories = self.get_cost_categories()
        
        if primary not in categories:
            categories[primary] = []
        
        if secondary and secondary not in categories[primary]:
            categories[primary].append(secondary)
        
        return self.save_cost_categories(categories)
    
    def delete_category(self, primary: str, secondary: Optional[str] = None) -> bool:
        """删除费用分类"""
        categories = self.get_cost_categories()
        
        if primary not in categories:
            return False
        
        if secondary:
            if secondary in categories[primary]:
                categories[primary].remove(secondary)
        else:
            del categories[primary]
        
        return self.save_cost_categories(categories)
    
    def reset_categories_to_default(self) -> bool:
        """重置费用分类为默认值"""
        return self.save_cost_categories(self._get_default_categories())
    
    # ========================================
    # 偶尔收支（一次性收入/支出）
    # ========================================
    def get_occasional_items(self) -> pd.DataFrame:
        """获取偶尔收支数据"""
        return self._load_dataframe(self.occasional_file, columns=[
            'id', '类型', '分类', '项目名称', '金额', '发生日期', '备注', '创建时间'
        ])
    
    def save_occasional_items(self, df: pd.DataFrame) -> bool:
        """保存偶尔收支数据"""
        return self._save_dataframe(df, self.occasional_file)
    
    def add_occasional_item(self, item_type: str, category: str, item_name: str,
                            amount: float, occur_date: date, remark: str = "") -> bool:
        """
        添加偶尔收支记录
        
        Args:
            item_type: 类型（支出/所得）
            category: 分类
            item_name: 项目名称
            amount: 金额（正数）
            occur_date: 发生日期
            remark: 备注
        """
        df = self.get_occasional_items()
        
        new_id = self._generate_id(df, prefix="OCC")
        new_row = pd.DataFrame([{
            'id': new_id,
            '类型': item_type,
            '分类': category,
            '项目名称': item_name,
            '金额': amount,
            '发生日期': occur_date.isoformat() if isinstance(occur_date, date) else str(occur_date),
            '备注': remark,
            '创建时间': datetime.now().isoformat()
        }])
        
        df = pd.concat([df, new_row], ignore_index=True)
        return self.save_occasional_items(df)
    
    def delete_occasional_item(self, item_id: str) -> bool:
        """删除偶尔收支记录"""
        df = self.get_occasional_items()
        df = df[df['id'] != item_id]
        return self.save_occasional_items(df)
    
    def get_occasional_expense_types(self) -> List[str]:
        """获取偶尔支出分类列表"""
        return self.OCCASIONAL_EXPENSE_TYPES.copy()
    
    def get_occasional_income_types(self) -> List[str]:
        """获取偶尔所得分类列表"""
        return self.OCCASIONAL_INCOME_TYPES.copy()
    
    def get_occasional_summary(self, start_date: date = None, end_date: date = None) -> Dict[str, float]:
        """
        获取偶尔收支汇总
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            包含支出总额、所得总额、净额的字典
        """
        df = self.get_occasional_items()
        
        if df.empty:
            return {'支出': 0, '所得': 0, '净额': 0, '支出记录数': 0, '所得记录数': 0}
        
        # 转换日期
        df['发生日期'] = pd.to_datetime(df['发生日期'], errors='coerce')
        
        # 筛选日期范围
        if start_date:
            df = df[df['发生日期'].dt.date >= start_date]
        if end_date:
            df = df[df['发生日期'].dt.date <= end_date]
        
        # 确保金额为数值
        df['金额'] = df['金额'].apply(lambda x: float(x) if pd.notna(x) and x is not None else 0.0)
        
        # 分类汇总
        expense_df = df[df['类型'] == '支出']
        income_df = df[df['类型'] == '所得']
        
        total_expense = expense_df['金额'].sum() if not expense_df.empty else 0
        total_income = income_df['金额'].sum() if not income_df.empty else 0
        
        return {
            '支出': total_expense,
            '所得': total_income,
            '净额': total_income - total_expense,
            '支出记录数': len(expense_df),
            '所得记录数': len(income_df)
        }
    
    # ========================================
    # 汇总统计
    # ========================================
    def get_cost_summary(self) -> Dict[str, float]:
        """获取成本汇总"""
        labor_df = self.get_labor_costs()
        admin_df = self.get_admin_costs()
        occasional_df = self.get_occasional_items()
        
        # 人工成本：月度的按月度计，一次性的直接计入
        labor_monthly = 0
        labor_total = 0
        if not labor_df.empty:
            for _, row in labor_df.iterrows():
                amt = row.get('金额', 0)
                amt = float(amt) if pd.notna(amt) and amt is not None else 0.0
                labor_total += amt
                if row.get('付款频率') == '月度':
                    labor_monthly += amt
        
        # 费用支出
        admin_total = 0
        if not admin_df.empty:
            admin_df['月度成本'] = admin_df['月度成本'].apply(lambda x: float(x) if pd.notna(x) and x is not None else 0.0)
            admin_total = admin_df['月度成本'].sum()
        
        # 偶尔收支
        occasional_expense = 0
        occasional_income = 0
        if not occasional_df.empty:
            occasional_df['金额'] = occasional_df['金额'].apply(lambda x: float(x) if pd.notna(x) and x is not None else 0.0)
            expense_df = occasional_df[occasional_df['类型'] == '支出']
            income_df = occasional_df[occasional_df['类型'] == '所得']
            occasional_expense = expense_df['金额'].sum() if not expense_df.empty else 0
            occasional_income = income_df['金额'].sum() if not income_df.empty else 0
        
        return {
            '人工成本': labor_total,
            '人工成本_月度': labor_monthly,
            '费用支出': admin_total,
            '人工成本记录数': len(labor_df),
            '费用支出记录数': len(admin_df),
            '偶尔支出': occasional_expense,
            '偶尔所得': occasional_income,
            '偶尔收支记录数': len(occasional_df)
        }
    
    def get_monthly_costs(self, year: int = None, month: int = None) -> pd.DataFrame:
        """
        获取月度成本明细
        
        Args:
            year: 年份（可选，不指定则返回所有）
            month: 月份（可选）
        """
        labor_df = self.get_labor_costs()
        admin_df = self.get_admin_costs()
        
        all_costs = []
        
        # 处理人工成本
        for _, row in labor_df.iterrows():
            all_costs.append({
                '类别': '人工成本',
                '类型': row.get('成本类型', ''),
                '项目': row.get('费用项目', ''),
                '金额': row.get('金额', 0),
                '付款频率': row.get('付款频率', '月度'),
                '开始日期': row.get('开始日期', ''),
                '结束日期': row.get('结束日期', '')
            })
        
        # 处理费用支出
        for _, row in admin_df.iterrows():
            all_costs.append({
                '类别': '费用支出',
                '类型': row.get('费用类型', ''),
                '项目': row.get('费用项目', ''),
                '金额': row.get('月度成本', 0),
                '付款频率': row.get('付款频率', '月度'),
                '开始日期': row.get('开始日期', ''),
                '结束日期': row.get('结束日期', '')
            })
        
        return pd.DataFrame(all_costs)
    
    # ========================================
    # 数据导入导出
    # ========================================
    def export_all_costs(self) -> Dict[str, Any]:
        """导出所有成本数据"""
        return {
            'labor_costs': self.get_labor_costs().to_dict('records'),
            'admin_costs': self.get_admin_costs().to_dict('records'),
            'occasional_items': self.get_occasional_items().to_dict('records'),
            'cost_categories': self.get_cost_categories(),
            'export_time': datetime.now().isoformat()
        }
    
    def import_all_costs(self, data: Dict[str, Any]) -> bool:
        """导入所有成本数据"""
        try:
            if 'labor_costs' in data:
                labor_df = pd.DataFrame(data['labor_costs'])
                self.save_labor_costs(labor_df)
            
            if 'admin_costs' in data:
                admin_df = pd.DataFrame(data['admin_costs'])
                self.save_admin_costs(admin_df)
            
            if 'occasional_items' in data:
                occasional_df = pd.DataFrame(data['occasional_items'])
                self.save_occasional_items(occasional_df)
            
            if 'cost_categories' in data:
                self.save_cost_categories(data['cost_categories'])
            
            return True
        except Exception as e:
            print(f"导入成本数据失败: {e}")
            return False
    
    def clear_all_costs(self) -> bool:
        """清空所有成本数据"""
        try:
            self.save_labor_costs(pd.DataFrame())
            self.save_admin_costs(pd.DataFrame())
            self.save_occasional_items(pd.DataFrame())
            return True
        except Exception:
            return False
    
    # ========================================
    # 私有方法
    # ========================================
    def _load_dataframe(self, filepath: Path, columns: List[str]) -> pd.DataFrame:
        """从 JSON 文件加载 DataFrame"""
        if not filepath.exists():
            return pd.DataFrame(columns=columns)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                return pd.DataFrame(columns=columns)
            
            df = pd.DataFrame(data)
            
            # 确保所有列都存在
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            
            return df
        except Exception as e:
            print(f"加载数据失败 {filepath}: {e}")
            return pd.DataFrame(columns=columns)
    
    def _save_dataframe(self, df: pd.DataFrame, filepath: Path) -> bool:
        """将 DataFrame 保存到 JSON 文件"""
        try:
            # 转换日期类型
            df_copy = df.copy()
            for col in df_copy.columns:
                if df_copy[col].dtype == 'datetime64[ns]':
                    df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d')
            
            data = df_copy.to_dict('records')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"保存数据失败 {filepath}: {e}")
            return False
    
    def _generate_id(self, df: pd.DataFrame, prefix: str = "COST") -> str:
        """生成唯一 ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        count = len(df) + 1
        return f"{prefix}_{timestamp}_{count:04d}"
    
    def _get_default_categories(self) -> Dict[str, List[str]]:
        """获取默认费用分类（2025年更新版）"""
        return {
            "场地费": [
                "租金-杭州总部",
                "物业-杭州总部",
                "租金-凤凰座",
                "租金-实验室",
                "物业-实验室",
                "能耗-杭州总部",
                "能耗-凤凰座",
                "能耗-实验室",
                "保洁/劳务费",
                "日用消耗-凤凰座",
                "日用消耗-杭州总部",
                "日用消耗-实验室",
                "绿植租赁",
                "搬迁",
                "其他"
            ],
            "企业福利": [
                "团队建设",
                "员工关怀",
                "节庆福利",
                "会议活动",
                "雇主品牌",
                "其他"
            ],
            "办公资源": [
                "办公文具",
                "软件账号服务",
                "宽带网络",
                "快递/交通",
                "图文打印",
                "仪器租赁/购置",
                "仪器耗材/维修",
                "其他"
            ],
            "业务招待费": [
                "商务礼",
                "商务接待",
                "其他"
            ],
            "第三方服务": [
                "审计服务",
                "咨询/代理服务",
                "资质认定",
                "其他"
            ],
            "知识产权": [
                "专利官费",
                "快速预审&优先审查",
                "复审驳回",
                "软著登记",
                "专利年费",
                "商标注册",
                "版权登记",
                "其他"
            ],
            "研发支出": [
                "外部测试与验证费用",
                "研发测试用（耗材）",
                "研发日常工具",
                "研发设备与仪器采购费用",
                "研发样品用（研发样机）"
            ],
            "营销支出": [
                "推广费",
                "品牌建设费",
                "展会费"
            ],
            "差旅费": [
                "国内差旅",
                "海外差旅",
                "其他"
            ]
        }


# 创建全局实例
cost_data_service = CostDataService()
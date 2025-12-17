# data/marketing_service.py
"""
市场推广数据服务模块 V3 - JSON存储方案
核心字段用飞书原生 + 扩展数据用data字段存JSON
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN, SALES_TABLES
from data.feishu_client import FeishuClient


# ========== 表ID配置 ==========
def get_table_id(key: str, default: str) -> str:
    """从secrets获取表ID"""
    try:
        return st.secrets.get(key, default)
    except:
        return default

# 4个核心表
TABLE_TOPICS = get_table_id("TABLE_MARKETING_TOPICS", "tblJQ2aTImBGYoDl")      # 选题管理表
TABLE_POSTS = get_table_id("TABLE_MARKETING_POSTS", "tblyjCIVlPNNXXss")        # 发布记录表
TABLE_LEADS = get_table_id("TABLE_MARKETING_LEADS", "tbljmAbFuOJZcWNe")        # 线索池表
TABLE_ACCOUNTS = get_table_id("TABLE_MARKETING_ACCOUNTS", "tblykWLUiH6w5RnC")  # 账号运营表


# ========== JSON工具函数 ==========
def parse_json_field(value):
    """安全解析JSON字段，如果不是JSON则返回原始值"""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
            # 如果解析出来不是dict，返回包装的dict
            return {"_raw": parsed}
        except:
            # 不是有效JSON，返回包含原始文本的dict
            return {"_raw_text": value}
    return {}


def to_json_string(data: dict) -> str:
    """转换为JSON字符串"""
    if not data:
        return ""
    try:
        return json.dumps(data, ensure_ascii=False, indent=None)
    except:
        return ""


# ========== 日期工具函数 ==========
def extract_feishu_date(x):
    """提取飞书日期字段的值"""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, dict):
        for k in ("value", "timestamp", "start_time", "end_time"):
            if k in x:
                return x[k]
        return None
    if isinstance(x, list):
        return extract_feishu_date(x[0]) if len(x) > 0 else None
    return x


def parse_timestamp(v):
    """解析时间戳为datetime"""
    if v is None:
        return pd.NaT
    vn = pd.to_numeric(v, errors="coerce")
    if pd.notna(vn):
        if vn >= 1e12:
            return pd.to_datetime(vn, unit="ms", errors="coerce")
        if vn >= 1e9:
            return pd.to_datetime(vn, unit="s", errors="coerce")
        return pd.NaT
    return pd.to_datetime(str(v).strip(), errors="coerce")


def format_date_display(dt) -> str:
    """格式化日期为显示字符串"""
    if pd.isna(dt):
        return ""
    try:
        if isinstance(dt, (datetime, pd.Timestamp)):
            return dt.strftime("%Y-%m-%d")
        return str(dt)[:10]
    except:
        return ""


def date_to_feishu(d) -> Optional[int]:
    """转换日期为飞书时间戳（毫秒）"""
    if d is None:
        return None
    try:
        if isinstance(d, str):
            d = pd.to_datetime(d)
        if isinstance(d, date) and not isinstance(d, datetime):
            d = datetime.combine(d, datetime.min.time())
        if isinstance(d, (datetime, pd.Timestamp)):
            d = d.replace(hour=12, minute=0, second=0, microsecond=0)
            return int(d.timestamp() * 1000)
    except:
        pass
    return None


def safe_numeric(series, default=0):
    """安全转换为数值"""
    return pd.to_numeric(series, errors='coerce').fillna(default)


def safe_sum(df: pd.DataFrame, col: str, default=0) -> float:
    """安全求和"""
    if df.empty or col not in df.columns:
        return default
    return float(safe_numeric(df[col], default).sum())


# ========== 市场推广服务类 ==========
class MarketingService:
    """市场推广数据服务 - JSON存储方案（带缓存）"""
    
    def __init__(self):
        self.client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN)
        # 缓存
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 60  # 缓存60秒
    
    def _get_cache_key(self, table_id: str) -> str:
        return f"mkt_{table_id}"
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache:
            return False
        import time
        if time.time() - self._cache_time.get(key, 0) > self._cache_ttl:
            return False
        return True
    
    def _set_cache(self, key: str, data: pd.DataFrame):
        """设置缓存"""
        import time
        self._cache[key] = data.copy()
        self._cache_time[key] = time.time()
    
    def _get_cache(self, key: str) -> Optional[pd.DataFrame]:
        """获取缓存"""
        if self._is_cache_valid(key):
            return self._cache[key].copy()
        return None
    
    def _clear_cache(self, table_id: str = None):
        """清除缓存"""
        if table_id:
            key = self._get_cache_key(table_id)
            self._cache.pop(key, None)
            self._cache_time.pop(key, None)
        else:
            self._cache.clear()
            self._cache_time.clear()
    
    # ==================== 通用方法 ====================
    def _load_table_with_json(
        self, 
        table_id: str, 
        date_cols: List[str] = None, 
        num_cols: List[str] = None,
        json_col: str = "data",
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        加载飞书表数据，并解析JSON扩展字段
        JSON字段中的key会被展开为DataFrame的列
        同时保留原始data字段值
        """
        # 检查缓存
        cache_key = self._get_cache_key(table_id)
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached
        
        try:
            records = self.client.get_records(table_id)
            if not records:
                return pd.DataFrame()
            
            data = []
            for r in records:
                fields = r.get("fields", {})
                fields["record_id"] = r.get("record_id", "")
                
                # 保留data字段原始值（用于显示脚本等纯文本内容）
                if json_col in fields:
                    original_data = fields[json_col]
                    fields[f"_{json_col}_raw"] = original_data  # 保留原始值
                    
                    # 解析JSON扩展字段
                    json_data = parse_json_field(original_data)
                    for k, v in json_data.items():
                        if k not in fields and not k.startswith("_"):  # 避免覆盖核心字段
                            fields[k] = v
                
                data.append(fields)
            
            df = pd.DataFrame(data)
            
            # 处理日期列
            if date_cols:
                for col in date_cols:
                    if col in df.columns:
                        df[col] = df[col].apply(extract_feishu_date).apply(parse_timestamp)
                        df[f"{col}_显示"] = df[col].apply(format_date_display)
            
            # 处理数值列
            if num_cols:
                for col in num_cols:
                    if col in df.columns:
                        df[col] = safe_numeric(df[col])
            
            # 存入缓存
            if use_cache:
                self._set_cache(cache_key, df)
            
            return df
        except Exception as e:
            st.error(f"加载数据失败: {e}")
            return pd.DataFrame()
    
    def _prepare_fields_with_json(
        self, 
        core_data: Dict,
        extra_data: Dict = None,
        date_fields: List[str] = None,
        json_col: str = "data"
    ) -> Dict:
        """
        准备写入飞书的字段
        core_data: 核心字段（直接写入飞书）
        extra_data: 扩展字段（打包成JSON写入data字段）
        """
        fields = {}
        
        # 处理核心字段
        for key, value in core_data.items():
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            
            # 日期字段
            if date_fields and key in date_fields:
                ts = date_to_feishu(value)
                if ts:
                    fields[key] = ts
                continue
            
            # 数值字段
            if isinstance(value, (int, float)):
                fields[key] = value
                continue
            
            # 字符串
            fields[key] = str(value) if value else ""
        
        # 处理扩展字段 -> JSON
        if extra_data:
            # 清理空值
            clean_extra = {k: v for k, v in extra_data.items() if v is not None and v != ""}
            if clean_extra:
                fields[json_col] = to_json_string(clean_extra)
        
        return fields
    
    def _create_record(
        self, 
        table_id: str, 
        core_data: Dict,
        extra_data: Dict = None,
        date_fields: List[str] = None
    ) -> Tuple[bool, str]:
        """创建记录"""
        try:
            fields = self._prepare_fields_with_json(core_data, extra_data, date_fields)
            result = self.client.create_record(table_id, fields)
            if result:
                # 清除该表缓存
                self._clear_cache(table_id)
                # 处理不同类型的返回值
                if isinstance(result, dict):
                    return True, result.get("record_id", "")
                elif isinstance(result, str):
                    return True, result
                else:
                    return True, str(result)
            return False, "创建失败"
        except Exception as e:
            return False, str(e)
    
    def _update_record(
        self, 
        table_id: str, 
        record_id: str, 
        core_data: Dict,
        extra_data: Dict = None,
        date_fields: List[str] = None
    ) -> bool:
        """更新记录"""
        try:
            fields = self._prepare_fields_with_json(core_data, extra_data, date_fields)
            self.client.update_record(table_id, record_id, fields)
            # 清除该表缓存
            self._clear_cache(table_id)
            return True
        except Exception as e:
            st.error(f"更新失败: {e}")
            return False

    # ==================== 选题管理 ====================
    def get_topics(self, status: str = None) -> pd.DataFrame:
        """获取选题列表"""
        df = self._load_table_with_json(
            TABLE_TOPICS,
            json_col="data"
        )
        if status and not df.empty and "审核状态" in df.columns:
            df = df[df["审核状态"] == status]
        return df
    
    def add_topic(
        self,
        topic_id: str,
        category: str,
        title: str,
        status: str = "待审",
        extra: Dict = None
    ) -> Tuple[bool, str]:
        """添加选题"""
        core = {
            "选题ID": topic_id,
            "栏目类型": category,
            "选题标题": title,
            "审核状态": status,
        }
        return self._create_record(TABLE_TOPICS, core, extra)
    
    def update_topic(self, record_id: str, core_data: Dict, extra_data: Dict = None) -> bool:
        """更新选题"""
        return self._update_record(TABLE_TOPICS, record_id, core_data, extra_data)
    
    def get_topic_options(self) -> List[Dict]:
        """获取选题下拉选项（用于发布记录关联）"""
        df = self.get_topics()
        if df.empty:
            return []
        options = []
        for _, row in df.iterrows():
            options.append({
                "id": row.get("选题ID", ""),
                "title": row.get("选题标题", ""),
                "category": row.get("栏目类型", ""),
                "record_id": row.get("record_id", ""),
                "display": f"{row.get('选题ID', '')} - {row.get('选题标题', '')}"
            })
        return options

    # ==================== 发布记录 ====================
    def get_posts(self, topic_id: str = None, platform: str = None) -> pd.DataFrame:
        """获取发布记录"""
        df = self._load_table_with_json(
            TABLE_POSTS,
            date_cols=["发布日期"],
            num_cols=["投放费用", "views", "likes", "comments", "shares", "new_fans"],
            json_col="data"
        )
        if topic_id and not df.empty and "选题ID" in df.columns:
            df = df[df["选题ID"] == topic_id]
        if platform and not df.empty and "平台" in df.columns:
            df = df[df["平台"] == platform]
        return df
    
    def add_post(
        self,
        topic_id: str,
        platform: str,
        publish_date,
        cost: float = 0,
        extra: Dict = None
    ) -> Tuple[bool, str]:
        """添加发布记录"""
        core = {
            "选题ID": topic_id,
            "平台": platform,
            "发布日期": publish_date,
            "投放费用": cost,
        }
        return self._create_record(TABLE_POSTS, core, extra, date_fields=["发布日期"])
    
    def update_post(self, record_id: str, core_data: Dict, extra_data: Dict = None) -> bool:
        """更新发布记录"""
        return self._update_record(TABLE_POSTS, record_id, core_data, extra_data, date_fields=["发布日期"])
    
    def get_posts_by_topic(self, topic_id: str) -> pd.DataFrame:
        """获取某选题的所有发布记录"""
        return self.get_posts(topic_id=topic_id)

    # ==================== 线索管理 ====================
    def get_leads(self, status: str = None) -> pd.DataFrame:
        """获取线索列表"""
        df = self._load_table_with_json(
            TABLE_LEADS,
            date_cols=["获取日期"],
            num_cols=["预估金额"],
            json_col="data"
        )
        if status and not df.empty and "线索状态" in df.columns:
            df = df[df["线索状态"] == status]
        return df
    
    def add_lead(
        self,
        company: str,
        status: str = "新线索",
        amount: float = 0,
        lead_date = None,
        extra: Dict = None
    ) -> Tuple[bool, str]:
        """添加线索"""
        core = {
            "公司名称": company,
            "线索状态": status,
            "预估金额": amount,
            "获取日期": lead_date or date.today(),
        }
        return self._create_record(TABLE_LEADS, core, extra, date_fields=["获取日期"])
    
    def update_lead(self, record_id: str, core_data: Dict, extra_data: Dict = None) -> bool:
        """更新线索"""
        return self._update_record(TABLE_LEADS, record_id, core_data, extra_data, date_fields=["获取日期"])

    # ==================== 账号运营 ====================
    def get_accounts(self, platform: str = None) -> pd.DataFrame:
        """获取账号运营数据"""
        df = self._load_table_with_json(
            TABLE_ACCOUNTS,
            date_cols=["记录日期"],
            num_cols=["粉丝数", "following", "posts", "new_fans", "lost_fans"],
            json_col="data"
        )
        if platform and not df.empty and "平台" in df.columns:
            df = df[df["平台"] == platform]
        return df
    
    def add_account_record(
        self,
        platform: str,
        record_date,
        followers: int = 0,
        extra: Dict = None
    ) -> Tuple[bool, str]:
        """添加账号记录"""
        core = {
            "平台": platform,
            "记录日期": record_date,
            "粉丝数": followers,
        }
        return self._create_record(TABLE_ACCOUNTS, core, extra, date_fields=["记录日期"])
    
    def get_latest_followers(self) -> Dict[str, Dict]:
        """获取各平台最新粉丝数"""
        df = self.get_accounts()
        if df.empty:
            return {}
        
        result = {}
        if "平台" in df.columns and "粉丝数" in df.columns:
            for platform in df["平台"].unique():
                pdf = df[df["平台"] == platform]
                if "记录日期" in pdf.columns:
                    pdf = pdf.sort_values("记录日期", ascending=False)
                if not pdf.empty:
                    latest = pdf.iloc[0]
                    result[platform] = {
                        "followers": int(latest.get("粉丝数", 0)),
                        "new_fans": int(latest.get("new_fans", 0)),
                        "date": latest.get("记录日期_显示", "")
                    }
        return result

    # ==================== 线索同步到销售台账 ====================
    def sync_lead_to_sales(self, lead_record_id: str) -> Tuple[bool, str]:
        """将线索同步到对应的销售台账"""
        try:
            leads_df = self.get_leads()
            lead = leads_df[leads_df["record_id"] == lead_record_id]
            
            if lead.empty:
                return False, "线索不存在"
            lead = lead.iloc[0]
            
            # 获取需求产品（从JSON的products字段）
            products = lead.get("products", [])
            if isinstance(products, str):
                try:
                    products = json.loads(products)
                except:
                    products = [products] if products else []
            
            if not products:
                return False, "请先选择需求产品"
            
            # 产品到表的映射
            product_table_map = {
                "在线光谱仪": SALES_TABLES.get("光谱设备/服务"),
                "配液设备": SALES_TABLES.get("配液设备"),
                "自动化系统": SALES_TABLES.get("自动化项目"),
            }
            
            synced = []
            errors = []
            
            for product in products:
                product = str(product).strip()
                table_id = product_table_map.get(product)
                
                if not table_id:
                    errors.append(f"产品'{product}'无对应表")
                    continue
                
                # 构建销售台账数据
                contact_info = f"联系人: {lead.get('contact', '')}"
                if lead.get('phone'):
                    contact_info += f" 电话: {lead.get('phone', '')}"
                
                sales_data = {
                    "客户": lead.get("公司名称", ""),
                    "金额": float(lead.get("预估金额", 0)),
                    "成单率": "10%-30%",
                    "当前进展": "初步接触",
                    "交付内容": ["产品"],  # 多选字段用数组
                    "主要描述": f"{contact_info}\n需求: {lead.get('description', '')}",
                    "客户来源": f"市场推广-{lead.get('platform', '')}",
                    "市场线索ID": lead_record_id,
                }
                
                try:
                    result = self.client.create_record(table_id, sales_data)
                    if result:
                        synced.append(product)
                except Exception as e:
                    errors.append(f"{product}: {e}")
            
            if synced:
                # 更新线索状态
                self.update_lead(lead_record_id, {"线索状态": "已同步"})
                return True, f"已同步: {', '.join(synced)}"
            return False, "; ".join(errors) if errors else "同步失败"
            
        except Exception as e:
            return False, str(e)
    
    def batch_sync_leads(self, lead_ids: List[str]) -> Dict:
        """批量同步线索"""
        results = {"success": 0, "failed": 0, "details": []}
        for rid in lead_ids:
            ok, msg = self.sync_lead_to_sales(rid)
            results["success" if ok else "failed"] += 1
            results["details"].append({"record_id": rid, "success": ok, "message": msg})
        return results

    # ==================== 统计分析 ====================
    def get_posts_stats(self) -> Dict:
        """获取发布统计"""
        df = self.get_posts()
        if df.empty:
            return {"count": 0, "cost": 0, "views": 0, "likes": 0, "new_fans": 0}
        return {
            "count": len(df),
            "cost": safe_sum(df, "投放费用"),
            "views": safe_sum(df, "views"),
            "likes": safe_sum(df, "likes"),
            "new_fans": safe_sum(df, "new_fans"),
        }
    
    def get_platform_stats(self) -> pd.DataFrame:
        """按平台统计"""
        df = self.get_posts()
        if df.empty or "平台" not in df.columns:
            return pd.DataFrame()
        
        agg_dict = {}
        for col in ["投放费用", "views", "likes", "comments", "shares", "new_fans"]:
            if col in df.columns:
                agg_dict[col] = "sum"
        
        if not agg_dict:
            return df.groupby("平台").size().reset_index(name="发布数")
        
        stats = df.groupby("平台").agg(agg_dict).reset_index()
        stats["发布数"] = df.groupby("平台").size().values
        return stats
    
    def get_topic_performance(self) -> pd.DataFrame:
        """选题效果排名"""
        posts_df = self.get_posts()
        topics_df = self.get_topics()
        
        if posts_df.empty or topics_df.empty:
            return pd.DataFrame()
        
        # 按选题汇总
        agg_dict = {"投放费用": "sum"}
        for col in ["views", "likes", "new_fans"]:
            if col in posts_df.columns:
                agg_dict[col] = "sum"
        
        topic_stats = posts_df.groupby("选题ID").agg(agg_dict).reset_index()
        topic_stats["平台数"] = posts_df.groupby("选题ID")["平台"].nunique().values
        
        # 关联选题信息
        if "选题ID" in topics_df.columns:
            topic_stats = topic_stats.merge(
                topics_df[["选题ID", "选题标题", "栏目类型"]],
                on="选题ID",
                how="left"
            )
        
        return topic_stats.sort_values("views", ascending=False) if "views" in topic_stats.columns else topic_stats


# 全局实例
marketing_service = MarketingService()
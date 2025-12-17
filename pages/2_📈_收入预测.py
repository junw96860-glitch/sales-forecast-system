# pages/2_📈_Income_Forecast.py
"""
收入预测页面

功能：
1. 核心指标展示（基于 _final_amount）
2. 月度趋势图表
3. 人工纠偏（Overrides）
4. 付款节奏管理（支持模板 + 自定义）
"""
from utils.page_init import init_page
init_page()
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径（解决 Pylance 导入警告）
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import datetime as dt
import json
from typing import Dict, Any, List

import pandas as pd
import streamlit as st
from data.data_manager import data_manager
data_manager.set_state_store(st.session_state)
from dateutil.relativedelta import relativedelta

from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_APP_TOKEN,
    PAYMENT_SCHEDULE_TABLE_ID,
)

from data.data_manager import data_manager
from data.feishu_client import FeishuClient
from data.override_service import OverrideService

# 导入付款模板配置
try:
    from payment_templates import (
        PAYMENT_TEMPLATES,
        get_template,
        get_default_template_for_business,
        get_all_template_names,
        validate_template,
    )
except ImportError:
    # 如果配置文件不存在，使用内置默认值
    PAYMENT_TEMPLATES = {
        "标准三笔(5-4-1)": [
            {"name": "首付款", "ratio": 0.5, "offset_months": -1, "base": "开始时间"},
            {"name": "到货验收款", "ratio": 0.4, "offset_months": 0, "base": "交付时间"},
            {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
        ],
        "四笔分期(3-3-3-1)": [
            {"name": "首付款", "ratio": 0.3, "offset_months": 0, "base": "开始时间"},
            {"name": "到货款", "ratio": 0.3, "offset_months": 0, "base": "交付时间"},
            {"name": "验收款", "ratio": 0.3, "offset_months": 1, "base": "交付时间"},
            {"name": "质保金", "ratio": 0.1, "offset_months": 12, "base": "交付时间"},
        ],
    }
    get_template = lambda name: PAYMENT_TEMPLATES.get(name, list(PAYMENT_TEMPLATES.values())[0])
    get_default_template_for_business = lambda _: "标准三笔(5-4-1)"
    get_all_template_names = lambda: list(PAYMENT_TEMPLATES.keys())
    validate_template = lambda stages: (True, "") if stages else (False, "空")

# 导入 UI 工具（如果存在）
try:
    from utils.chart_formatter import ChartFormatter, inject_plotly_css
    from utils.display_helper import DisplayHelper
    HAS_UI_UTILS = True
except ImportError:
    HAS_UI_UTILS = False
    inject_plotly_css = lambda: None


# ============================================================
# Page Config
# ============================================================
st.set_page_config(page_title="收入预测", layout="wide")
st.title("📈 收入预测")
inject_plotly_css()
if HAS_UI_UTILS:
    try:
        DisplayHelper.apply_global_styles()
    except Exception:
        # 防御：避免某些环境 display_helper 没实现该方法导致页面直接报错
        pass

# ============================================================
# Helpers
# ============================================================
def get_feishu_client() -> FeishuClient:
    return FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN)


def date_to_timestamp(date_val) -> int:
    """将日期转换为 Unix 时间戳（毫秒）"""
    if date_val is None or date_val == "" or pd.isna(date_val):
        return None
    try:
        dt_obj = pd.to_datetime(date_val, errors="coerce")
        if pd.isna(dt_obj):
            return None
        return int(dt_obj.timestamp() * 1000)
    except Exception:
        return None


def timestamp_to_date_str(ts) -> str:
    """将 Unix 时间戳转换为日期字符串"""
    if ts is None or pd.isna(ts):
        return ""
    try:
        return pd.to_datetime(ts, unit="ms").strftime("%Y-%m-%d")
    except Exception:
        return ""


def apply_template_with_dates(
    template_stages: List[Dict],
    start_date,
    delivery_date,
) -> List[Dict]:
    """应用模板并计算具体日期"""
    result = []
    for stage in template_stages:
        base = stage.get("base", "交付时间")
        base_date = start_date if base == "开始时间" else delivery_date
        offset = stage.get("offset_months", 0)
        
        pay_date_ts = None
        if base_date and pd.notna(base_date):
            try:
                base_dt = pd.to_datetime(base_date, errors="coerce")
                if pd.notna(base_dt):
                    pay_date = base_dt + relativedelta(months=offset)
                    pay_date_ts = int(pay_date.timestamp() * 1000)
            except Exception:
                pass
        
        result.append({
            "name": stage.get("name", ""),
            "ratio": stage.get("ratio", 0),
            "date": pay_date_ts,
        })
    return result


# ============================================================
# PaymentSchedule Service（简化版，支持 JSON 存储）
# ============================================================
class PaymentScheduleService:
    def __init__(self, client: FeishuClient, table_id: str):
        self.client = client
        self.table_id = table_id
        self._cache = None

    def load(self, force_refresh=False) -> pd.DataFrame:
        if self._cache is not None and not force_refresh:
            return self._cache
        try:
            records = self.client.get_records(self.table_id)
            if records is None:
                records = []
        except Exception as e:
            st.warning(f"加载付款节奏表失败: {e}")
            return pd.DataFrame()

        if not records:
            self._cache = pd.DataFrame()
            return self._cache

        rows = []
        for item in records:
            if item is None:
                continue
            fields = item.get("fields", {}) or {}
            rows.append({
                "_ps_record_id": item.get("record_id"),
                "record_id": fields.get("record_id", ""),
                "template_name": fields.get("template_name", ""),
                "payment_stages": fields.get("payment_stages", "[]"),
            })
        self._cache = pd.DataFrame(rows) if rows else pd.DataFrame()
        return self._cache

    def get_stages(self, source_record_id: str) -> tuple:
        """返回 (template_name, stages_list)"""
        df = self.load()
        if df.empty or "record_id" not in df.columns:
            return "", []
        hit = df[df["record_id"] == source_record_id]
        if hit.empty:
            return "", []
        row = hit.iloc[0]
        template_name = row.get("template_name", "")
        stages_json = row.get("payment_stages", "[]")
        try:
            stages = json.loads(stages_json) if stages_json else []
        except json.JSONDecodeError:
            stages = []
        return template_name, stages

    def save(self, source_record_id: str, template_name: str, stages: List[Dict]):
        df = self.load(force_refresh=True)
        ps_record_id = None
        if not df.empty and "record_id" in df.columns:
            hit = df[df["record_id"] == source_record_id]
            if not hit.empty:
                ps_record_id = hit.iloc[0].get("_ps_record_id")

        fields = {
            "record_id": source_record_id,
            "template_name": template_name,
            "payment_stages": json.dumps(stages, ensure_ascii=False),
            "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 改为字符串格式
        }

        if ps_record_id:
            self.client.update_record(self.table_id, ps_record_id, fields)
        else:
            self.client.create_record(self.table_id, fields)
        self._cache = None


# ============================================================
# Load Data
# ============================================================
with st.spinner("🔄 正在加载销售数据..."):
    df = data_manager.get_active_data()

if df is None or df.empty:
    st.warning("暂无数据")
    st.stop()

if "record_id" not in df.columns or "_final_amount" not in df.columns:
    st.error("缺少 record_id / _final_amount 字段")
    st.stop()

df = df.copy()


# ============================================================
# KPI
# ============================================================
st.subheader("📌 核心指标")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("预测收入合计（万元）", f"{df['_final_amount'].fillna(0).sum():,.2f}")
with c2:
    st.metric("项目数", len(df))
with c3:
    override_count = df["人工纠偏金额"].notna().sum() if "人工纠偏金额" in df.columns else 0
    st.metric("已纠偏项目数", override_count)


# ============================================================
# Charts
# ============================================================
st.divider()
st.subheader("📈 月度预测趋势")

if "_交付月份" in df.columns:
    monthly = (
        df.dropna(subset=["_交付月份"])
        .groupby("_交付月份")["_final_amount"]
        .sum()
        .reset_index()
        .sort_values("_交付月份")
    )
    if HAS_UI_UTILS:
        fig = ChartFormatter.create_monthly_trend_chart(
            monthly, "_交付月份", "_final_amount", "月度预测收入趋势（万元）", "收入"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        import plotly.express as px
        fig = px.bar(monthly, x="_交付月份", y="_final_amount", title="月度预测收入趋势（万元）")
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Section 1: Overrides
# ============================================================
st.divider()
st.subheader("✏️ 人工纠偏（Overrides）")

if "人工纠偏金额" not in df.columns:
    df["人工纠偏金额"] = pd.NA

override_cols = ["客户", "业务线", "金额", "成单率", "_system_pred_amount", "人工纠偏金额", "_final_amount", "record_id"]
override_cols = [c for c in override_cols if c in df.columns]
override_df = df[override_cols].copy()

# 数值格式化
for col in ["金额", "_system_pred_amount", "人工纠偏金额", "_final_amount"]:
    if col in override_df.columns:
        override_df[col] = pd.to_numeric(override_df[col], errors="coerce")

st.dataframe(
    override_df.drop(columns=["record_id"], errors="ignore"),
    use_container_width=True,
    height=400,
)

with st.expander("✏️ 编辑并保存人工纠偏金额", expanded=False):
    edit_df = df[override_cols].copy()
    edited_override = st.data_editor(
        edit_df,
        disabled=[c for c in edit_df.columns if c != "人工纠偏金额"],
        use_container_width=True,
        key="override_editor",
    )

    if st.button("💾 保存人工纠偏", key="save_overrides_btn"):
        changed = (
            pd.to_numeric(edited_override["人工纠偏金额"], errors="coerce").fillna(-1)
            != pd.to_numeric(edit_df["人工纠偏金额"], errors="coerce").fillna(-1)
        )
        rows = edited_override.loc[changed, ["record_id", "人工纠偏金额"]].copy()

        if rows.empty:
            st.info("没有检测到纠偏金额变更。")
        else:
            service = OverrideService(get_feishu_client())
            ok = 0
            for _, r in rows.iterrows():
                rid = str(r["record_id"]).strip()
                amt = pd.to_numeric(r["人工纠偏金额"], errors="coerce")
                if not rid or pd.isna(amt):
                    continue
                try:
                    service.upsert_override(rid, float(amt), dt.datetime.now().isoformat())
                    ok += 1
                except Exception as e:
                    st.error(f"{rid} 写入失败：{e}")
            st.success(f"✅ 已写入 {ok} 条人工纠偏")


# ============================================================
# Section 2: Payment Schedule (模板 + 自定义)
# ============================================================
st.divider()
st.subheader("💰 付款节奏管理")

ps_service = PaymentScheduleService(get_feishu_client(), PAYMENT_SCHEDULE_TABLE_ID)

# 显示模板说明
with st.expander("📋 付款模板说明", expanded=False):
    st.markdown("""
    **预设模板：**
    - **标准三笔(5-4-1)**：首付50% → 到货验收40% → 质保金10%
    - **四笔分期(3-3-3-1)**：首付30% → 到货30% → 验收30% → 质保金10%
    - 更多模板可在 `config/payment_templates.py` 中配置
    
    **使用方法：**
    1. 选择项目
    2. 选择模板或自定义编辑
    3. 点击保存
    """)

# 项目选择
st.markdown("### 选择项目配置付款节奏")

project_options = df[["客户", "业务线", "_final_amount", "record_id"]].copy()
project_options["显示名"] = project_options.apply(
    lambda r: f"{r['客户']} ({r['业务线']}) - ¥{r['_final_amount']:.2f}万", axis=1
)

selected_project = st.selectbox(
    "选择项目",
    options=project_options["record_id"].tolist(),
    format_func=lambda rid: project_options[project_options["record_id"] == rid]["显示名"].values[0],
)

if selected_project:
    project_row = df[df["record_id"] == selected_project].iloc[0]
    project_amount = project_row.get("_final_amount", 0)
    start_date = project_row.get("开始时间")
    delivery_date = project_row.get("交付时间") or project_row.get("预计截止时间")
    business_line = project_row.get("业务线", "")

    # 获取已保存的配置
    saved_template, saved_stages = ps_service.get_stages(selected_project)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### 模板选择")
        
        # 模板选择
        template_names = ["自定义"] + get_all_template_names()
        default_idx = 0
        if saved_template and saved_template in template_names:
            default_idx = template_names.index(saved_template)
        elif not saved_stages:
            # 新项目，根据业务线选择默认模板
            default_template = get_default_template_for_business(business_line)
            if default_template in template_names:
                default_idx = template_names.index(default_template)

        selected_template = st.selectbox("选择模板", template_names, index=default_idx)

        # 应用模板按钮
        if selected_template != "自定义":
            if st.button("🔄 应用模板", help="应用选中的模板，将覆盖当前配置"):
                template_def = get_template(selected_template)
                new_stages = apply_template_with_dates(template_def, start_date, delivery_date)
                st.session_state[f"stages_{selected_project}"] = new_stages
                st.success(f"已应用模板：{selected_template}")
                st.rerun()

    with col2:
        st.markdown("#### 付款节点编辑")

        # 获取当前节点（优先 session_state，其次已保存，最后模板默认）
        session_key = f"stages_{selected_project}"
        if session_key in st.session_state:
            current_stages = st.session_state[session_key]
        elif saved_stages:
            current_stages = saved_stages
        else:
            # 使用默认模板
            default_template = get_default_template_for_business(business_line)
            template_def = get_template(default_template)
            current_stages = apply_template_with_dates(template_def, start_date, delivery_date)

        # 转换为可编辑的 DataFrame
        stages_for_edit = []
        for i, stage in enumerate(current_stages):
            stages_for_edit.append({
                "序号": i + 1,
                "名称": stage.get("name", ""),
                "比例(%)": round(stage.get("ratio", 0) * 100, 1),
                "金额(万)": round(project_amount * stage.get("ratio", 0), 2),
                "付款日期": timestamp_to_date_str(stage.get("date")),
            })

        stages_df = pd.DataFrame(stages_for_edit)

        edited_stages = st.data_editor(
            stages_df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "序号": st.column_config.NumberColumn("序号", disabled=True, width="small"),
                "名称": st.column_config.TextColumn("名称", required=True, width="medium"),
                "比例(%)": st.column_config.NumberColumn("比例(%)", min_value=0, max_value=100, step=1, width="small"),
                "金额(万)": st.column_config.NumberColumn("金额(万)", disabled=True, format="%.2f", width="small"),
                "付款日期": st.column_config.TextColumn("付款日期", help="格式: YYYY-MM-DD", width="medium"),
            },
            key=f"stages_editor_{selected_project}",
        )

        # 显示比例总和
        total_ratio = edited_stages["比例(%)"].sum()
        if abs(total_ratio - 100) < 0.1:
            st.success(f"✅ 比例总和: {total_ratio:.1f}%")
        else:
            st.warning(f"⚠️ 比例总和: {total_ratio:.1f}%（应为 100%）")

        # 保存按钮
        if st.button("💾 保存付款节奏", type="primary"):
            # 转换回存储格式
            new_stages = []
            for _, row in edited_stages.iterrows():
                new_stages.append({
                    "name": row["名称"],
                    "ratio": row["比例(%)"] / 100,
                    "date": date_to_timestamp(row["付款日期"]),
                })

            # 验证
            total = sum(s["ratio"] for s in new_stages)
            if abs(total - 1.0) > 0.01:
                st.error(f"比例总和必须为 100%，当前为 {total * 100:.1f}%")
            else:
                try:
                    template_to_save = selected_template if selected_template != "自定义" else "自定义"
                    ps_service.save(selected_project, template_to_save, new_stages)
                    st.success("✅ 付款节奏已保存！")
                    # 清除 session_state
                    if session_key in st.session_state:
                        del st.session_state[session_key]
                except Exception as e:
                    st.error(f"保存失败: {e}")


# ============================================================
# Section 3: 付款节奏总览
# ============================================================
st.divider()
st.subheader("📊 所有项目付款节奏总览")

# 汇总所有项目的付款节奏
all_payment_rows = []
for _, row in df.iterrows():
    rid = row.get("record_id")
    _, stages = ps_service.get_stages(rid)
    
    if not stages:
        # 使用默认模板
        default_template = get_default_template_for_business(row.get("业务线", ""))
        template_def = get_template(default_template)
        stages = apply_template_with_dates(
            template_def,
            row.get("开始时间"),
            row.get("交付时间") or row.get("预计截止时间"),
        )
    
    amount = row.get("_final_amount", 0)
    for stage in stages:
        all_payment_rows.append({
            "客户": row.get("客户", ""),
            "业务线": row.get("业务线", ""),
            "付款节点": stage.get("name", ""),
            "比例": f"{stage.get('ratio', 0) * 100:.0f}%",
            "金额(万)": round(amount * stage.get("ratio", 0), 2),
            "付款日期": timestamp_to_date_str(stage.get("date")),
            "付款月份": timestamp_to_date_str(stage.get("date"))[:7] if stage.get("date") else "",
        })

all_payments_df = pd.DataFrame(all_payment_rows)

if not all_payments_df.empty:
    # 按月份汇总
    monthly_payments = all_payments_df.groupby("付款月份")["金额(万)"].sum().reset_index()
    monthly_payments = monthly_payments[monthly_payments["付款月份"] != ""].sort_values("付款月份")

    if not monthly_payments.empty:
        import plotly.express as px
        fig = px.bar(
            monthly_payments,
            x="付款月份",
            y="金额(万)",
            title="月度预计回款金额",
        )
        st.plotly_chart(fig, use_container_width=True)

    # 详细表格
    st.dataframe(all_payments_df, use_container_width=True, height=400)
else:
    st.info("暂无付款节奏数据")
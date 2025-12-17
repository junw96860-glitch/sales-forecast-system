# pages/9_📣_市场推广.py
"""
市场推广管理页面 V3
选题 → 多平台发布 → 效果追踪
"""

# === 认证检查 ===
from utils.page_init import init_page
init_page()

import streamlit as st
from data.data_manager import data_manager
data_manager.set_state_store(st.session_state)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

from data.marketing_service import marketing_service, safe_sum

st.set_page_config(page_title="市场推广", layout="wide")
st.title("📣 市场推广管理")

# 刷新按钮（清除缓存）
col_title, col_refresh = st.columns([6, 1])
with col_refresh:
    if st.button("🔄 刷新", help="清除缓存，重新加载数据"):
        marketing_service._clear_cache()
        st.rerun()

# === 常量 ===
PLATFORMS = ["抖音", "小红书", "微信视频号", "B站", "知乎", "LinkedIn"]
CATEGORIES = ["急诊室", "老咸讲堂", "实验室日常"]
RISK_LEVELS = ["A", "B", "C"]
TOPIC_STATUS = ["待审", "通过", "驳回", "已发布"]
LEAD_STATUS = ["新线索", "需求确认", "方案阶段", "商务谈判", "已成交", "已同步", "无效"]
INDUSTRIES = ["制药", "新材料", "化工", "食品", "半导体", "其他"]
PRODUCTS = ["在线光谱仪", "配液设备", "自动化系统"]

# === Tab ===
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📝 选题管理", 
    "📺 发布记录", 
    "🎯 线索管理", 
    "👥 账号运营",
    "📊 效果分析",
    "🔗 台账同步"
])

# ============================================================
# Tab1: 选题管理
# ============================================================
with tab1:
    st.header("📝 选题管理")
    
    # 选题列表
    topics_df = marketing_service.get_topics()
    
    if not topics_df.empty:
        # 筛选（去掉风险等级）
        col1, col2 = st.columns(2)
        f_category = col1.selectbox("栏目类型", ["全部"] + CATEGORIES, key="f_t_cat")
        f_status = col2.selectbox("审核状态", ["全部"] + TOPIC_STATUS, key="f_t_status")
        
        filtered = topics_df.copy()
        if f_category != "全部" and "栏目类型" in filtered.columns:
            filtered = filtered[filtered["栏目类型"] == f_category]
        if f_status != "全部" and "审核状态" in filtered.columns:
            filtered = filtered[filtered["审核状态"] == f_status]
        
        st.metric("选题数量", len(filtered))
        
        st.divider()
        
        # 批量审核区域
        st.subheader("✅ 批量审核")
        
        col1, col2 = st.columns([3, 1])
        
        with col2:
            new_status = st.selectbox("设置新状态", TOPIC_STATUS, key="batch_new_status")
            batch_btn = st.button("🔄 批量更新状态", type="primary", use_container_width=True)
        
        with col1:
            # 准备显示数据（去掉风险等级列）
            show_cols = ["选题ID", "栏目类型", "选题标题", "审核状态"]
            show_cols = [c for c in show_cols if c in filtered.columns]
            
            if show_cols and "record_id" in filtered.columns:
                # 添加序号列用于选择
                display_df = filtered[show_cols + ["record_id"]].copy()
                display_df.insert(0, "选择", False)
                
                # 可编辑表格
                edited_df = st.data_editor(
                    display_df,
                    hide_index=True,
                    use_container_width=True,
                    height=350,
                    column_config={
                        "选择": st.column_config.CheckboxColumn("选择", default=False, width="small"),
                        "审核状态": st.column_config.TextColumn("当前状态", width="small"),
                        "record_id": None,  # 隐藏record_id列
                    },
                    disabled=["选题ID", "栏目类型", "选题标题", "审核状态"],
                    key="topic_editor"
                )
                
                # 处理批量更新
                if batch_btn:
                    selected_rows = edited_df[edited_df["选择"] == True]
                    
                    if selected_rows.empty:
                        st.warning("⚠️ 请先勾选要更新的选题")
                    else:
                        success_count = 0
                        fail_count = 0
                        
                        for _, row in selected_rows.iterrows():
                            record_id = row["record_id"]
                            if marketing_service.update_topic(record_id, {"审核状态": new_status}):
                                success_count += 1
                            else:
                                fail_count += 1
                        
                        if success_count > 0:
                            st.success(f"✅ 成功更新 {success_count} 条")
                        if fail_count > 0:
                            st.error(f"❌ 失败 {fail_count} 条")
                        
                        if success_count > 0:
                            st.rerun()
            else:
                st.dataframe(filtered[show_cols] if show_cols else filtered, use_container_width=True, height=350)
        
        # 查看脚本详情
        st.divider()
        st.subheader("📄 查看脚本详情")
        
        if "record_id" in filtered.columns and "选题ID" in filtered.columns:
            topic_opts = {f"{r['选题ID']} - {r.get('选题标题', '')[:30]}": r['record_id'] 
                        for _, r in filtered.iterrows()}
            
            selected_topic = st.selectbox("选择选题查看详情", list(topic_opts.keys()), key="view_topic_detail")
            
            if selected_topic:
                # 找到选中的行
                sel_record_id = topic_opts[selected_topic]
                sel_row = filtered[filtered["record_id"] == sel_record_id].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**三句话大纲**")
                    outline = sel_row.get("三句话大纲", "")
                    if outline:
                        st.text_area("", value=outline, height=200, disabled=True, key="view_outline", label_visibility="collapsed")
                    else:
                        st.caption("暂无大纲")
                
                with col2:
                    st.markdown("**脚本内容 (data)**")
                    # 优先使用原始data字段
                    data_content = sel_row.get("_data_raw", "") or sel_row.get("data", "")
                    
                    if data_content:
                        st.text_area("", value=str(data_content), height=200, disabled=True, key="view_script", label_visibility="collapsed")
                    else:
                        st.caption("暂无脚本内容")
    else:
        st.info("暂无选题数据")

# ============================================================
# Tab2: 发布记录
# ============================================================
with tab2:
    st.header("📺 发布记录")
    st.caption("一个选题 → 多平台发布 → 分别追踪效果")
    
    # 选择选题
    topic_options = marketing_service.get_topic_options()
    
    if topic_options:
        selected_topic = st.selectbox(
            "选择选题",
            options=[t["display"] for t in topic_options],
            key="sel_topic_post"
        )
        
        # 获取选中的选题ID
        current_topic_id = None
        for t in topic_options:
            if t["display"] == selected_topic:
                current_topic_id = t["id"]
                break
        
        if current_topic_id:
            st.divider()
            
            # 该选题的发布记录
            posts_df = marketing_service.get_posts_by_topic(current_topic_id)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader(f"📋 已发布平台 ({len(posts_df)})")
                
                if not posts_df.empty:
                    show_cols = ["平台", "发布日期_显示", "投放费用", "views", "likes", "new_fans"]
                    show_cols = [c for c in show_cols if c in posts_df.columns]
                    
                    st.dataframe(
                        posts_df[show_cols] if show_cols else posts_df,
                        use_container_width=True,
                        column_config={
                            "发布日期_显示": st.column_config.TextColumn("发布日期"),
                            "投放费用": st.column_config.NumberColumn("投放费用", format="¥%.0f"),
                            "views": st.column_config.NumberColumn("播放量", format="%d"),
                            "likes": st.column_config.NumberColumn("点赞", format="%d"),
                            "new_fans": st.column_config.NumberColumn("新增粉丝", format="%d"),
                        }
                    )
                    
                    # 汇总
                    total_cost = safe_sum(posts_df, "投放费用")
                    total_views = safe_sum(posts_df, "views")
                    total_likes = safe_sum(posts_df, "likes")
                    total_fans = safe_sum(posts_df, "new_fans")
                    
                    st.markdown(f"""
                    **汇总**: 投放 ¥{total_cost:,.0f} | 播放 {total_views:,.0f} | 点赞 {total_likes:,.0f} | 新增粉丝 {total_fans:,.0f}
                    """)
                else:
                    st.info("该选题暂未发布到任何平台")
            
            with col2:
                st.subheader("➕ 添加发布记录")
                
                p_platform = st.selectbox("平台", PLATFORMS, key="p_platform")
                p_date = st.date_input("发布日期", value=date.today(), key="p_date")
                p_cost = st.number_input("投放费用(元)", min_value=0.0, value=0.0, key="p_cost")
                
                if st.button("💾 添加发布", key="add_post", type="primary"):
                    ok, msg = marketing_service.add_post(
                        topic_id=current_topic_id,
                        platform=p_platform,
                        publish_date=p_date,
                        cost=p_cost,
                        extra={"views": 0, "likes": 0, "comments": 0, "shares": 0, "new_fans": 0}
                    )
                    if ok:
                        st.success("✅ 添加成功！")
                        st.rerun()
                    else:
                        st.error(f"❌ 失败: {msg}")
            
            # 更新效果数据
            if not posts_df.empty:
                st.divider()
                st.subheader("🔄 更新效果数据")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if "record_id" in posts_df.columns and "平台" in posts_df.columns:
                        post_opts = {f"{r['平台']} ({r.get('发布日期_显示', '')})": r['record_id'] 
                                    for _, r in posts_df.iterrows()}
                        sel_post = st.selectbox("选择记录", list(post_opts.keys()), key="sel_post_update")
                
                with col2:
                    u_views = st.number_input("播放量", min_value=0, key="u_views")
                    u_likes = st.number_input("点赞数", min_value=0, key="u_likes")
                    u_comments = st.number_input("评论数", min_value=0, key="u_comments")
                    u_shares = st.number_input("转发数", min_value=0, key="u_shares")
                    u_fans = st.number_input("新增粉丝", min_value=0, key="u_fans")
                    u_cost = st.number_input("更新投放费用(元)", min_value=0.0, key="u_cost")
                
                if st.button("💾 更新数据", key="update_post"):
                    core = {}
                    if u_cost > 0:
                        core["投放费用"] = u_cost
                    extra = {
                        "views": u_views,
                        "likes": u_likes,
                        "comments": u_comments,
                        "shares": u_shares,
                        "new_fans": u_fans,
                    }
                    if marketing_service.update_post(post_opts[sel_post], core, extra):
                        st.success("✅ 更新成功！")
                        st.rerun()
    else:
        st.warning("请先在「选题管理」中添加选题")

# ============================================================
# Tab3: 线索管理
# ============================================================
with tab3:
    st.header("🎯 线索管理")
    
    # 获取选题选项（用于关联）
    topic_options = marketing_service.get_topic_options()
    topic_display_list = ["无"] + [t["display"] for t in topic_options]
    
    # 添加线索
    with st.expander("➕ 添加新线索", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            l_company = st.text_input("公司名称", key="l_company")
            l_industry = st.selectbox("行业", INDUSTRIES, key="l_industry")
            l_date = st.date_input("获取日期", value=date.today(), key="l_date")
            l_platform = st.selectbox("来源平台", PLATFORMS, key="l_platform")
        
        with col2:
            l_contact = st.text_input("联系人", key="l_contact")
            l_phone = st.text_input("联系电话", key="l_phone")
            l_wechat = st.text_input("微信", key="l_wechat")
            l_position = st.text_input("职位", key="l_position")
        
        with col3:
            l_products = st.multiselect("需求产品", PRODUCTS, key="l_products")
            l_amount = st.number_input("预估金额(万)", min_value=0.0, key="l_amount")
            l_status = st.selectbox("线索状态", LEAD_STATUS, key="l_status")
            # 关联选题ID
            l_topic = st.selectbox("关联选题", topic_display_list, key="l_topic")
        
        l_desc = st.text_area("需求描述", key="l_desc", height=80)
        
        if st.button("💾 保存线索", key="save_lead"):
            if l_company:
                # 提取选题ID
                topic_id = ""
                if l_topic != "无":
                    for t in topic_options:
                        if t["display"] == l_topic:
                            topic_id = t["id"]
                            break
                
                extra = {
                    "platform": l_platform,
                    "industry": l_industry,
                    "contact": l_contact,
                    "phone": l_phone,
                    "wechat": l_wechat,
                    "position": l_position,
                    "products": l_products,
                    "description": l_desc,
                    "topic_id": topic_id,  # 关联选题ID
                }
                ok, msg = marketing_service.add_lead(l_company, l_status, l_amount, l_date, extra)
                if ok:
                    st.success("✅ 保存成功！")
                    st.rerun()
                else:
                    st.error(f"❌ 失败: {msg}")
            else:
                st.warning("请填写公司名称")
    
    st.divider()
    
    # 线索列表
    leads_df = marketing_service.get_leads()
    
    if not leads_df.empty:
        # 筛选
        col1, col2, col3 = st.columns(3)
        f_lead_status = col1.selectbox("状态筛选", ["全部"] + LEAD_STATUS, key="f_lead_status")
        f_lead_platform = col2.selectbox("平台筛选", ["全部"] + PLATFORMS, key="f_lead_platform")
        # 按选题筛选
        f_lead_topic = col3.selectbox("选题筛选", ["全部"] + [t["id"] for t in topic_options], key="f_lead_topic")
        
        filtered = leads_df.copy()
        if f_lead_status != "全部" and "线索状态" in filtered.columns:
            filtered = filtered[filtered["线索状态"] == f_lead_status]
        if f_lead_platform != "全部" and "platform" in filtered.columns:
            filtered = filtered[filtered["platform"] == f_lead_platform]
        if f_lead_topic != "全部" and "topic_id" in filtered.columns:
            filtered = filtered[filtered["topic_id"] == f_lead_topic]
        
        # 统计
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("线索总数", len(filtered))
        c2.metric("预估总金额", f"¥{safe_sum(filtered, '预估金额'):,.0f}万")
        new_count = len(filtered[filtered["线索状态"] == "新线索"]) if "线索状态" in filtered.columns else 0
        c3.metric("新线索", new_count)
        synced_count = len(filtered[filtered["线索状态"] == "已同步"]) if "线索状态" in filtered.columns else 0
        c4.metric("已同步", synced_count)
        
        # 显示（增加topic_id列）
        show_cols = ["获取日期_显示", "公司名称", "线索状态", "contact", "phone", "products", "预估金额", "platform", "topic_id"]
        show_cols = [c for c in show_cols if c in filtered.columns]
        
        st.dataframe(
            filtered[show_cols] if show_cols else filtered,
            use_container_width=True,
            height=400,
            column_config={
                "获取日期_显示": st.column_config.TextColumn("获取日期"),
                "contact": st.column_config.TextColumn("联系人"),
                "phone": st.column_config.TextColumn("电话"),
                "products": st.column_config.TextColumn("需求产品"),
                "platform": st.column_config.TextColumn("来源平台"),
                "预估金额": st.column_config.NumberColumn("预估金额(万)", format="%.1f"),
                "topic_id": st.column_config.TextColumn("关联选题"),
            }
        )
        
        # 更新状态
        with st.expander("🔄 更新线索状态"):
            if "record_id" in filtered.columns:
                lead_opts = {f"{r.get('公司名称', '')} ({r.get('contact', '')})": r['record_id'] 
                            for _, r in filtered.iterrows()}
                sel_lead = st.selectbox("选择线索", list(lead_opts.keys()), key="sel_lead_update")
                new_lead_status = st.selectbox("新状态", LEAD_STATUS, key="new_lead_status")
                
                if st.button("💾 更新状态", key="update_lead_status"):
                    if marketing_service.update_lead(lead_opts[sel_lead], {"线索状态": new_lead_status}):
                        st.success("✅ 更新成功！")
                        st.rerun()
    else:
        st.info("暂无线索")

# ============================================================
# Tab4: 账号运营
# ============================================================
with tab4:
    st.header("👥 账号运营")
    
    # 各平台粉丝概览
    latest = marketing_service.get_latest_followers()
    
    if latest:
        cols = st.columns(len(latest))
        for i, (platform, data) in enumerate(latest.items()):
            with cols[i]:
                st.metric(
                    platform,
                    f"{data['followers']:,}",
                    delta=f"+{data['new_fans']}" if data['new_fans'] > 0 else None
                )
                st.caption(f"更新: {data['date']}")
    
    st.divider()
    
    # 添加记录
    with st.expander("➕ 添加账号数据", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            a_platform = st.selectbox("平台", PLATFORMS, key="a_platform")
            a_date = st.date_input("记录日期", value=date.today(), key="a_date")
            a_followers = st.number_input("粉丝数", min_value=0, key="a_followers")
        
        with col2:
            a_following = st.number_input("关注数", min_value=0, key="a_following")
            a_posts = st.number_input("作品数", min_value=0, key="a_posts")
            a_new = st.number_input("新增粉丝", min_value=0, key="a_new")
            a_lost = st.number_input("取关数", min_value=0, key="a_lost")
        
        if st.button("💾 保存", key="save_account"):
            extra = {
                "following": a_following,
                "posts": a_posts,
                "new_fans": a_new,
                "lost_fans": a_lost,
            }
            ok, msg = marketing_service.add_account_record(a_platform, a_date, a_followers, extra)
            if ok:
                st.success("✅ 保存成功！")
                st.rerun()
            else:
                st.error(f"❌ 失败: {msg}")
    
    st.divider()
    
    # 粉丝趋势
    account_df = marketing_service.get_accounts()
    
    if not account_df.empty:
        st.subheader("📈 粉丝趋势")
        
        sel_plat = st.selectbox("选择平台", ["全部"] + PLATFORMS, key="trend_plat")
        trend_df = account_df if sel_plat == "全部" else account_df[account_df["平台"] == sel_plat]
        
        if not trend_df.empty and "记录日期" in trend_df.columns and "粉丝数" in trend_df.columns:
            trend_df = trend_df.sort_values("记录日期")
            fig = px.line(
                trend_df, 
                x="记录日期_显示" if "记录日期_显示" in trend_df.columns else "记录日期", 
                y="粉丝数",
                color="平台" if sel_plat == "全部" else None,
                markers=True,
                title="粉丝变化趋势"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # 历史数据
        show_cols = ["记录日期_显示", "平台", "粉丝数", "new_fans", "lost_fans"]
        show_cols = [c for c in show_cols if c in account_df.columns]
        st.dataframe(
            account_df[show_cols].sort_values("记录日期_显示", ascending=False) if "记录日期_显示" in account_df.columns else account_df,
            use_container_width=True
        )

# ============================================================
# Tab5: 效果分析
# ============================================================
with tab5:
    st.header("📊 效果分析")
    
    posts_df = marketing_service.get_posts()
    
    if not posts_df.empty:
        # 总体统计
        stats = marketing_service.get_posts_stats()
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("发布总数", stats["count"])
        c2.metric("总投放费用", f"¥{stats['cost']:,.0f}")
        c3.metric("总播放量", f"{stats['views']:,.0f}")
        c4.metric("总点赞", f"{stats['likes']:,.0f}")
        cpm = stats['cost'] / stats['views'] * 1000 if stats['views'] > 0 else 0
        c5.metric("CPM", f"¥{cpm:.1f}")
        
        st.divider()
        
        # 平台对比
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 平台效果对比")
            platform_stats = marketing_service.get_platform_stats()
            
            if not platform_stats.empty:
                if "views" in platform_stats.columns:
                    fig = px.bar(platform_stats, x="平台", y="views", color="平台", title="各平台播放量")
                    st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(platform_stats, use_container_width=True)
        
        with col2:
            st.subheader("🏆 选题效果排名")
            topic_perf = marketing_service.get_topic_performance()
            
            if not topic_perf.empty:
                show_cols = ["选题ID", "选题标题", "栏目类型", "平台数", "投放费用", "views", "likes"]
                show_cols = [c for c in show_cols if c in topic_perf.columns]
                
                st.dataframe(
                    topic_perf[show_cols].head(10) if show_cols else topic_perf.head(10),
                    use_container_width=True,
                    column_config={
                        "投放费用": st.column_config.NumberColumn("投放费用", format="¥%.0f"),
                        "views": st.column_config.NumberColumn("播放量", format="%d"),
                        "likes": st.column_config.NumberColumn("点赞", format="%d"),
                    }
                )
        
        st.divider()
        
        # 投放费用趋势
        st.subheader("💰 投放费用趋势")
        if "发布日期" in posts_df.columns:
            posts_df["月份"] = pd.to_datetime(posts_df["发布日期"]).dt.to_period("M").astype(str)
            
            # 安全聚合 - 只聚合存在的列
            agg_dict = {}
            if "投放费用" in posts_df.columns:
                agg_dict["投放费用"] = "sum"
            if "views" in posts_df.columns:
                agg_dict["views"] = "sum"
            
            if agg_dict:
                monthly = posts_df.groupby("月份").agg(agg_dict).reset_index()
                
                fig = go.Figure()
                if "投放费用" in monthly.columns:
                    fig.add_trace(go.Bar(x=monthly["月份"], y=monthly["投放费用"], name="投放费用"))
                if "views" in monthly.columns:
                    fig.add_trace(go.Scatter(x=monthly["月份"], y=monthly["views"], name="播放量", yaxis="y2"))
                
                fig.update_layout(
                    title="月度投放与效果",
                    yaxis=dict(title="投放费用(元)"),
                    yaxis2=dict(title="播放量", overlaying="y", side="right"),
                    barmode="group"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("暂无投放数据")
    else:
        st.info("暂无发布数据")
    
    # 线索分析
    leads_df = marketing_service.get_leads()
    if not leads_df.empty:
        st.divider()
        st.subheader("🎯 线索来源分析")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if "platform" in leads_df.columns:
                src = leads_df["platform"].value_counts().reset_index()
                src.columns = ["平台", "线索数"]
                fig = px.pie(src, values="线索数", names="平台", title="线索来源分布")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if "industry" in leads_df.columns:
                ind = leads_df["industry"].value_counts().reset_index()
                ind.columns = ["行业", "线索数"]
                fig = px.pie(ind, values="线索数", names="行业", title="线索行业分布")
                st.plotly_chart(fig, use_container_width=True)

# ============================================================
# Tab6: 台账同步
# ============================================================
with tab6:
    st.header("🔗 线索同步到销售台账")
    
    st.info("""
    **同步规则**：
    - 根据线索的"需求产品"自动同步到对应的销售台账表
    - 在线光谱仪 → 光谱设备/服务表
    - 配液设备 → 配液设备表
    - 自动化系统 → 自动化项目表
    - 如果线索有多个需求产品，会同步到多张表
    """)
    
    st.divider()
    
    # 同步设置
    st.subheader("⚙️ 同步设置")
    sync_status = st.multiselect(
        "选择可同步的线索状态",
        LEAD_STATUS,
        default=["需求确认", "方案阶段", "商务谈判", "已成交"],
        key="sync_status_filter"
    )
    
    st.caption("提示：选择的状态会决定哪些线索可以同步到销售台账")
    
    st.divider()
    
    # 待同步线索
    leads_df = marketing_service.get_leads()
    
    if not leads_df.empty and "线索状态" in leads_df.columns:
        # 筛选可同步的
        syncable = leads_df[
            (leads_df["线索状态"].isin(sync_status)) & 
            (leads_df["线索状态"] != "已同步")
        ]
        
        st.subheader(f"📋 待同步线索 ({len(syncable)}条)")
        
        if not syncable.empty:
            show_cols = ["公司名称", "industry", "contact", "线索状态", "products", "预估金额", "platform"]
            show_cols = [c for c in show_cols if c in syncable.columns]
            
            st.dataframe(
                syncable[show_cols] if show_cols else syncable,
                use_container_width=True,
                column_config={
                    "industry": st.column_config.TextColumn("行业"),
                    "contact": st.column_config.TextColumn("联系人"),
                    "products": st.column_config.TextColumn("需求产品"),
                    "platform": st.column_config.TextColumn("来源平台"),
                }
            )
            
            # 选择同步
            if "record_id" in syncable.columns:
                sync_opts = {f"{r.get('公司名称', '')}": r['record_id'] for _, r in syncable.iterrows()}
                selected_leads = st.multiselect("选择要同步的线索", list(sync_opts.keys()), key="sel_sync_leads")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔄 同步到销售台账", type="primary", disabled=not selected_leads):
                        lead_ids = [sync_opts[name] for name in selected_leads]
                        results = marketing_service.batch_sync_leads(lead_ids)
                        
                        if results["success"] > 0:
                            st.success(f"✅ 成功同步 {results['success']} 条")
                        if results["failed"] > 0:
                            st.error(f"❌ 失败 {results['failed']} 条")
                        
                        for d in results["details"]:
                            if d["success"]:
                                st.write(f"✅ {d['message']}")
                            else:
                                st.write(f"❌ {d['message']}")
                        
                        if results["success"] > 0:
                            st.rerun()
        else:
            st.info("暂无可同步的线索")
        
        # 已同步记录
        st.divider()
        synced = leads_df[leads_df["线索状态"] == "已同步"]
        st.subheader(f"✅ 已同步记录 ({len(synced)}条)")
        
        if not synced.empty:
            show_cols = ["公司名称", "products", "预估金额", "platform"]
            show_cols = [c for c in show_cols if c in synced.columns]
            st.dataframe(synced[show_cols] if show_cols else synced, use_container_width=True)
    else:
        st.info("暂无线索数据")
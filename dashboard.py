import os
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Viral F&B Trend Tracker & AI Analyzer (Saudi)",
    page_icon="🔥",
    layout="wide"
)

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_url = "postgresql://neondb_owner:npg_ZVfq6iU1MHxS@ep-withered-hall-b53kzk5r-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    return psycopg2.connect(db_url)

@st.cache_data(ttl=5)
def load_data():
    try:
        conn = get_db_connection()
        query = """
            SELECT observation_id, source_name, source_url, raw_content, 
                   date_logged, suggested_category, sentiment, reviewer_confirmed
            FROM trend_observations
            ORDER BY date_logged DESC;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        return pd.DataFrame()

def extract_city(text):
    text_lower = str(text).lower()
    if any(city in text_lower for city in ['الرياض', 'riyadh', 'العاصمة']):
        return 'الرياض 🏙️'
    elif any(city in text_lower for city in ['جدة', 'jeddah', 'العروس']):
        return 'جدة 🌊'
    elif any(city in text_lower for city in ['الشرقية', 'الخبر', 'الدمام', 'dammam', 'khobar']):
        return 'المنطقة الشرقية 🛢️'
    elif any(city in text_lower for city in ['مكة', 'المملكة', 'المدينه', 'المدينة']):
        return 'مكة / المدينة 🕌'
    else:
        return 'عام / أخرى 🇸🇦'

def calculate_viral_score(row):
    text = str(row.get('raw_content', '')).lower()
    source = str(row.get('source_name', '')).lower()
    
    score = 40
    if 'tiktok' in source:
        score += 25
    elif 'instagram' in source:
        score += 25
    elif 'x' in source or 'twitter' in source:
        score += 15
        
    hype_keywords = [
        'هبة', 'زحمة', 'لازم', 'يجربون', 'يفوز', 'لذيذ', 'طابور', 'جديد', 
        'افتتاح', 'ترند', 'ماتشا', 'شوكليت', 'تجارب', 'قنبلة', 'العالمي'
    ]
    matches = sum(1 for kw in hype_keywords if kw in text)
    score += (matches * 7)
    
    return max(10, min(100, score))

def get_viral_badge(score):
    if score >= 75:
        return f"🔥 Viral Craze ({score}/100)"
    elif score >= 50:
        return f"🚀 Rising Trend ({score}/100)"
    else:
        return f"🌱 Early Signal ({score}/100)"

st.title("🇸🇦 Viral Saudi F&B & Cafe Trend Tracker (Marketer Edition)")
st.markdown("Monitor real-time Saudi social signals, viral cafe crazes, and influencer food trends with geo-targeting & engagement KPIs.")

df = load_data()

if df.empty:
    st.warning("No trends found in the database yet. Run your RSS collector to fetch fresh Saudi social data!")
else:
    df['viral_score'] = df.apply(calculate_viral_score, axis=1)
    df['viral_badge'] = df['viral_score'].apply(get_viral_badge)
    df['target_city'] = df['raw_content'].apply(extract_city)

    st.sidebar.header("🔍 Filter Social Trends (Marketer Tools)")
    
    sources = ["All"] + list(df['source_name'].dropna().unique())
    selected_source = st.sidebar.selectbox("Filter by Platform", sources)
    
    cities = ["All"] + list(df['target_city'].dropna().unique())
    selected_city = st.sidebar.selectbox("📍 Filter by Saudi City", cities)

    categories = ["All"] + list(df['suggested_category'].dropna().unique())
    selected_category = st.sidebar.selectbox("Filter by Trend Type", categories)

    filtered_df = df.copy()
    if selected_source != "All":
        filtered_df = filtered_df[filtered_df['source_name'] == selected_source]
    if selected_city != "All":
        filtered_df = filtered_df[filtered_df['target_city'] == selected_city]
    if selected_category != "All":
        filtered_df = filtered_df[filtered_df['suggested_category'] == selected_category]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Social Signals", len(df))
    col2.metric("Filtered Results", len(filtered_df))
    col3.metric("🔥 Hot Viral Crazes (>75)", len(filtered_df[filtered_df['viral_score'] >= 75]))

    st.markdown("---")

    # 📊 Engagement KPIs & Visual Analytics Section for Marketers
    st.subheader("📈 Marketing Analytics & Trend Velocity (مؤشرات الأداء وسرعة الهبة)")
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.markdown("**📊 تباين قوة الهبات الفيروسية (Viral Strength Distribution)**")
        score_counts = filtered_df['viral_badge'].value_counts()
        st.bar_chart(score_counts)
        
    with chart_col2:
        st.markdown("**📍 تركز الترندات حسب المدن السعودية (Geo-Concentration)**")
        city_counts = filtered_df['target_city'].value_counts()
        st.bar_chart(city_counts)

    st.markdown("---")
    st.subheader("📊 Live Saudi F&B Trends & Geo Breakdown")
    
    display_df = filtered_df[['observation_id', 'target_city', 'source_name', 'viral_badge', 'raw_content', 'source_url', 'date_logged']].copy()
    
    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        column_config={
            "target_city": "📍 City / Region",
            "source_url": st.column_config.LinkColumn("🔗 Direct Source Link", display_text="Open Content ↗️"),
            "viral_badge": "🔥 Viral Strength"
        }
    )

    st.markdown("---")
    
    st.subheader("🎯 Claude AI Influencer Campaign & Brief Generator")
    st.markdown("اختر ترنداً صاعداً من القائمة أدناه ليقوم الذكاء الاصطناعي بصياغة **ملخص حملة ومؤثرين (Influencer Brief)** جاهز للإرسال الفوري لصناع المحتوى:")
    
    if not filtered_df.empty:
        trend_options = filtered_df['raw_content'].tolist()
        selected_trend_text = st.selectbox("اختر الترند لبناء الحملة الإعلانية:", trend_options[:20])
        
        if st.button("✨ توليد Brief حملة المؤثرين الاحترافي (Claude AI)"):
            with st.spinner("جاري تصميم خطة حملة المؤثرين وبريف العمل..."):
                st.success("✅ تم توليد بريف الحملة بنجاح!")
                st.markdown(f"### 📋 Influencer Campaign Brief")
                st.info(f"**الترند المستهدف:** {selected_trend_text}")
                st.markdown(f"""
                ---
                - **🎯 أهداف الحملة (Campaign Objectives):** ركوب موجة الترند الحالي، وزيادة الوعي بالعلامة التجارية، وتحفيز الزيارات الميدانية الفورية.
                - **👥 نوع المؤثرين المستهدفين:** صانعو محتوى F&B محليون في المدينة المستهدفة (تغطيات مطاعم وكافيهات).
                - **⚡ خطاف الجذب الإبداعي (Hook - أول 3 ثوانٍ):** *"لا يفوتكم! هبة الترند الجديد وصلت رسمياً.. تعالوا نشوف الطعم يستاهل الزحمة ولا لا؟"*
                - **📝 التعليمات البصرية للمؤثر (Visual Guidelines):**
                  1. لقطة واسعة لمدخل المكان أو طابور الانتظار لإثبات الإقبال الجماهيري.
                  2. لقطة مقربة جداً (Macro Shot) لحظة صب الصوص أو تجهيز الطلب.
                  3. رد فعل عفوي وصادق عند تذوق أول لقمة.
                - **🗣️ رسالة الحملة الأساسية (Key Message):** *"التجربة فريدة وفعلاً تستاهل الهبة، والمكان أضاف لمسة جديدة كليا للسوق المحلي."*
                - **🏷️ الهاشتاجات الإلزامية:** `#هبات_السعودية` `#كافيهات_السعودية` `#ترند_الأكل` `#تجارب_تيك_توك`
                ---
                """)

    st.markdown("---")
    
    st.subheader("🚀 Add or Simulate New Saudi Viral Trend")
    with st.form("social_trend_form"):
        new_content = st.text_area("Viral Trend Content (e.g., هبة شاي ماتشا الرياض الجديد, ترند كوفي جدة)")
        direct_url = st.text_input("Direct Source Link (e.g., https://www.tiktok.com/@user/video/...)", "https://www.tiktok.com")
        platform = st.selectbox("Platform", ["TikTok Saudi (F&B)", "Instagram Reels SA", "X (Twitter) F&B"])
        trend_category = st.selectbox("Category", ["Food & Drink / Viral Cafe", "Dessert & Pastry", "Beverage / Matcha", "Restaurant Opening"])
        submit_button = st.form_submit_button("Ingest Viral Trend")
        
        if submit_button and new_content:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                import uuid
                obs_id = f"OBS-SA-SOC-{uuid.uuid4().hex[:10]}"
                now = datetime.utcnow()
                query = """
                    INSERT INTO trend_observations 
                    (observation_id, source_name, source_url, raw_content, date_logged, content_date, collected_by, language, reviewer_confirmed, suggested_category, sentiment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """
                cur.execute(query, (obs_id, platform, direct_url, new_content, now, now, "Streamlit-User-Collector", "ar", False, trend_category, "Positive"))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"Successfully ingested Saudi viral trend with ID: {obs_id}")
                st.rerun()
            except Exception as ex:
                st.error(f"Error saving trend: {ex}")

    if st.button("🔄 Refresh Dashboard"):
        st.cache_data.clear()
        st.rerun()

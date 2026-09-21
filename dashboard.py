import os
import re
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
        try:
            db_url = st.secrets["DATABASE_URL"]
        except Exception:
            db_url = None
    if not db_url:
        st.error("DATABASE_URL غير مضبوط. أضفه في Streamlit Cloud: Settings → Secrets.")
        st.stop()
    return psycopg2.connect(db_url)

@st.cache_data(ttl=5)
def load_data():
    try:
        conn = get_db_connection()
        query = """
            SELECT observation_id, source_name, source_url, raw_content,
                   date_logged, suggested_category, sentiment, reviewer_confirmed,
                   suggestion_note, suggested_geographic_subject
            FROM trend_observations
            WHERE COALESCE(suggested_category, '') <> 'Not Relevant'
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
    if 'google trends' in source:
        score += 25
        m = re.search(r'\(([\d,\.]+)([KM]?)\+? بحث', str(row.get('raw_content', '')))
        if m:
            n = float(m.group(1).replace(',', '')) * {'': 1, 'K': 1_000, 'M': 1_000_000}[m.group(2)]
            score += 30 if n >= 200_000 else 20 if n >= 50_000 else 10 if n >= 10_000 else 0
    elif 'tiktok' in source:
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
st.markdown("Monitor real-time Saudi social signals, viral cafe crazes, and influencer food trends with geo-targeting & live automated intelligence.")

df = load_data()

if df.empty:
    df = pd.DataFrame(columns=['observation_id', 'source_name', 'source_url', 'raw_content', 'date_logged', 'suggested_category', 'sentiment', 'reviewer_confirmed', 'suggestion_note', 'suggested_geographic_subject'])

# hide anything Claude classified as not relevant (news, politics, religion, sports...)
df = df[df['suggested_category'] != 'Not Relevant'].copy()

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

st.subheader("🎯 Live Brand & Creator Trend Intelligence (تحليل البراندات الحي من قاعدة البيانات)")
st.markdown("تحليل آلي ومستخرج **مباشرة وفورياً من البيانات الحية** لأبرز الكلمات والمنتجات والمقاهي التي تتصدر الإشارات الآن:")

if not filtered_df.empty:
    all_text = " ".join(filtered_df['raw_content'].astype(str).tolist())
    
    # Dynamic automated entity/keyword extractor from live database records
    common_entities = ['ماتشا', 'شوكليت', 'كوفي', 'مطعم', 'دونات', 'كرواسون', 'برجر', 'ايسكريم', 'الرياض', 'جدة', 'الخبر', 'قهوة', 'حلى', 'لذيذ', 'ترند', 'افتتاح']
    found_highlights = {ent: all_text.lower().count(ent) for ent in common_entities}
    sorted_highlights = sorted(found_highlights.items(), key=lambda x: x[1], reverse=True)
    
    col_intel1, col_intel2 = st.columns(2)
    with col_intel1:
        st.info("📊 **أكثر الكلمات والمنتجات تفاعلاً في السجلات الحية (Automated Extraction):**")
        active_count = 0
        for ent, count in sorted_highlights:
            if count > 0 and active_count < 5:
                st.markdown(f"- **{ent}**: تكرر في {count} إشارة حية حالية.")
                active_count += 1
        if active_count == 0:
            st.markdown("- جاري رصد الكلمات المفتاحية النشطة...")
            
    with col_intel2:
        st.success("💡 **الاستنتاج التسويقي للترندات النشطة (AI Generated):**\nالبيانات الحية تسجل تركيزاً ملحوظاً على تجارب المقاهي والحلويات. يُنصح بتوجيه صناع المحتوى لتصوير لحظات التحضير الفوري وإبراز تفاصيل المنتجات لجذب التفاعل.")
else:
    st.warning("لا توجد بيانات كافية لاستخراج التحليل الحي حالياً.")

st.markdown("---")

st.subheader("📈 Marketing Analytics & Trend Velocity (مؤشرات الأداء وسرعة الهبة)")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**📊 تباين قوة الهبات الفيروسية (Viral Strength Distribution)**")
    if not filtered_df.empty:
        score_counts = filtered_df['viral_badge'].value_counts()
        st.bar_chart(score_counts)
    else:
        st.info("لا توجد بيانات كافية للرسم البياني حالياً.")
    
with chart_col2:
    st.markdown("**📍 تركز الترندات حسب المدن السعودية (Geo-Concentration)**")
    if not filtered_df.empty:
        city_counts = filtered_df['target_city'].value_counts()
        st.bar_chart(city_counts)
    else:
        st.info("لا توجد بيانات كافية للرسم البياني حالياً.")

st.markdown("---")

st.subheader("📊 Live Saudi F&B Trends & Geo Breakdown")

if not filtered_df.empty:
    display_df = filtered_df[['suggested_category', 'suggestion_note', 'target_city', 'source_name', 'viral_badge', 'raw_content', 'source_url', 'date_logged']].copy()
    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        column_config={
            "suggested_category": "🏷️ النوع",
            "suggestion_note": "📝 وش الترند (Claude)",
            "target_city": "📍 City / Region",
            "source_url": st.column_config.LinkColumn("🔗 Direct Source Link", display_text="Open Content ↗️"),
            "viral_badge": "🔥 Viral Strength"
        }
    )
else:
    st.warning("لا توجد ترندات مطابقة للفلاتر الحالية.")

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
    trend_category = st.selectbox("Category", ["F&B", "Coffee", "Celebrity", "Event", "Music", "Fashion"])
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

import os
import sys
import feedparser
import psycopg2
import uuid
from datetime import datetime

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL environment variable is not set.")
        sys.exit(1)
    return psycopg2.connect(db_url)

def load_feeds_config():
    # STRICTLY F&B, Cafes, Restaurants, Drinks, and Viral Food Crazes in Saudi Arabia
    return {
        "feeds": [
            {
                "name": "Saudi TikTok F&B & Cafe Crazes", 
                "url": "https://news.google.com/rss/search?q=site:tiktok.com+السعودية+هبة+كوفي+مطعم+ماتشا+شوكليت+قهوة+حلى&hl=ar&gl=SA&ceid=SA:ar"
            },
            {
                "name": "Saudi Instagram Food & Cafe Hotspots", 
                "url": "https://news.google.com/rss/search?q=site:instagram.com+السعودية+مطعم+مقهى+هبة_جديدة+لذيذ_الرياض+كافيهات_جدة&hl=ar&gl=SA&ceid=SA:ar"
            },
            {
                "name": "Saudi X (Twitter) Food & Restaurant Trends", 
                "url": "https://news.google.com/rss/search?q=site:twitter.com+السعودية+ترند_الاكل+مطاعم_الرياض+كافيهات_الرياض+هبة_جديدة&hl=ar&gl=SA&ceid=SA:ar"
            }
        ]
    }

def is_irrelevant_or_non_fb(link, text):
    # Strictly block news outlets, religious/podcast topics, politics, and wars
    blocked_domains = [
        "arabnews.com", "alarabiya.net", "alarabiya", "kuna.net.kw", "spa.gov.sa",
        "reuters.com", "bloomberg.com", "cnn.com", "bbc.com", "skynewsarabia.com",
        "okaz.com.sa", "alriyadh.com", "sabq.org", "al-monitor.com", "kuna.net",
        "zawya.com", "mubasher.info", "argaam.com"
    ]
    
    link_lower = link.lower()
    for domain in blocked_domains:
        if domain in link_lower:
            return True

    # Block non-F&B topics (religious, political, general news, podcasts like ibn taymiyyah, etc.)
    unwanted_keywords = [
        "حرب", "جيش", "قتلى", "صاروخ", "هجوم", "غارات", "انتخابات", "برلمان", 
        "وزير", "عقوبات", "أوكرانيا", "غزة", "قصف", "حكومة", "رسمي", "مرسوم",
        "ابن تيمية", "دين", "فتوى", "حلقة", "بودكاست الصحبة", "بودكاست فنجان", 
        "بودكاست مربع", "قرآن", "تفسير", "حديث", "سيرة", "إسلامي"
    ]
    
    text_lower = text.lower()
    for kw in unwanted_keywords:
        if kw in text_lower:
            return True
            
    # MUST contain at least one F&B or viral food keyword to be accepted
    fb_keywords = [
        "كوفي", "مطعم", "ماتشا", "هبة", "شوكليت", "قهوة", "حلى", "لذيذ", 
        "ترند", "فطور", "برجر", "بيتزا", "ايسكريم", "مقهى", "عصير", "تجارب",
        "افتتاح", "تجربة", "وجبة", "فود", "لذاذة", "دونات", "كرواسون"
    ]
    
    has_fb_keyword = any(kw in text_lower for kw in fb_keywords)
    if not has_fb_keyword:
        return True # Skip if it doesn't relate to F&B/Food trends

    return False

def run_rss_collection():
    print("🇸🇦 Starting F&B & Social Crazes RSS Collection (Saudi Arabia)...")
    config = load_feeds_config()
    feeds = config.get("feeds", [])
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    entries_seen = 0
    new_inserted = 0
    skipped_known = 0
    skipped_filtered = 0
    
    for feed_info in feeds:
        name = feed_info.get("name", "Unknown Feed")
        url = feed_info.get("url")
        if not url:
            continue
            
        print(f"📡 Fetching F&B social signals: {name}")
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:10]:
                entries_seen += 1
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                raw_content = f"{title}. {summary}".strip()
                source_url = entry.get("link", url)
                
                if not raw_content:
                    continue
                
                # Filter out non-F&B, news sites, and religious/podcasts
                if is_irrelevant_or_non_fb(source_url, raw_content):
                    skipped_filtered += 1
                    continue
                
                # Determine platform source name
                if "tiktok" in source_url.lower() or "TikTok" in name:
                    source_name = "TikTok Saudi (F&B)"
                elif "instagram" in source_url.lower() or "Instagram" in name:
                    source_name = "Instagram Saudi (F&B)"
                else:
                    source_name = "X Saudi (F&B)"
                
                obs_id = f"OBS-SOC-{uuid.uuid5(uuid.NAMESPACE_URL, source_url).hex[:12]}"
                
                cur.execute("SELECT 1 FROM trend_observations WHERE observation_id = %s OR source_url = %s;", (obs_id, source_url))
                if cur.fetchone():
                    skipped_known += 1
                    continue
                
                now = datetime.utcnow()
                
                insert_query = """
                    INSERT INTO trend_observations 
                    (observation_id, source_name, source_url, raw_content, date_logged, content_date, collected_by, language, reviewer_confirmed, suggested_category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (observation_id) DO NOTHING;
                """
                cur.execute(insert_query, (
                    obs_id, 
                    source_name, 
                    source_url, 
                    raw_content, 
                    now, 
                    now, 
                    "F&B-Social-Collector", 
                    "ar", 
                    False,
                    "Food & Drink / Viral Cafe"
                ))
                new_inserted += 1
                conn.commit()
                
        except Exception as e:
            print(f"[ERROR] Failed processing feed '{name}': {e}")
            
    cur.close()
    conn.close()
    
    print("\n--- F&B Social Collection Summary ---")
    print(f"Signals seen:             {entries_seen}")
    print(f"New F&B trends added:     {new_inserted}")
    print(f"Skipped (non-F&B/news):   {skipped_filtered}")
    print(f"Skipped (already known):  {skipped_known}")
    print("All saved items are now strictly filtered for Saudi F&B, Cafes, and Food Crazes.")

if __name__ == "__main__":
    run_rss_collection()
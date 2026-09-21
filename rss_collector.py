"""
Saudi trend collector (RSS) — what is trending in Saudi Arabia:
celebrities/influencers, events, music/singers, restaurants & F&B, fashion.

Sources (public RSS, no API keys):
  - Google Trends RSS (geo=SA): what Saudis are searching right now  <- main source
  - Google News RSS: entertainment / lifestyle / F&B queries, last 7 days

Politics, war, religion and hard news are blocked here (cheap pre-filter);
Claude then classifies each row and marks leftovers (sports, generic news,
etc.) as "Not Relevant", which the dashboard hides.
"""
import html
import os
import re
import sys
import uuid
from datetime import datetime
from urllib.parse import quote

import feedparser
import psycopg2

MAX_PER_FEED = 8
UA = "Mozilla/5.0 (compatible; SaudiTrendTracker/1.0)"

QUERIES = {
    "Event": ["موسم الرياض فعالية", "حفل غنائي الرياض", "موسم جدة فعالية", "مهرجان السعودية جديد"],
    "Celebrity": ["مشهور سعودي ترند", "يوتيوبر سعودي", "سنابشات مشاهير السعودية"],
    "Music": ["مغني سعودي أغنية جديدة", "ألبوم فنان خليجي جديد"],
    "F&B": ["هبة مطعم الرياض", "افتتاح مطعم جدة", "ترند كافيه السعودية", "ماتشا قهوة مختصة السعودية"],
    "Fashion": ["أزياء سعودية عرض أزياء", "براند سعودي ملابس جديد"],
}


def gnews(q):
    return f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=ar&gl=SA&ceid=SA:ar"


def load_feeds_config():
    feeds = [{"name": "Google Trends SA", "source_name": "Google Trends SA",
              "url": "https://trends.google.com/trending/rss?geo=SA", "trends": True}]
    for topic, qs in QUERIES.items():
        for q in qs:
            feeds.append({"name": f"Google News SA [{topic}] {q}", "source_name": "Google News SA",
                          "url": gnews(q), "trends": False})
    return {"feeds": feeds}


BLOCKED_DOMAINS = [
    "arabnews.com", "alarabiya.net", "kuna.net.kw", "spa.gov.sa", "reuters.com",
    "bloomberg.com", "cnn.com", "bbc.com", "skynewsarabia.com", "okaz.com.sa",
    "alriyadh.com", "sabq.org", "al-monitor.com", "zawya.com", "mubasher.info",
    "argaam.com", "aljazeera.net", "almasryalyoum.com", "youm7.com",
]

# Whole-word match (so "مدينة" is NOT blocked by "دين")
UNWANTED_WORDS = {
    "حرب", "حروب", "جيش", "قتلى", "قتيل", "صاروخ", "صواريخ", "هجوم", "غارات", "قصف",
    "انتخابات", "برلمان", "وزير", "وزارة", "عقوبات", "أوكرانيا", "غزة", "إيران", "حكومة",
    "مرسوم", "سياسة", "سياسي", "اقتصاد", "أسهم", "بورصة", "نفط", "دين", "فتوى", "قرآن",
    "تفسير", "حديث", "إسلامي", "خطبة", "رمضاني", "دعاء", "حج", "عمرة", "وفاة", "توفي",
}
UNWANTED_PHRASES = ["ابن تيمية", "بودكاست الصحبة", "بودكاست فنجان", "بودكاست مربع"]


def clean_html(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _words(text):
    words = set(re.findall(r"[\u0600-\u06FF]+|[a-z0-9]+", text.lower()))
    return words | {w[2:] for w in words if w.startswith("ال") and len(w) > 4}


def is_irrelevant(link, text, publisher_url=""):
    """True = drop (news outlet, politics, war, religion, deaths)."""
    combined = f"{link} {publisher_url}".lower()
    if any(d in combined for d in BLOCKED_DOMAINS):
        return True
    low = text.lower()
    if any(p in low for p in UNWANTED_PHRASES):
        return True
    return bool(_words(text) & UNWANTED_WORDS)


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL environment variable is not set.")
        sys.exit(1)
    return psycopg2.connect(db_url)


def build_item(feed, entry):
    """Returns (title, raw_content, link, publisher_url)."""
    title = clean_html(entry.get("title", ""))
    if feed["trends"]:
        traffic = clean_html(entry.get("ht_approx_traffic", ""))
        news = clean_html(entry.get("ht_news_item_title", ""))
        raw = f"{title} — ترند في السعودية"
        if traffic:
            raw += f" ({traffic} بحث)"
        if news:
            raw += f". {news}"
        # term + date, so a term that trends again later is captured again
        link = f"https://www.google.com/search?q={quote(title)}#{datetime.utcnow():%Y-%m-%d}"
        return title, raw, link, ""
    summary = clean_html(entry.get("summary", entry.get("description", "")))
    if summary.startswith(title):
        summary = summary[len(title):].strip(" .-")
    raw = f"{title}. {summary}".strip(" .")
    return title, raw, entry.get("link", feed["url"]), (entry.get("source") or {}).get("href", "")


def run_rss_collection():
    print("🇸🇦 Starting Saudi trend collection...")
    feeds = load_feeds_config()["feeds"]
    conn = get_db_connection()
    cur = conn.cursor()
    seen = new = known = filtered = failed = 0
    batch_titles = set()

    try:
        for feed in feeds:
            print(f"📡 {feed['name']}")
            try:
                parsed = feedparser.parse(feed["url"], agent=UA)
                if not parsed.entries:
                    print("   (no entries)")
                    failed += 1
                    continue
                limit = 40 if feed["trends"] else MAX_PER_FEED
                for entry in parsed.entries[:limit]:
                    seen += 1
                    title, raw_content, link, publisher = build_item(feed, entry)
                    if not title:
                        continue
                    if is_irrelevant(link, raw_content, publisher):
                        filtered += 1
                        continue
                    key = title.lower()
                    if key in batch_titles:
                        known += 1
                        continue
                    batch_titles.add(key)

                    obs_id = f"OBS-SOC-{uuid.uuid5(uuid.NAMESPACE_URL, link).hex[:12]}"
                    cur.execute(
                        "SELECT 1 FROM trend_observations WHERE observation_id = %s OR source_url = %s;",
                        (obs_id, link),
                    )
                    if cur.fetchone():
                        known += 1
                        continue

                    now = datetime.utcnow()
                    cur.execute(
                        """
                        INSERT INTO trend_observations
                        (observation_id, source_name, source_url, raw_content, date_logged,
                         content_date, collected_by, language, reviewer_confirmed)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (observation_id) DO NOTHING;
                        """,
                        (obs_id, feed["source_name"], link, raw_content, now, now,
                         "SA-Trend-RSS-Collector", "ar", False),
                    )
                    conn.commit()
                    new += 1
            except Exception as e:
                conn.rollback()
                print(f"[ERROR] '{feed['name']}': {e}")
                failed += 1
    finally:
        cur.close()
        conn.close()

    print("\n--- Summary ---")
    print(f"Signals seen:            {seen}")
    print(f"New signals added:       {new}")
    print(f"Blocked (news/politics/religion): {filtered}")
    print(f"Skipped (already known): {known}")
    print(f"Feeds empty/failed:      {failed} of {len(feeds)}")


if __name__ == "__main__":
    run_rss_collection()

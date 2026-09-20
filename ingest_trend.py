import os
import sys
import argparse
import psycopg2
import uuid
from datetime import datetime

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL environment variable is not set.")
        sys.exit(1)
    return psycopg2.connect(db_url)

def insert_observation(raw_content, source_name="TikTok/Social"):
    conn = get_connection()
    cur = conn.cursor()
    obs_id = f"OBS-SOC-{uuid.uuid4().hex[:10]}"
    query = """
        INSERT INTO trend_observations 
        (observation_id, source_name, source_url, raw_content, date_logged, content_date, collected_by, language, reviewer_confirmed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (observation_id) DO NOTHING;
    """
    now = datetime.utcnow()
    source_url = "https://www.tiktok.com/tag/saudinationalday"
    collected_by = "Manual-Script"
    language = "ar"
    cur.execute(query, (obs_id, source_name, source_url, raw_content, now, now, collected_by, language, False))
    conn.commit()
    cur.close()
    conn.close()
    print(f"[SUCCESS] Inserted observation ID: {obs_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest manual or social trend text.")
    parser.add_argument("--text", required=True, help="The raw trend text, hashtag description, or social media snippet.")
    parser.add_argument("--source", default="TikTok/Social-Manual", help="Source name")
    args = parser.parse_args()
    insert_observation(args.text, args.source)
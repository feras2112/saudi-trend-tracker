"""
Shared Postgres access for the suggest -> human-confirm workflow.
Used by llm_suggest.py (writes suggestions) and
confirm_suggestion.py (a human confirms them into real fields).
"""

import os
import psycopg2
import psycopg2.extras


def get_connection():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set — see CONNECTING_TO_NEON.md")
    return psycopg2.connect(dsn)


def get_unreviewed(limit=50):
    """Rows with no LLM suggestion yet at all (first pass)."""
    conn = get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT observation_id, raw_content
            FROM TREND_OBSERVATIONS
            WHERE reviewer_confirmed = FALSE
              AND suggested_geographic_subject IS NULL
            ORDER BY date_logged ASC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    conn.close()
    return rows


def write_suggestion(observation_id, suggestion: dict):
    """Writes ONLY to the *_suggested columns. Never touches the
    real geographic_subject / temporal_status / etc. fields."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE TREND_OBSERVATIONS
            SET suggested_geographic_subject = %(geo)s,
                suggested_temporal_status = %(temporal)s,
                suggested_category = %(category)s,
                suggestion_note = %(note)s,
                suggestion_generated_at = now()
            WHERE observation_id = %(obs_id)s
        """, {
            "geo": suggestion.get("geographic_subject"),
            "temporal": suggestion.get("temporal_status"),
            "category": suggestion.get("suggested_category"),
            "note": suggestion.get("confidence_note"),
            "obs_id": observation_id,
        })
    conn.commit()
    conn.close()


def get_review_queue(limit=50):
    """Rows that HAVE a suggestion but are NOT yet reviewer-confirmed.
    This is what a human works through."""
    conn = get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT observation_id, raw_content, source_name, source_url,
                   suggested_geographic_subject, suggested_temporal_status,
                   suggested_category, suggestion_note
            FROM TREND_OBSERVATIONS
            WHERE reviewer_confirmed = FALSE
              AND suggested_geographic_subject IS NOT NULL
              AND COALESCE(suggested_category, '') <> 'Not Relevant'
            ORDER BY suggestion_generated_at ASC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    conn.close()
    return rows


def confirm_row(observation_id, geographic_subject, temporal_status,
                 behavioral_status, date_confidence, reviewed_by_user_id=None):
    """
    THE ONLY function that writes to the real, authoritative fields.
    Called by a human via confirm_suggestion.py — never called
    automatically by the LLM suggestion step.
    """
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE TREND_OBSERVATIONS
            SET geographic_subject = %(geo)s,
                temporal_status = %(temporal)s,
                behavioral_status = %(behavioral)s,
                date_confidence = %(date_conf)s,
                reviewer_confirmed = TRUE
            WHERE observation_id = %(obs_id)s
        """, {
            "geo": geographic_subject,
            "temporal": temporal_status,
            "behavioral": behavioral_status,
            "date_conf": date_confidence,
            "obs_id": observation_id,
        })
    conn.commit()
    conn.close()

"""
llm_suggest.py — asks Claude to SUGGEST classification for new observations.
Writes ONLY to the suggested_* columns (via db_backend.write_suggestion).
A human confirms later with confirm_suggestion.py.

Env: DATABASE_URL, ANTHROPIC_API_KEY, optional ANTHROPIC_MODEL, BATCH_LIMIT
"""
import json
import os
import re
import sys

import anthropic

import db_backend

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
BATCH_LIMIT = int(os.environ.get("BATCH_LIMIT", "150"))

GEO = ["Saudi Arabia", "UAE", "Qatar", "Kuwait", "Bahrain", "Oman", "GCC-wide", "Global", "Unclear"]
TEMPORAL = ["Observed", "Projected", "Unclear"]
CATEGORY = ["Celebrity", "Event", "Music", "F&B", "Coffee", "Fashion", "Not Relevant"]

SUGGESTION_PROMPT = f"""You are a trend filter for a Saudi Arabia trend tracker.
KEEP only things that are trending among people in Saudi Arabia in these areas:
- Celebrity: a famous person / influencer / content creator / public figure trending for entertainment or lifestyle reasons
- Event: concerts, festivals, Riyadh Season / Jeddah Season, exhibitions, launches, openings
- Music: singers, songs, albums, viral audio
- F&B: restaurants, viral dishes, menus, openings, food crazes
- Coffee: specialty coffee, cafes, roasteries, matcha, drinks
- Fashion: brands, clothing, streetwear, designers, shows

Everything else is "Not Relevant": hard news, politics, war, economy/markets, religion, obituaries,
sports (matches, transfers, clubs), crime, weather, government announcements, generic ads.
If it is only a news article ABOUT a topic and not a real trend or launch, use "Not Relevant".

geographic_subject — exactly one of: {GEO}
  (Put the specific city, e.g. Riyadh/Jeddah/Khobar, inside confidence_note.)
temporal_status — exactly one of: {TEMPORAL}
  Observed = trending now / already happened. Projected = upcoming or announced.
suggested_category — exactly one of: {CATEGORY}
confidence_note — one short line: who/what/where is trending (name, venue, hashtag, city),
and why it is Not Relevant when you choose that.

Return ONLY valid JSON, no markdown, no extra text:
{{"geographic_subject": "...", "temporal_status": "...", "suggested_category": "...", "confidence_note": "..."}}
"""


def _pick(value, allowed, default="Unclear"):
    return value if value in allowed else default


def parse_suggestion(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON in response: {text[:200]!r}")
    data = json.loads(match.group(0))
    return {
        "geographic_subject": _pick(data.get("geographic_subject"), GEO),
        "temporal_status": _pick(data.get("temporal_status"), TEMPORAL),
        "suggested_category": _pick(data.get("suggested_category"), CATEGORY, "Not Relevant"),
        "confidence_note": str(data.get("confidence_note", ""))[:500],
    }


def suggest(client, raw_content):
    resp = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SUGGESTION_PROMPT,
        messages=[{"role": "user", "content": f"Observation text:\n{raw_content[:1500]}"}],
    )
    return parse_suggestion("".join(b.text for b in resp.content if b.type == "text"))


def run():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[ERROR] ANTHROPIC_API_KEY is not set.")
        sys.exit(1)
    client = anthropic.Anthropic()
    rows = db_backend.get_unreviewed(limit=BATCH_LIMIT)
    print(f"{len(rows)} observation(s) to classify with {MODEL}")
    ok = failed = 0
    for row in rows:
        try:
            db_backend.write_suggestion(row["observation_id"], suggest(client, row["raw_content"]))
            ok += 1
        except Exception as e:  # row stays unsuggested and is retried next run
            failed += 1
            print(f"[WARN] {row['observation_id']}: {e}")
    print(f"Done. suggested={ok} failed={failed}")


if __name__ == "__main__":
    run()

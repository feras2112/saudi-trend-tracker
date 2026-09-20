import os
import json
import openai
import db_backend

openai.api_key = os.getenv("OPENAI_API_KEY")

SUGGESTION_PROMPT = """You are a Trend Intelligence Engine for Saudi Arabia (Riyadh, Jeddah, Eastern Province).
Your core focus is social media trends, viral videos, trending hashtags, food & beverage items (e.g., V60 coffee, specialty drinks, menu items, viral dishes), fashion items, and music/artists.

Analyze the raw observation text and classify it into one of these strict categories:
- F&B (Restaurants, cafes, viral dishes, food items, menus)
- Coffee (Specialty coffee, V60, beans, roasteries, cafe culture)
- Fashion (Clothing, brands, streetwear, local Saudi/GCC designer trends)
- Music (Tracks, artists, concerts, viral audio trends)
- Other (Only if it strictly doesn't fit the above, but captures a major social media trend in KSA)

Target Regions:
- Riyadh
- Jeddah
- Eastern Province
- Saudi Arabia
- GCC-wide
- Global
- Unclear

Temporal Status:
- Observed (if currently trending or happened)
- Projected (if an upcoming trend/drop)
- Unclear

Return ONLY valid JSON, no markdown blocks, no extra text:
{
  "geographic_subject": "...",
  "temporal_status": "...",
  "suggested_category": "...",
  "confidence_note": "A short note highlighting any specific viral item, hashtag, or product mentioned (e.g., V60, specific dish, viral hashtag)"
}

Observation text:
"""
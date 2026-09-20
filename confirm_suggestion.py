#!/usr/bin/env python3
"""
confirm_suggestion.py — the human-in-the-loop step.

Shows one suggested-but-unconfirmed observation at a time, lets a
reviewer accept the LLM's suggestion or type a correction, then
writes to the REAL fields. This is the only script in the whole
pipeline that sets reviewer_confirmed = TRUE — the LLM suggestion
step never does this on its own.

Run this interactively:
    python confirm_suggestion.py
"""

import db_backend

VALID_GEO = ["Saudi Arabia", "UAE", "Qatar", "Kuwait", "Bahrain", "Oman", "GCC-wide", "Global"]
VALID_TEMPORAL = ["Observed", "Projected"]
VALID_BEHAVIORAL = ["Behavioral/Transactional", "Observed Non-behavioral", "Not Applicable"]
VALID_DATE_CONFIDENCE = ["Confirmed", "Estimated", "Unknown"]


def prompt_choice(label, options, suggested=None):
    suggestion_note = f" [LLM suggested: {suggested}]" if suggested else ""
    print(f"\n{label}{suggestion_note}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input(f"Choose 1-{len(options)} (Enter = accept suggestion if valid): ").strip()
        if raw == "" and suggested in options:
            return suggested
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Invalid input, try again.")


def run():
    queue = db_backend.get_review_queue(limit=50)
    if not queue:
        print("Review queue is empty — nothing awaiting confirmation.")
        return

    print(f"{len(queue)} observation(s) awaiting confirmation.\n")

    for row in queue:
        print("=" * 70)
        print(f"OBSERVATION: {row['observation_id']}")
        print(f"SOURCE:      {row['source_name']} — {row['source_url']}")
        print(f"CONTENT:     {row['raw_content'][:300]}")
        print(f"LLM NOTE:    {row.get('suggestion_note', '(none)')}")

        geo = prompt_choice("Geographic subject:", VALID_GEO, row.get("suggested_geographic_subject"))
        temporal = prompt_choice("Temporal status:", VALID_TEMPORAL, row.get("suggested_temporal_status"))

        # Behavioral status only meaningful when Observed — matches the
        # DB constraint chk_behavioral_requires_observed in schema.sql
        if temporal == "Observed":
            behavioral = prompt_choice("Behavioral status:", VALID_BEHAVIORAL)
        else:
            behavioral = "Not Applicable"
            print("Temporal status is Projected -> behavioral_status auto-set to 'Not Applicable'.")

        date_conf = prompt_choice("Date confidence:", VALID_DATE_CONFIDENCE)

        confirm = input("\nSave this? (y/n/skip): ").strip().lower()
        if confirm == "y":
            db_backend.confirm_row(
                observation_id=row["observation_id"],
                geographic_subject=geo,
                temporal_status=temporal,
                behavioral_status=behavioral,
                date_confidence=date_conf,
            )
            print(f"✓ Confirmed {row['observation_id']}")
        else:
            print(f"Skipped {row['observation_id']} — will reappear next run.")


if __name__ == "__main__":
    run()

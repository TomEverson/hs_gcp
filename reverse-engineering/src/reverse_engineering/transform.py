from datetime import datetime

import pandas as pd


def normalize(course: dict) -> dict:
    partner_ids = course.get("partnerIds", [])
    return {
        "course_id": course.get("id", ""),
        "name": course.get("name", ""),
        "slug": course.get("slug", ""),
        "description": (course.get("description") or "")[:500],
        "course_status": course.get("courseStatus", ""),
        "workload": course.get("workload", ""),
        "start_date": course.get("startDate", ""),
        "primary_languages": ", ".join(course.get("primaryLanguages", [])),
        "subtitle_languages": ", ".join(course.get("subtitleLanguages", [])),
        "certificates": ", ".join(course.get("certificates", [])),
        "partner_ids": ", ".join(str(p) for p in partner_ids),
        "partner_count": len(partner_ids),
        "photo_url": course.get("photoUrl", ""),
        "preview_link": course.get("previewLink", ""),
        "is_georestricted": course.get("isGeorestricted", False),
        "extracted_at": datetime.utcnow().isoformat() + "Z",
    }


def build_dataframe(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([normalize(c) for c in raw])
    before = len(df)
    df.drop_duplicates(subset="course_id", inplace=True)
    print(f"Dedup: {before} -> {len(df)} rows")
    return df

#!/usr/bin/env python3
"""Seed articles/posted.json from current WordPress posts + local markdown slugs."""

from __future__ import annotations

import json
import os
from pathlib import Path

import frontmatter
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
BASE = os.getenv("WP_URL", "").replace("/xmlrpc.php", "").rstrip("/")
AUTH = (os.getenv("WP_USER"), os.getenv("WP_PASS"))
MEDIA_INDEX = ROOT / "images" / "uploaded-media.json"
OUT = ROOT / "articles" / "posted.json"


def main() -> None:
    media = {
        row["file"]: row["id"]
        for row in json.loads(MEDIA_INDEX.read_text(encoding="utf-8"))
    }
    r = requests.get(
        f"{BASE}/wp-json/wp/v2/posts",
        params={
            "per_page": 100,
            "status": "draft,publish,pending,private",
            "_fields": "id,slug,featured_media",
        },
        auth=AUTH,
        timeout=60,
    )
    r.raise_for_status()
    by_slug = {p["slug"]: p for p in r.json()}

    rows = []
    for path in sorted((ROOT / "articles").glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta = frontmatter.load(path)
        slug = meta.get("slug") or path.stem
        wp = by_slug.get(slug)
        if not wp:
            continue
        eyecatch = Path(str(meta.get("eyecatch", ""))).name if meta.get("eyecatch") else None
        rows.append(
            {
                "file": path.name,
                "slug": slug,
                "id": wp["id"],
                "featured_media": wp.get("featured_media") or media.get(eyecatch),
            }
        )
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()

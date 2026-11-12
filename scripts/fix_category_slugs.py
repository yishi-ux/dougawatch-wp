#!/usr/bin/env python3
"""Fix WordPress category slugs to English for onsened.com permalinks."""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = os.getenv("WP_URL", "").replace("/xmlrpc.php", "").rstrip("/")
AUTH = (os.getenv("WP_USER"), os.getenv("WP_PASS"))

# name -> desired slug
WANTED = {
    "買い方ガイド": "guide",
    "セール情報": "sale",
    "見放題・月額": "streaming",
    "キャンペーン": "campaign",
}


def list_categories() -> list[dict]:
    r = requests.get(
        f"{BASE}/wp-json/wp/v2/categories",
        params={"per_page": 100},
        auth=AUTH,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def update_slug(cat_id: int, slug: str) -> dict:
    r = requests.post(
        f"{BASE}/wp-json/wp/v2/categories/{cat_id}",
        json={"slug": slug},
        auth=AUTH,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def create_category(name: str, slug: str) -> dict:
    r = requests.post(
        f"{BASE}/wp-json/wp/v2/categories",
        json={"name": name, "slug": slug},
        auth=AUTH,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def main() -> None:
    if not all(AUTH) or not BASE:
        raise SystemExit(".env の WP_URL / WP_USER / WP_PASS が必要です")

    cats = list_categories()
    by_name = {c["name"]: c for c in cats}
    by_slug = {c["slug"]: c for c in cats}

    print("BEFORE:")
    for c in cats:
        print(f"  id={c['id']} name={c['name']!r} slug={c['slug']!r}")

    for name, slug in WANTED.items():
        existing = by_name.get(name)
        if existing:
            if existing["slug"] == slug:
                print(f"OK already {name} -> {slug}")
                continue
            # if target slug already taken by another category, abort
            conflict = by_slug.get(slug)
            if conflict and conflict["id"] != existing["id"]:
                raise SystemExit(
                    f"slug {slug!r} は別カテゴリ id={conflict['id']} name={conflict['name']!r} が使用中"
                )
            updated = update_slug(existing["id"], slug)
            print(f"UPDATED {name}: {existing['slug']!r} -> {updated['slug']!r}")
            by_slug[slug] = updated
        else:
            created = create_category(name, slug)
            print(f"CREATED {name} -> {created['slug']!r} id={created['id']}")
            by_name[name] = created
            by_slug[slug] = created

    print("AFTER:")
    for c in list_categories():
        if c["name"] in WANTED or c["slug"] in WANTED.values():
            print(f"  id={c['id']} name={c['name']!r} slug={c['slug']!r}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Attach local eyecatch images to WordPress posts by slug (no manual linking)."""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path

import frontmatter
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ARTICLES = ROOT / "articles"
IMAGES = ROOT / "images"
MEDIA_INDEX = IMAGES / "uploaded-media.json"


def site_base(wp_url: str) -> str:
    u = wp_url.strip().rstrip("/")
    for suffix in ("/xmlrpc.php", "/wp-json", "/wp-admin"):
        if u.endswith(suffix):
            u = u[: -len(suffix)]
            break
    return u.rstrip("/")


def main() -> None:
    load_dotenv(ROOT / ".env")
    base = site_base(os.getenv("WP_URL", ""))
    auth = (os.getenv("WP_USER"), os.getenv("WP_PASS"))
    session = requests.Session()
    session.auth = auth

    media_index = {}
    if MEDIA_INDEX.exists():
        for row in json.loads(MEDIA_INDEX.read_text(encoding="utf-8")):
            media_index[row["file"]] = row

    # fetch posts by slug
    posts = {}
    page = 1
    while True:
        r = session.get(
            f"{base}/wp-json/wp/v2/posts",
            params={
                "per_page": 100,
                "page": page,
                "status": "draft,publish,pending,private,future",
                "_fields": "id,slug,featured_media",
            },
            timeout=60,
        )
        if r.status_code == 400:
            break
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for p in batch:
            posts[p["slug"]] = p
        if len(batch) < 100:
            break
        page += 1

    for path in sorted(ARTICLES.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        meta = frontmatter.load(path)
        slug = meta.get("slug") or path.stem
        eyecatch = meta.get("eyecatch")
        if not eyecatch:
            print(f"SKIP {path.name} (no eyecatch)")
            continue
        filename = Path(str(eyecatch)).name
        img_path = IMAGES / filename
        if not img_path.exists():
            print(f"MISSING image {filename}")
            continue

        post = posts.get(slug)
        if not post:
            print(f"SKIP {path.name} (post not on WP yet)")
            continue

        # upload if needed
        if filename not in media_index:
            print(f"UPLOAD {filename}")
            mime = mimetypes.guess_type(filename)[0] or "image/jpeg"
            res = session.post(
                f"{base}/wp-json/wp/v2/media",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": mime,
                },
                data=img_path.read_bytes(),
                timeout=120,
            )
            res.raise_for_status()
            info = res.json()
            media_index[filename] = {
                "file": filename,
                "id": info["id"],
                "source_url": info.get("source_url"),
                "link": info.get("link"),
                "mime_type": info.get("mime_type"),
            }
        media_id = int(media_index[filename]["id"])
        if post.get("featured_media") == media_id:
            print(f"OK {slug} already featured_media={media_id}")
            continue

        r = session.post(
            f"{base}/wp-json/wp/v2/posts/{post['id']}",
            json={"featured_media": media_id},
            timeout=60,
        )
        r.raise_for_status()
        print(f"SET {slug} id={post['id']} featured_media={media_id}")

    MEDIA_INDEX.write_text(
        json.dumps(list(media_index.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"SAVED {MEDIA_INDEX}")


if __name__ == "__main__":
    main()

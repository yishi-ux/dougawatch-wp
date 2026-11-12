#!/usr/bin/env python3
"""
追加分をまとめて WordPress へ送る。

使い方（ファイル名の指定は不要）:
  python scripts/push.py              # 未投稿の記事 + 未アップロード画像
  python scripts/push.py --update     # 既存記事もローカル内容で上書き
  python scripts/push.py --dry-run    # 何が送られるかだけ表示
  python scripts/push.py --articles   # 記事だけ
  python scripts/push.py --images     # 画像だけ
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

import frontmatter
import requests
from dotenv import load_dotenv
from wordpress_xmlrpc.methods.posts import EditPost, NewPost

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_DIR = ROOT / "articles"
IMAGES_DIR = ROOT / "images"
MEDIA_INDEX = IMAGES_DIR / "uploaded-media.json"
POSTED_INDEX = ROOT / "articles" / "posted.json"

sys.path.insert(0, str(ROOT / "scripts"))
import wp_post  # noqa: E402


def site_base(wp_url: str) -> str:
    u = wp_url.strip().rstrip("/")
    for suffix in ("/xmlrpc.php", "/wp-json", "/wp-admin"):
        if u.endswith(suffix):
            u = u[: -len(suffix)]
            break
    return u.rstrip("/")


def load_json(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SAVED {path}")


def auth_session() -> tuple[requests.Session, str]:
    load_dotenv(ROOT / ".env")
    wp_url = os.getenv("WP_URL")
    user = os.getenv("WP_USER")
    password = os.getenv("WP_PASS")
    if not wp_url or not user or not password:
        raise SystemExit(".env に WP_URL / WP_USER / WP_PASS を設定してください")
    base = site_base(wp_url)
    s = requests.Session()
    s.auth = (user, password)
    s.headers.update({"Accept": "application/json"})
    return s, base


def fetch_existing_posts(session: requests.Session, base: str) -> dict[str, dict]:
    """slug -> {id, featured_media, status}"""
    by_slug: dict[str, dict] = {}
    page = 1
    while True:
        r = session.get(
            f"{base}/wp-json/wp/v2/posts",
            params={
                "per_page": 100,
                "page": page,
                "status": "draft,publish,pending,private,future",
                "_fields": "id,slug,featured_media,status",
            },
            timeout=60,
        )
        if r.status_code == 400 and "rest_post_invalid_page_number" in r.text:
            break
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for p in batch:
            slug = p.get("slug")
            if slug:
                by_slug[slug] = p
        if len(batch) < 100:
            break
        page += 1
    return by_slug


def article_files() -> list[Path]:
    return sorted(
        p for p in ARTICLES_DIR.glob("*.md") if p.name.lower() != "readme.md"
    )


def image_files() -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    return sorted(p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in exts)


def push_images(session: requests.Session, base: str, *, dry_run: bool) -> dict[str, int]:
    index = load_json(MEDIA_INDEX)
    if not isinstance(index, list):
        index = []
    by_file = {row["file"]: row for row in index if isinstance(row, dict) and "file" in row}
    endpoint = f"{base}/wp-json/wp/v2/media"

    for path in image_files():
        if path.name in by_file:
            print(f"SKIP image {path.name} (already id={by_file[path.name].get('id')})")
            continue
        if dry_run:
            print(f"WOULD upload {path.name}")
            continue
        print(f"UPLOAD {path.name}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        res = session.post(
            endpoint,
            headers={
                "Content-Disposition": f'attachment; filename="{path.name}"',
                "Content-Type": mime,
            },
            data=path.read_bytes(),
            timeout=120,
        )
        if res.status_code >= 400:
            raise RuntimeError(f"{path.name}: HTTP {res.status_code} {res.text[:400]}")
        info = res.json()
        row = {
            "file": path.name,
            "id": info.get("id"),
            "source_url": info.get("source_url"),
            "link": info.get("link"),
            "mime_type": info.get("mime_type"),
        }
        by_file[path.name] = row
        print(f"  OK id={row['id']}")

    merged = list(by_file.values())
    if not dry_run:
        save_json(MEDIA_INDEX, merged)
    return {k: int(v["id"]) for k, v in by_file.items() if v.get("id") is not None}


def load_media_rows() -> dict[str, dict]:
    index = load_json(MEDIA_INDEX)
    if not isinstance(index, list):
        return {}
    return {
        row["file"]: row
        for row in index
        if isinstance(row, dict) and row.get("file")
    }


def resolve_eyecatch(meta: dict, media_rows: dict[str, dict]) -> tuple[int | None, str | None]:
    raw = meta.get("eyecatch")
    if not raw:
        return None, None
    name = Path(str(raw)).name
    row = media_rows.get(name)
    if not row:
        return None, None
    media_id = int(row["id"]) if row.get("id") is not None else None
    url = row.get("source_url")
    return media_id, url


def set_featured_media(session: requests.Session, base: str, post_id: int, media_id: int) -> None:
    r = session.post(
        f"{base}/wp-json/wp/v2/posts/{post_id}",
        json={"featured_media": media_id},
        timeout=60,
    )
    if r.status_code >= 400:
        print(f"  WARN featured_media failed: {r.status_code} {r.text[:200]}")
    else:
        print(f"  featured_media={media_id}")


def push_articles(
    session: requests.Session,
    base: str,
    media_ids: dict[str, int],
    *,
    dry_run: bool,
    update: bool,
) -> None:
    wp_post.load_env()
    affiliates = wp_post.load_affiliates()
    media_rows = load_media_rows()
    # push_images 直後の ID を補完（source_url は uploaded-media.json 側を優先）
    for name, mid in media_ids.items():
        row = dict(media_rows.get(name) or {"file": name})
        row["id"] = mid
        media_rows[name] = row

    try:
        existing = fetch_existing_posts(session, base)
    except Exception as e:
        if dry_run:
            print(f"WARN: could not fetch existing posts ({e})")
            existing = {}
        else:
            raise

    posted = load_json(POSTED_INDEX)
    if not isinstance(posted, list):
        posted = []
    posted_by_slug = {
        row["slug"]: row for row in posted if isinstance(row, dict) and "slug" in row
    }

    client = None if dry_run else wp_post.get_client()

    for path in article_files():
        meta = frontmatter.load(path)
        meta_dict = dict(meta)
        slug = meta.get("slug") or path.stem
        wp_post_info = existing.get(slug)
        local_info = posted_by_slug.get(slug)
        post_id = None
        if wp_post_info:
            post_id = int(wp_post_info["id"])
        elif local_info and local_info.get("id") is not None:
            post_id = int(local_info["id"])

        media_id, eyecatch_url = resolve_eyecatch(meta_dict, media_rows)

        if post_id is not None:
            if not update:
                print(f"SKIP article {path.name} (slug={slug} already on WP; use --update)")
                continue
            if dry_run:
                print(f"WOULD update {path.name} slug={slug} id={post_id} eyecatch={bool(eyecatch_url)}")
                continue
            assert client is not None
            post = wp_post.build_post(path, affiliates, None, eyecatch_url=eyecatch_url)
            client.call(EditPost(post_id, post))
            print(f"UPDATE {path.name} -> id={post_id}")
            if media_id:
                set_featured_media(session, base, post_id, media_id)
            posted_by_slug[slug] = {
                "file": path.name,
                "slug": slug,
                "id": post_id,
                "featured_media": media_id,
            }
            continue

        if dry_run:
            print(f"WOULD post {path.name} slug={slug} eyecatch={bool(eyecatch_url)}")
            continue

        assert client is not None
        post = wp_post.build_post(path, affiliates, None, eyecatch_url=eyecatch_url)
        post_id = int(client.call(NewPost(post)))
        print(f"POST {path.name} -> id={post_id}")
        if media_id:
            set_featured_media(session, base, post_id, media_id)
        posted_by_slug[slug] = {
            "file": path.name,
            "slug": slug,
            "id": post_id,
            "featured_media": media_id,
        }

    if not dry_run:
        save_json(POSTED_INDEX, list(posted_by_slug.values()))


def main() -> None:
    parser = argparse.ArgumentParser(description="未送信の記事・画像を一括アップロード")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update", action="store_true", help="既存記事をローカル内容で上書き")
    parser.add_argument("--articles", action="store_true", help="記事だけ")
    parser.add_argument("--images", action="store_true", help="画像だけ")
    args = parser.parse_args()

    do_articles = args.articles or not args.images
    do_images = args.images or not args.articles
    if not args.articles and not args.images:
        do_articles = do_images = True

    session, base = auth_session()
    media_ids: dict[str, int] = {}

    if do_images:
        print("=== images ===")
        media_ids = push_images(session, base, dry_run=args.dry_run)
    else:
        index = load_json(MEDIA_INDEX)
        if isinstance(index, list):
            media_ids = {
                row["file"]: int(row["id"])
                for row in index
                if isinstance(row, dict) and row.get("file") and row.get("id") is not None
            }

    if do_articles:
        print("=== articles ===")
        push_articles(
            session,
            base,
            media_ids,
            dry_run=args.dry_run,
            update=args.update,
        )

    print("done")


if __name__ == "__main__":
    main()

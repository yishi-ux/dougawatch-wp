#!/usr/bin/env python3
"""Upload local image files to WordPress Media Library via REST API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def site_base(wp_url: str) -> str:
    u = wp_url.strip().rstrip("/")
    for suffix in ("/xmlrpc.php", "/wp-json", "/wp-admin"):
        if u.endswith(suffix):
            u = u[: -len(suffix)]
            break
    return u.rstrip("/")


def upload_one(session: requests.Session, endpoint: str, path: Path) -> dict:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "Content-Disposition": f'attachment; filename="{path.name}"',
        "Content-Type": mime,
    }
    data = path.read_bytes()
    res = session.post(endpoint, headers=headers, data=data, timeout=120)
    if res.status_code >= 400:
        raise RuntimeError(f"{path.name}: HTTP {res.status_code} {res.text[:500]}")
    return res.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="Image files to upload")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    wp_url = os.getenv("WP_URL")
    user = os.getenv("WP_USER")
    password = os.getenv("WP_PASS")
    if not wp_url or not user or not password:
        raise SystemExit("WP_URL / WP_USER / WP_PASS required in .env")

    base = site_base(wp_url)
    endpoint = f"{base}/wp-json/wp/v2/media"
    session = requests.Session()
    session.auth = (user, password)
    session.headers.update({"Accept": "application/json"})

    results = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_absolute():
            cand = (Path.cwd() / path).resolve()
            path = cand if cand.exists() else (ROOT / raw).resolve()
        if not path.exists():
            print(f"MISSING {raw}", file=sys.stderr)
            continue
        print(f"UPLOAD {path.name} -> {endpoint}")
        info = upload_one(session, endpoint, path)
        row = {
            "file": path.name,
            "id": info.get("id"),
            "source_url": info.get("source_url"),
            "link": info.get("link"),
            "mime_type": info.get("mime_type"),
        }
        results.append(row)
        print(json.dumps(row, ensure_ascii=False))

    out = ROOT / "images" / "uploaded-media.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SAVED {out}")


if __name__ == "__main__":
    main()

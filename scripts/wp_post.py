#!/usr/bin/env python3
"""
WordPress 投稿スクリプト（テンプレート共通）。

Markdown（YAML frontmatter）を HTML に変換し、XML-RPC で投稿する。
カテゴリ名・CTA文言は site.yaml（なければ site.example.yaml）を読む。

使い方:
  python scripts/wp_post.py articles/01-sample.md
  python scripts/wp_post.py articles/ --all
  python scripts/wp_post.py articles/01-sample.md --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import frontmatter
import markdown
import yaml
from dotenv import load_dotenv
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))
import site_config  # noqa: E402

CATEGORY_NAMES = site_config.categories()
TAG_NAMES = site_config.tags()
CTA_LABELS = site_config.cta_labels()

CTA_HTML = (
    '<p class="affiliate-cta">'
    '<a href="{url}" rel="nofollow sponsored" target="_blank">{label}</a>'
    "</p>"
)


def load_env() -> None:
    load_dotenv(ROOT / ".env")


def load_affiliates() -> dict[str, str]:
    path = ROOT / "affiliates.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): str(v) for k, v in data.items() if v}


def apply_affiliates(text: str, affiliates: dict[str, str]) -> str:
    for key, url in affiliates.items():
        text = text.replace(f"{{{{{key}}}}}", url)
        label = CTA_LABELS.get(key, "詳しく見る")
        cta = CTA_HTML.format(url=url, label=label)
        text = re.sub(
            rf"<!--\s*CTA:\s*{re.escape(key)}\s*-->",
            cta,
            text,
        )
    # 未置換の CTA コメントは分かりやすい注記に変える
    text = re.sub(
        r"<!--\s*CTA:\s*([A-Z0-9_]+)\s*-->",
        r'<p class="affiliate-cta-missing">[アフィ未設定: \1]</p>',
        text,
    )
    return text


def resolve_categories(meta: dict) -> list[str]:
    if meta.get("categories"):
        return list(meta["categories"])
    raw = meta.get("category")
    if not raw:
        return ["未分類"]
    if isinstance(raw, list):
        keys = raw
    else:
        keys = [raw]
    return [CATEGORY_NAMES.get(str(k), str(k)) for k in keys]


def resolve_tags(meta: dict) -> list[str]:
    raw = meta.get("tags") or []
    if isinstance(raw, str):
        raw = [raw]
    names = []
    for t in raw:
        names.append(TAG_NAMES.get(str(t), str(t)))
    return names


def md_to_html(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=["extra", "sane_lists", "nl2br", "tables"],
    )


def get_client() -> Client:
    url = os.getenv("WP_URL")
    user = os.getenv("WP_USER")
    password = os.getenv("WP_PASS")
    if not url or not user or not password:
        raise SystemExit(
            ".env に WP_URL / WP_USER / WP_PASS を設定してください。"
            " 例: cp .env.example .env"
        )
    return Client(url, user, password)


def prepend_eyecatch(html: str, image_url: str | None, alt: str) -> str:
    """Cocoon は本文先頭画像をアイキャッチに使えるので、先頭へ挿入する。"""
    if not image_url:
        return html
    # 既存の先頭アイキャッチを除去してから付け直す（--update 時の重複防止）
    html = re.sub(
        r'(?is)^\s*<p class="eyecatch">\s*<img[^>]*>\s*</p>\s*',
        "",
        html,
    )
    safe_alt = (
        alt.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    block = (
        f'<p class="eyecatch">'
        f'<img src="{image_url}" alt="{safe_alt}" />'
        f"</p>\n"
    )
    return block + html


def build_post(
    path: Path,
    affiliates: dict[str, str],
    status_override: str | None,
    eyecatch_url: str | None = None,
) -> WordPressPost:
    post_data = frontmatter.load(path)
    body = apply_affiliates(post_data.content, affiliates)
    html = md_to_html(body)
    title = post_data.get("title", path.stem)
    html = prepend_eyecatch(html, eyecatch_url, str(title))

    post = WordPressPost()
    post.title = title
    post.content = html
    post.slug = post_data.get("slug", "")
    post.post_status = status_override or post_data.get("status", "draft")
    post.terms_names = {
        "category": resolve_categories(dict(post_data)),
        "post_tag": resolve_tags(dict(post_data)),
    }
    return post


def iter_targets(path: Path, all_flag: bool) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise SystemExit(f"パスが見つかりません: {path}")
    files = sorted(path.glob("*.md"))
    files = [f for f in files if f.name.lower() != "readme.md"]
    if not all_flag:
        raise SystemExit(
            f"ディレクトリが指定されました。一括投稿するなら --all を付けてください。"
            f" 対象候補: {len(files)} 件"
        )
    return files


def post_file(
    client: Client | None,
    path: Path,
    affiliates: dict[str, str],
    *,
    dry_run: bool,
    status_override: str | None,
) -> None:
    post = build_post(path, affiliates, status_override)
    cats = post.terms_names.get("category", [])
    tags = post.terms_names.get("post_tag", [])
    print(f"--- {path.name}")
    print(f"  title : {post.title}")
    print(f"  slug  : {post.slug}")
    print(f"  status: {post.post_status}")
    print(f"  cats  : {cats}")
    print(f"  tags  : {tags}")
    if dry_run:
        print("  dry-run: 投稿しません")
        return
    assert client is not None
    post_id = client.call(NewPost(post))
    print(f"  OK id={post_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="onsened.com WordPress 投稿")
    parser.add_argument("path", help="Markdown ファイル、または articles/ ディレクトリ")
    parser.add_argument("--all", action="store_true", help="ディレクトリ内の md を一括投稿")
    parser.add_argument("--dry-run", action="store_true", help="変換結果だけ表示して投稿しない")
    parser.add_argument(
        "--status",
        choices=["draft", "publish", "pending"],
        help="frontmatter の status を上書き",
    )
    args = parser.parse_args()

    load_env()
    affiliates = load_affiliates()
    if not affiliates:
        print("注意: affiliates.yaml が無い、または空です。CTA は未設定のまま投稿されます。")

    target = Path(args.path)
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
        if not target.exists():
            target = (ROOT / args.path).resolve()

    files = iter_targets(target, args.all)
    client = None if args.dry_run else get_client()

    ok = 0
    for f in files:
        try:
            post_file(
                client,
                f,
                affiliates,
                dry_run=args.dry_run,
                status_override=args.status,
            )
            ok += 1
        except Exception as e:
            print(f"  ERROR: {e}")
    print(f"完了: {ok}/{len(files)}")


if __name__ == "__main__":
    main()

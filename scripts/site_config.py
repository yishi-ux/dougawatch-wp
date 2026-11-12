"""Load per-site settings from site.yaml (fallback to site.example.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CATEGORIES = {
    "guide": "買い方ガイド",
    "sale": "セール情報",
    "streaming": "見放題・月額",
    "campaign": "キャンペーン",
}

DEFAULT_TAGS = {
    "coupon": "クーポン",
    "first-time": "初回特典",
}

DEFAULT_CTA = {
    "AFFILIATE_MAIN": "公式サイトで見る",
    "AFFILIATE_SALE": "セールを見る",
}


def load_site_config() -> dict:
    for name in ("site.yaml", "site.example.yaml"):
        path = ROOT / name
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                return data
    return {}


def categories() -> dict[str, str]:
    cfg = load_site_config()
    raw = cfg.get("categories") or {}
    return {str(k): str(v) for k, v in {**DEFAULT_CATEGORIES, **raw}.items()}


def tags() -> dict[str, str]:
    cfg = load_site_config()
    raw = cfg.get("tags") or {}
    return {str(k): str(v) for k, v in {**DEFAULT_TAGS, **raw}.items()}


def cta_labels() -> dict[str, str]:
    cfg = load_site_config()
    raw = cfg.get("cta_labels") or {}
    return {str(k): str(v) for k, v in {**DEFAULT_CTA, **raw}.items()}

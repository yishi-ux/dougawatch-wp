# 記事

YAML frontmatter 付き Markdown を置く。

```yaml
---
title: "記事タイトル"
slug: sample-slug
category: guide
tags: [coupon]
status: draft
eyecatch: ../images/eyecatch-sample.jpg
affiliate_slots:
  - AFFILIATE_MAIN
---
```

本文中の CTA:

```html
<!-- CTA: AFFILIATE_MAIN -->
```

ひな形: `00-sample.md`  
投稿: `python scripts/push.py`

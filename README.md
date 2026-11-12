# dougawatch.com

MGS動画アフィリエイトの **買い方・セール案内** サイト。  
ベース: [wp-affiliate-template](https://github.com/yishi-ux/wp-affiliate-template)

## いまの状態

- **対象**: dougawatch.com
- **ASP**: MGS動画
- **フェーズ**: Step 1（案件・キーワード設計）
- **前サイト**: onsened.com（公開済み・観測中）

## セットアップ

```bash
cd /home/yishi/development/dougawatch
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp affiliates.example.yaml affiliates.yaml
cp site.example.yaml site.yaml
```

`.env` / `affiliates.yaml` / `site.yaml` を編集してから記事作成・`python scripts/push.py`。

## 次やること

1. キーワード 10〜15本（`keywords.md`）
2. WordPress 基盤（パーマリンク・カテゴリ・サイト名）
3. 初期記事 → push → Search Console

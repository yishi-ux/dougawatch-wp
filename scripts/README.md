# スクリプト

| ファイル | 用途 |
|---|---|
| `push.py` | 未投稿記事・未アップロード画像を一括送信。`--update` で既存上書き |
| `wp_post.py` | Markdown 1本投稿 |
| `wp_upload_media.py` | 画像アップロード |
| `attach_eyecatches.py` | 既存投稿へアイキャッチ紐付け |
| `site_config.py` | `site.yaml` 読み込み |
| `fix_category_slugs.py` | カテゴリスラッグを英語化（必要なら中身を編集） |

```bash
python scripts/push.py
python scripts/push.py --update
python scripts/push.py --dry-run
```

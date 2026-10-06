# 🍄 Hatena Blog Photo Gallery

はてなブログの各カテゴリごとの画像を自動収集し、GitHub Pages上にギャラリーページを生成します。

- Python + GitHub Actions で毎晩自動更新
- カテゴリ名ごとに画像をタイル表示
- 完全無料運用

## ローカル管理画面（ブログ管理者専用）

Windowsでは `admin/start_admin.bat` をダブルクリックすると、標準ライブラリだけで
`http://127.0.0.1:8765/` に「きのこブログ管理室」が起動します。公開サイトには生成・配布
されません。PR作成には別途 `gh auth login` が必要です。変更はメモリ上の「変更予定」として
保持され、検証後に一時git worktreeからbranch・commit・push・PRを作成します。

## Admin Console v2: Knowledge Expansion

Work 等が生成した batch は local-only の `admin/inbox/<batch-id>/` に、`batch-manifest.json`、`candidate-delta.json`、`source-snapshots.jsonl` の3ファイルで配置します。管理画面は hash・provenance・既存 Phase 4C.9 overlay contract を fail-closed に検証し、候補ごとに人間が「採用 / 保留 / 未決」を明示します。レビュー状態は `admin/local-state/knowledge/` のみに atomic 保存され、validator や AI が採用を自動設定することはありません。

未決がなく採用が1件以上あり、batch base SHA が fresh `origin/main` と一致する場合だけ、採用候補を一時 worktree で overlay audit package に変換し、production JSON を既存 contract から再構築して PR を作成できます。保留候補は production artifact に入りません。管理画面は PR 作成までで、自動 merge / deploy は行いません。

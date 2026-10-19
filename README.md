# 🍄 Hatena Blog Photo Gallery

はてなブログの各カテゴリごとの画像を自動収集し、GitHub Pages上にギャラリーページを生成します。

- Python + GitHub Actions で毎晩自動更新
- カテゴリ名ごとに画像をタイル表示
- 完全無料運用

## ローカル管理画面（ブログ管理者専用）

Windowsでは `admin/start_admin.bat` をダブルクリックすると、標準ライブラリだけで
`http://127.0.0.1:8765/` に「きのこブログ管理室」が起動します。公開サイトには生成・配布
されません。GitHub CLIを一度インストールし、`gh auth login` と
`gh auth setup-git` を初回だけ実行すると、以降は認証済み環境からPRを作成できます。
CLIをあとからインストールした場合はWindows標準インストール先も検出します。
管理室でのBest Shot・通知・研究室の変更予定は操作のたびに
`admin/local-state/admin-draft.json` へ原子的に保存され、再起動後に自動復元します。
保存先はGitの追跡対象外で、サイト・外部サーバー・GitHubには自動送信しません。
保存ファイルが破損した場合や、未公開の編集を保持したままmainの元データが
変わった場合は、下書きを削除・上書きせず起動を停止します。
元データに戻す前にファイルをバックアップして差分を確認してください。
管理室のローカル下書きは、データの検証後に一時git worktreeから
branch・commit・push・PRを作成します。自動マージ・公開は行いません。

## Admin Console v2: Knowledge Expansion

Work 等が生成した batch は local-only の `admin/inbox/<batch-id>/` に、`batch-manifest.json`、`candidate-delta.json`、`source-snapshots.jsonl` の3ファイルで配置します。管理画面は hash・provenance・既存 Phase 4C.9 overlay contract を fail-closed に検証し、候補ごとに人間が「採用 / 保留 / 未決」を明示します。レビュー状態は `admin/local-state/knowledge/` のみに atomic 保存され、validator や AI が採用を自動設定することはありません。

未決がなく採用が1件以上あり、batch base SHA が fresh `origin/main` と一致する場合だけ、採用候補を一時 worktree で overlay audit package に変換し、production JSON を既存 contract から再構築して PR を作成できます。保留候補は production artifact に入りません。管理画面は PR 作成までで、自動 merge / deploy は行いません。

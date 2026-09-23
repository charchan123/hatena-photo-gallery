# Phase 1 handoff

## 現在のブランチ

`codex/phase1-complete`

GitHub PR #1 の head `codex/article` を開始点とし、PR #2
"Prevent empty gallery deployments — require non-empty articles/images and add tests"
の fail-safe 修正だけを上乗せした統合ブランチ。新しい PR は `main` を base、
`codex/phase1-complete` を head とし、PR #1 / PR #2 の両方を置き換える。
作業用コピーでは PR #1 head が当初 `work` というローカル名で checkout
され、remote ref は提供されていなかった。

## ベース commit SHA

`efb2e0935760d15b0258c14c85811dd36e283c5b`

開始時のリポジトリコピーには `main` および `origin/main` ref がなかったため、開始時 HEAD（`work`）をベースとした。

## Phase 1 で変更したファイル

- `.gitignore`
- `main.py`
- `requirements-dev.txt`
- `tests/test_article_extraction.py`
- `tests/fixtures/article_body.html`
- `tests/fixtures/legacy_full_page.html`
- `AUDIT_PHASE1.md`
- `HATENA_CHANGES.md`
- `HANDOFF.md`

`articles/article1.html` / `articles/article2.html`、workflow、output、現行 CSS/JS/LightGallery 資産は変更していない。

## 完了事項

- API が今回保存した article パスを返し、通常ビルドはそのパスだけを抽出対象にするよう変更。
- `fetch_images(article_files)` を fixture から独立して呼び出せるように変更。
- API credential なしで module import / fixture test を可能にし、API アクセス時は引き続き明示エラーとするように変更。
- 正常本文、同名連続画像、旧 full-page 併存、正常キノコ維持、既知誤ページ6名の非生成を自動テスト。
- アーキテクチャ、EXIF、旧 CSS/JS、iframe、fullscreen、Actions/deploy の監査と次 Phase 提案を文書化。
- API が記事ファイルを1件も返さない場合、または記事から画像エントリを1件も
  抽出できない場合は `RuntimeError` で生成を停止し、空の output を deploy しない。
- Hatena API の mock による保存ファイル一覧、2つの空データ停止、非空データの従来処理を
  自動テストで確認。

## テスト結果

- `python -m py_compile main.py tests/test_article_extraction.py`: 成功。既存の JS regex を含む Python 文字列に `SyntaxWarning: invalid escape sequence '\/'` あり。
- `python -m pytest -q`: 8 passed。
- `git diff --check`: 成功。

Secrets を捏造せず、Hatena API 実接続とフルビルドは実施していない。

## 未完了事項（意図的に Phase 1 範囲外）

- EXIF cache の Actions 間永続化。
- CSS/JS 外部化と旧 `gallery.css` / `gallery.js` 整理。
- iframe 実コンテンツ高さ監視、親側 origin/source 検証。
- LightGallery/fullscreen/親通知の重複経路整理。
- 画像メタデータ/manifest、差分解析と差分生成。
- JST 0:00 schedule と変更なし時の deploy skip。

## 既知の問題

- `cache/exif-cache.json` は tracked でなく Actions cache もないため、clean runner ごとに再取得になる。
- 共通 CSS/JS がページごとに大量埋め込みされる。ルート/output の `gallery.*` は現行機能と一致しない。
- iframe 高さ計測は親 iframe 高さと循環し、縮まない可能性がある。
- close/fullscreen/`lgClosed` に複数経路がある。
- `SCRIPT_TAG` 内の重複 `highlight` 宣言に見える箇所と Python SyntaxWarning は、現行挙動を不用意に変えないため未修正。

## 本番反映

**未反映**。`main` の変更、`gh-pages` の変更、GitHub Actions 実行、GitHub Pages deploy はいずれも行っていない。Hatena 管理画面も変更していない。

## Phase 2 で最初に行うこと

現行生成 HTML のスナップショットとブラウザテストを先に固定し、その後 `actions/cache` による EXIF cache 永続化を staging/手動ビルドで検証する。デプロイはしない。次に CSS/JS を挙動不変で外部化する。

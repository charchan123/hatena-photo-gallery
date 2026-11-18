# PR137 CPU / OPTIONS オフライン監査

基準HEAD：`582a6c19e136fe5f7f6b2c2448cb0f63f14d1235`。
開始main：`b913ad7b07f689f14f5c8dcecea11b7c99363827`。
開始gh-pages：`3549e4ea9fa5619fe6eb53f7c5716d675250ce4f`。

Cloudflareアカウント接続・設定変更・token発行・migration・deploy・既存D1再seedは0件。GitHubの既存PR137ブランチだけを更新し、Draft・未マージを維持する。

## CPU（Nodeローカル、Cloudflare実測ではない）

詳細・生標本：[local-cpu.json](local-cpu.json)。比較は基準HEADの関数をgit showで読み、同じin-memory SQLiteで実行。100要求×7標本、実行順を交互にしたprocess CPUの中央値。

| 項目 | 従来 | 最適化後 |
|---|---:|---:|
| 通常照合のCPU/要求 | 2.13228ms | 0.18148ms |
| 削減率 | — | 91.49% |
| 固定SHA/通常要求 | 67 | 0 |
| D1全件SELECT/要求 | 3 | 3 |

初回は67 SHA・3 SELECTを維持。初回ローカルprocess CPUは13.955ms、20新checkerの総CPUは47.501ms。初回負荷を解消したともFree 10msを達成したとも報告しない。JWT・実D1・ネットワークを含むCloudflare実測は別承認で必要。

## OPTIONS

[設計と一次資料](../../docs/research-comments-cpu-options.md)参照。過去の実403は[live-history.json](live-history.json)に保持し、元監査のSHAも記録。Worker直接試験はOrigin＋ACR-Method/Headers付き204期待を維持。Access外周の否定試験、同一originブラウザ機能試験、localhost Python Service Auth機能試験を別にする。期待値の単純な403への変更・Bypass・CORS緩和は行わない。

## 実行済みローカル検証

- Python全件：1132 passed、skipなし。初回は1099 passed/33 setup errors（OUTPUT_INTEGRITY_ERROR）。失敗対象の独立再実行34 passed、全件再実行1132 passed。コード/テスト緩和なし。全件間の生成物依存の可能性は未確定で、CIのクリーン環境でも全件結果を確認する。
- Nodeコメント/API/Access/D1：30 passed、fail/skipなし。
- Node既存表示・スター・iframe等：86 passed、fail/skipなし。
- Pythonコメント関連：41 passed。
- migrationオフライン再生成：差分0。新規in-memory DBだけでmigration試験。remote migration/既存DB再seedなし。
- 固定版Wrangler4.151.3 dry-run：成功、認証情報を渡さずbundleのみ。生成物はGit対象外。
- [保護データ比較](protection.json)：写真933、Best17、NEW14、研究室66、退役7、master141、sources419、WebP7。registry pendingなし、本番enabled=false。main保護ファイル・公開データを比較し不変。
- ローカルChromium：実行基盤にバイナリがなく、配布ZIPダウンロードも破損で失敗。成功扱いしない。GitHub ActionsのLinux/Windows実ブラウザ試験で検証する。

最終HEADのCI実行URL・各job/重要stepの結果は、完了後にPR137の監査コメントへ追記する。このファイル自身の更新で検証対象HEADを循環させない。

## 保護

`runtime-hashes.json` は意図して変えた2 runtimeファイルのバイトを固定。他の元runtimeの固定SHA比較は維持。変更する実装はstagingだけで、共通Worker・公開JS・管理室の実装・migration・registry・manifest・画像・トップ・同期/削除保護を変更していない。

改変試験は固定bundle/manifest、warm後のmetadata/case/alias、JWT、提供されたAccess snapshotを対象とする。外周設定の現在状態はオフラインで読めないため、実環境の保護状態を再実証したという主張はしない。

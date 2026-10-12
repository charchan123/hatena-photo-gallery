# Phase 2b：同期の例外案件を安全に処理する

## 結論と範囲

対応範囲を限定した **PARTIAL**。単一の既存写真への人間による名前修正は、管理画面の提案・根拠保存・実生成プレビュー・明示承認・独立Draft PR・翌日の再適用まで接続しました。通常の高信頼新規写真は自動追加のままです。

URL変更、削除、ギャラリー未収録の未分類画像追加、保護参照のある写真変更、重複URLの移行、適用済み修正の再変更は未対応です。各操作を無条件に許可するボタンや汎用の例外allow-listは設けません。

## 開始状態と調査

- main: `8d8c1b87427ea73e28313e4e586a87a968291ea1`
- tree: `d9c8ae6c8bb747f57b6bd202122a37ec2e51c721`
- 公開比較元: `e462f7ef362dc94400f73e1799771033f7c503b2`
- 開始時Actions: `38207816501` SUCCESS。906写真、Best Shot3件、研究室67件、退役7枚。
- 新規独立ブランチ: `phase2b-safe-sync-exceptions-2026-10-12`
- 未完成 `phase2b-sync-exception-request-2026-10-12` のファイルは読んだだけで、取り込みませんでした。監査申請のみで生成へ接続されていなかったため、別の適用設計を実装しました。

## 設計

元のPhase 3Cの抽出・検証はそのまま実施し、その後の独立したname projectionで1つのproduction entryのaltのみを変更します。portalを再構築し、生成する全一覧の名前を一致させます。変更前の分類根拠・detected label・shadow gallery nameは保持し、名称競合を検出器の高信頼判定へ偽装しません。

個別マニフェストの対象はAtom記事IDハッシュ、URLハッシュ、既存observation ID、元分類根拠fingerprint、旧名、新名、公開snapshot SHA-256、承認日時、メモのハッシュです。スキーマ・ファイル名・内容ハッシュ・重複・一意性・保護参照・既存taxonomyのcanonical nameを厳密に検証します。

初回はsnapshot完全一致を要求。適用済み台帳は公開snapshotのhash-only情報として保存し、毎回不変マニフェストと照合。翌日も同じ元画像・分類根拠なら表示名修正を維持します。元根拠が変わったら停止。対象外記事の順番や本文更新だけでは写真IDを変更しません。

`reconcile_ids`、`validate_references`、`compare_inventory`、`inventory`、Hatena API取得、Phase 3C cutover validatorは開始mainとのAST比較で完全一致。既存の安全ゲートを一般的に緩めていません（`unchanged-contracts.json`）。

## 管理画面とPR経路

公開状態・ライブ公開記事のレビュー、検索・ページング・保留・確認済み・監査保存を維持。健全な既存写真も検索できる「既存の公開写真（名前修正）」を追加。旧名・新名・対象ID・参照への影響・実生成結果をプレビューし、旧名と新名の再入力で承認します。

新しいPR経路は既存Best Shot/知識PR経路のallow-listを拡張せず、fresh main worktreeで1マニフェストだけをstage。実API GETを使う本番生成、全pytest・全JSテスト・compileall・diff-check、最終公開/ライブ鮮度再確認を行ってからDraft PRを作成します。認証情報・下書き本文・根拠メモ全文はPR/公開物へ出力しません。

local Host/origin制限・CSRF・strict body入力・任意URL/path拒否を既存サーバー経由で維持。承認後の再取得・判断変更・サーバー再起動では再プレビューを要求します。

## 検証

- Python: 771 passed / 771 collected。
- JavaScript: 43 passed。
- 個別移行/管理画面/通常自動更新のfocused tests: 65ケース（内訳は全テスト収集結果）。
- compileall、JavaScript syntax、workflow YAML parse、diff-check成功。
- 実生成fixtureで：名前変更を全出力へ反映、既存ID/URL/対象外名維持、翌日再適用、通常自動追加、旧サイト完全保持、stale/tamper/重複/参照保護/無承認変更の拒否。
- Chromium 1440：名前提案→実生成プレビュー→旧新名再入力の承認成功。既存6タブ表示、console errorなし、横overflowなし（`browser-validation.json`）。例外操作にはfixture APIを使用。CDN画像通信はブロックし、ブラウザー上で実写真を変更承認していません。
- 管理画面のGitHub PR書き込み操作はunitテストで検証。ブラウザーではGitHub資格情報がないため実操作しませんでした。実運用はWindowsで最新main＋gh認証＋ローカルHatena認証を設定して行います。

実APIの読み取り専用事前検証はPR専用Actionsで実施予定。完了後に結果とURLを追記し、一時workflowを最終差分から除去します。実APIでの実写真名変更は人間の写真承認がないため実施しません。

## 公開と保護

この開発PRには写真の変更承認マニフェストを含めません。マージしても906枚の名前・URL・IDは変わりません。固定retirement、Best Shot、研究室同定データ、科学的知識・出典・provenance・Phase 4C.9、Hatena CSS/footer、iframe、poison interaction、トップ表示を編集しません。

日次時刻・push/manual trigger・公開処理は変更なし。公開は従来のfail-closed成功後のみ。個別移行失敗時は旧公開サイトを保持します。

使い方と制限の詳細：`docs/ARTICLE_PHOTO_SYNC_EXCEPTIONS.md`。

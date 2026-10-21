# Windows管理室 Draft PR作成の恒久修正（2026-10-21）

## 開始状態と途中成果のレビュー

- main：`262f2a98a970b82b608db51b8051ee23001e7acb`
- gh-pages：`73afab87f1f60317033f763fd4d8ec692b273e4b`
- 既存の未完成ブランチ：`fix/admin-pr-draft-ci-validation-20261021`
- 引継ぎHEAD：`2d8425d48999e65b2c98c2968eacc1e822fce295`
- 独立取得した保護基準：写真933／Best Shot17／NEW!14／研究室66ケース／公開111記事・980画像。

既存5ファイルの差分を取得してレビューし、ローカル全pytestの撤去、Draft指定、元データ照合、エラー詳細、成功URLの返却、JSTの固定オフセット化を再利用した。最初から作り直していない。既存ブランチに今回の追補コミットを積み、新規の独立Draft PRにする。

元のコードは管理室のPR作成時に `python -m pytest -q` を呼び、環境のPythonにpytestがなければ失敗し、あればOS依存・テスト失敗でもPR作成を止めていた。撮影日のJST判定もWindowsに同梱されないIANAデータを要求していた。途中成果だけでは、失敗理由が確認ダイアログの裏に隠れる、起動コードの古さを検出しない、PR作成成功後の表示が上書きされる、古いPR writerテストがpytest呼出を前提とする問題が残っていた。

## 最終の作成手順

1. サーバーの編集ロック内でドメインvalidatorを実行する。
2. `DraftStore.verify_saved()` が、保存済み下書きのschema・元データhash・全3ファイルの内容と変更予定を**読み取り専用**で照合する。欠落・破損・別内容なら停止。PR作成のために下書きを再保存・削除せず、失敗時にもバイト列を維持する。
3. GitHub認証と管理JSONの厳密allow-list、入力検証の完了を確認する。
4. `git fetch origin main` 後、実行中HEADが最新mainのSHAと完全一致することを確認する。古いコードの場合は停止し、下書きのバックアップ・手動照合・更新・再起動を案内する。コード更新だけでも黙って最新mainへ載せ替えない。
5. 取得したmainの**固定SHA**から隔離worktreeを作り、Best Shot・NEW!・研究同定の元JSON全3ファイルを確認する。JSONの整形・OS改行だけは無視するが、型・配列順序・内容は厳密に比較する（`true`と`1`も区別）。重複key・非有限数も拒否する。
6. 全元データの一致後、変更があるJSONだけをUTF-8で書き出す。ステージ対象と差分を検証し、コミットする。
7. push直前にもremote mainのSHAを確認する。作成中にmainが進んでいれば停止し、自動rebaseしない。
8. 専用ブランチだけを通常pushし、`gh pr create --draft --body-file ...` でDraftを作る。本文はUTF-8ファイルなのでWindowsの文字コード・改行・引数長制限に左右されない。
9. 正規のGitHub PR URLを確認して返す。隔離worktreeの後片付け失敗で成功URLや元のエラーを隠さない。

このBest Shot／NEW!／研究同定のPR作成経路ではローカルPython・pytest・compileallを呼ばない。図鑑情報拡充や個別削除・採用等の別の承認経路は変更していない。

## CIへ移した検証と安全停止

既存 `Validate Admin Changes` が全Python・JavaScript・compileallと、最新はてなAPIの保護参照・非公開生成プレビューを検証する。`--safe-deletions --deletion-preview --output cache/never-published-admin-validation`、保護参照数、`history_persisted is False`、出力非公開のassertを維持した。workflowのread-only権限や失敗時停止条件は緩めていない。

PRが作成されてもCIはpendingであり、ローカルテスト合格を装わない。CI失敗時はDraftのまま修正・再検証し、CI成功だけでready・merge・deployへ進む処理はない。管理者の明示承認が別途必要。

新規read-only workflowはUbuntuと**実Windows runner**の両方で、隔離した実Git、下書き復元、UTF-8・空白付きパス、JST日付、localhost実管理室を検証する。各PR最終HEADを明示checkoutし、GitHubへの実PR作成は境界で隔離する。本番データや本番スターへ書き込む試験はない。

## 表示と失敗時の対応

- 確認ダイアログ内にrole=alertのエラー欄を置き、原因と対処方法へフォーカスする。背景の通知だけに頼らない。
- 処理中は実行・キャンセルとEscapeをロックし、二重送信を防止する。失敗後は入力と下書きを維持し、再試行できる。
- fetch・保存・commit・push・PR作成のどの段階かを日本語で示す。Gitのuser.name/email、空き容量・権限、gh auth login、ネットワーク等の確認先を示す。
- push後のPR作成が失敗した場合は、保存済みブランチ名と既存PRを確認してから再試行するよう案内する。
- 成功時はクリック可能なPR URLと「CI成功・管理者の明示承認が必要」を表示する。成功後の状態再取得が失敗してもURLを消さない。

[認証失敗](auth-error.webp)／[main不一致](stale-error.webp)／[保存確認失敗](save-error.webp)／[入力検証失敗](validation-error.webp)／[Draft PR成功](draft-pr-success.webp)。実際の管理室を合成データとlocalhostでレンダリングした画面。URLも架空で、本番写真の変更予定ではない。

## Windowsのタイムゾーン

`best_shot_ui._manual_date()` は `datetime.now(timezone(timedelta(hours=9)))` を使用する。標準ライブラリだけでJSTの今日を求め、OSのAsia/Tokyoデータやtzdataパッケージを要求しない。UTC日付が前日の15:30でもJSTの当日を受理し、翌日を拒否する境界をテストした。既存の厳密形式・実在日・うるう年・未来日拒否は維持している。

## テスト・保護証跡

専用Pythonは実Git・API・下書き復元・手動日付を含む66件、localhostの実画面30項目、既存Best Shotピッカー287項目、JavaScript13テストファイルの全回帰・構文検証を実施。画面には日本語フォントを用いた。

ローカル全件の初回は既存の同期フィクスチャ33件でOUTPUT_INTEGRITY_ERRORとなった。失敗を合格扱いにはせず、元のguardを変えずに対象単独20件・同期一式48件・前段を含む169件を再実行して合格した。診断を付けた全件再実行も1065件が合格した。診断コードを付けない最終変更後の全件再実行も**1070件PASS（115.00秒）**となった。Windowsを含む最終HEAD CI各URL・結果・最終SHA・PR URLはPR本文へ記録する。安全判定の緩和・テスト削除はしていない。

[独立保護照合](protection.json)に全data・sync-migrationsのSHA-256を保存。Best17件の選択ID・写真ID・順序・コメント・年間指定・手動日付、NEW!14件、研究室、master・sources・facets、退役・削除承認履歴の全バイトがmainと同一。公開portalも933写真の基準hashを照合した。日次同期・削除判定・スター・本番公開workflowには変更がない。

## 変更ファイルと理由

- `admin/git_workflow.py`：途中成果を継続し、固定main照合・厳密JSON・Draft作成・段階別エラー・UTF-8・後片付けを補強。
- `admin/server.py`：編集ロック・保存済み下書きの読み取り照合・エラー応答。
- `admin/draft_store.py`：新しい読み取り専用verify_savedだけを追加。既存save/recoverの動作は不変。
- `admin/static/admin.js`・`admin.css`：モーダル内エラー、操作ロック、成功URLリンク。
- `best_shot_ui.py`：途中成果の標準ライブラリJST修正を維持。
- `README.md`：Windowsの実運用・更新・下書き保護手順。
- `tests/test_admin_pr_workflow.py`・`test_admin_pr_api.py`：実Gitと実HTTPによる新回帰。
- `tests/test_manual_capture_date.py`：pytest呼出を前提にした古いmockを、新契約の照合・コミット・Draftペイロード検証へ更新。
- `tests/browser/admin_pr_server.py`・`admin_pr.cjs`：合成データのみの実管理室試験。
- `.github/workflows/admin-pr-regressions.yml`：Ubuntu／Windowsでの読取専用回帰。
- 本audit：レビュー・保護hash・画面・実測結果。

## マージ前の注意と停止状態

Draft PRのまま停止する。main直接push・force push・自動merge・本番再生成・GitHub Pages公開・本番写真・記事・スターへの変更・ローカル下書き削除は実行しない。

マージ後もWindows PCのコードは自動更新されない。既存下書きをバックアップし、最新mainと手動照合してから管理室を更新する。古いmainからの作成は今回の新しい安全ゲートで停止する。GitHub側へブランチだけ送信でき、PR作成が失敗した場合は、重複作成前にそのブランチと既存PRを確認する。

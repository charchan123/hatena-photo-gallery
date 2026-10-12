# 記事・写真の同期管理（Phase 2・安全な限定実装）

このPRは **PARTIAL** です。読み取り、公開写真レビュー、ローカル判断の監査保存、
高信頼の新規写真の追加承認→実生成検証→専用Draft PRを実装しました。
既存写真の名変更・URL置換・削除、未分類写真の手動分類を公開へ適用する機能は、
保護契約を弱めずに保証できないため「要個別移行」として保留します。
食毒・分類・出典・知識overlayを編集する機能ではありません。

## 開始状態と重要な挙動変更

- main: `20b1a09cb8b9d7b582d02896f6d89171b3048ba4`
- tree: `a79eccbbf6e6e1e50a0bc97373a48c259ddcec9e`
- 公開比較元: `ac1038aafb8dbedc8dc28a0e1264ef2fb500055c`
- 公開スナップショットの原本を編集していません。
- **新規ギャラリー写真は、既存Phase 3Cの高信頼判定に加え、人間承認を必要とします。**
  未承認写真がある実行は公開候補を置き換えず停止します。高信頼だから無承認で追加、とはしません。
- 現在の906枚、通常の既存記事更新、日次09:00 JST相当のtriggerは維持します。
- 新規記事・写真の再取得、未分類を人間が保留すること、公開することは別の操作です。
- このPRのレビュー記録に実写真の追加承認は含まれません。初期manifestは空です。

## Windowsでの使用

1. Git、Python 3.10以降、Node.js、GitHub CLIを準備します。
2. PRをユーザーが手動マージした後、ローカルcheckoutを最新mainへ更新します。
3. `python -m pip install -r requirements-dev.txt` を実行します。
4. 公開データだけ見る場合は、はてなAPI認証は不要です。`git fetch origin main gh-pages` 後、
   `admin\start_admin.bat` または `python -m admin.server` を起動します。
5. `http://127.0.0.1:8765/` の「記事・写真の同期管理」を開きます。
6. 実写真の新規レビューを利用する場合、**同じローカルプロセス**の環境へ
   `HATENA_USER`、`HATENA_BLOG_ID`、`HATENA_API_KEY` を安全に設定してから再起動します。
   ブラウザーへキーを入力する欄はありません。GitHub Actions Secretsはローカルへ自動配布されません。
   キーをGit、レビューコメント、スクリーンショット、共有ログへ保存しないでください。
7. Draft PR作成には `gh auth login` 済みのGitHub CLIが必要です。
   既存CLI認証方式を利用し、実行checkoutはcleanかつfresh origin/mainと一致する必要があります。

## 画面と判断

- 前回正常な公開状態は、単一のimmutable `origin/gh-pages` commitから読み取ります。
  `output/`の古いローカル生成物を比較元にしません。
- 成功日時は日本時間。UNKNOWN、未取得、実数0を区別します。
- 最新Actionsが失敗していても、最後に成功した公開状態を表示します。
  gh認証があれば読み取り専用で失敗時のsanitized reportから原因コードを取得します。
  認証・artifactがない場合は未取得と表示し、成功扱いにしません。
- 552件はすべて従来の分類保留として表示されます。新規問題552件とは表示しません。
- 名前・記事・日付・分類状態で検索し、カテゴリを選択、30件ずつページングします。
- サムネイルは公開portalまたはstrict GETで取得した公開記事のURLを使用。
  snapshotのURLハッシュからURLを復元・推測しません。安全な画像・記事リンクがない候補の採用は無効です。
- ブラウザーへ返す画像URLは既知のHTTPS Hatena CDN、記事リンクはブログのHTTPS originだけ。
  EXIFがない写真には撮影日を推測しません。
- GET一覧のために全写真を再ダウンロードしません。取得済みEXIFは利用し、未知は情報なし。
  実生成プレビューでは通常の生成・EXIFフローと全保護ゲートを実行します。

|操作|この版での結果|
|---|---|
|採用（追加）|新規・高信頼・accepted_subject・一意な対応の写真のみ。実生成検証後、固定manifestのDraft PRへ|
|「不明」のまま採用|キノコという被写体が確認済みで同じ高信頼条件を満たす新規写真のみ|
|保留／確認不要・現状維持／判断取消|ローカル監査状態へ保存。公開データは変更しない|
|名前修正の提案|人間の入力をローカルに保存。「要個別移行」で公開へ適用しない|
|対象外、URL確認、削除提案|この版では適用不可。既存写真の削除・置換の承認は拒否。個別移行が必要|
|未分類・曖昧な写真の名前を付けて公開|未対応。採用ボタン無効。既存分類validatorを迂回しない|

「確認不要」は、fail-closedを解除する例外ではありません。未承認新規写真が存在する場合、
一部だけ採用しても全体の実生成は停止します。未承認・保留項目をプレビューで確認してください。
同一URLの重複番号は記事IDハッシュ＋URLハッシュのscopeです。記事取得順やarticle_Nを使いません。
DOMとgalleryの同一URL件数が異なる場合、新規写真の対応を推測して承認しません。
retired記事が再公開された場合も、通常のretirementゲートが拒否します。

## 保存と鮮度

- ローカル状態: `admin/local-state/sync/review.json`（既存ignore対象）。
  atomic replace、作成時owner-only権限、symlink拒否。判断履歴を残します。
- candidate ID、旧snapshot checksum、新inventory hash、記事ID hash、URL hash、
  article内重複番号、分類根拠fingerprint、判断、日時、コメント、適用状態を保存。
- 再読込・取消可能。datasetが変われば前の判断は古い判断として無効になります。
  最近30件の判断履歴を表示します。取消はローカルの判断のみで、既に作成したDraft PRは取り消しません。
  作成済みPRを取り消す場合はGitHubで手動で閉じてください。同じレビューからの重複PRは拒否します。
- API取得失敗はlive承認状態を無効化。最後の公開成功状態は残します。
- 取得した記事本文・下書き内容は保存しません。公開写真のメタデータだけを扱います。
- version管理するものは固定 `sync-reviews/approvals.json`。
  コメント本文・写真URL・記事本文・名前文字列ではなく、対応するハッシュと追加承認境界だけです。
- public出力へadmin、local-state、review manifestをコピーしません。

## 生成とPR

1. 元のPhase 3C検証、retirement照合、ID・名前・URL互換ゲートをそのまま実行。
2. `sync_review.gate_new_photos()` が新規写真だけに正確な人間承認を追加要求。
3. `article_sync.run()` はisolated candidateを生成し、既存参照と出力を最終検証。
4. 管理室のプレビューは公開snapshotと実API入力を再取得して鮮度を確認し、同じgeneratorを実行。
   変更予定リスト（採用、保留、未承認）と参照保護結果を表示。失敗はready=false。
5. 同期専用PR経路はfresh mainの隔離worktreeで**固定manifestだけ**を書き込み、
   同じgenerator、全pytest、全JS、compileall、cached diff-checkを実行。
6. 長い検証後にもmain・公開snapshot・実APIの入力を再確認。staleならpushしない。
7. 厳格な単一path allow-list、承認された差分だけstage、commit、feature branch push、`gh pr create --draft`。
   merge／deployを呼びません。既存ベストショット・情報拡充のPR allow-listは変更しません。
8. マージ後の毎日同期がmanifestを実際に読み、新規写真を出力します。
   公開成功後は新snapshotで通常の既存写真となり、毎回承認を再適用しません。
   次の名前変更・削除・URL置換には従来のゲートが再び適用されます。

## 検証結果と限界

`docs/sync-review/public-protection.json` と `browser-validation.json` を参照してください。

- 公開906枚のID・名前・URLを同一性比較、Best Shot3件／研究室67ケース参照検証。
- retired7枚不在、固定retirement台帳検証。保護対象JSONに差分なし。
- fixture Atom API以外は実関数を使う生成テストで、未承認新規写真はBLOCKED、
  管理室の採用manifestで生成成功、既存ID保持、将来URL置換はBLOCKEDを確認。
- 判断取消・保存／再読込・冪等性・stale・改ざん・localhost／Origin／CSRF／path制限、
  PR専用allow-listとDraftフロー、失敗reportの秘匿化をテスト。
- Chromium 1440px: 日本語UI、552件一覧、30件paging、保留／取消／保留filter、既存タブ操作、
  console errorなし、横overflowなし。画像ネットワークはこの画面runではofflineにしたため、
  CDNの実画像読み込みと実写真の目視は未検証です。
- この実行環境にローカルはてな認証情報はありません。
  **実APIでのPhase 2写真レビュー→承認→管理室の実Draft PR作成は未実行です。**
  fixtureのGET・generator integrationとmockのGit/gh経路を実API成功と報告しません。
- 実機Windowsでの認証設定とこの操作経路の受入確認が残ります。
- 未分類への手動分類、既存名変更、URL置換、削除を安全に適用する個別移行は今後の作業です。
- 成功／失敗の最新Actions取得はgh認証依存。取得不可でも公開状態レビューは維持。

Hatena記事、GitHub Pages公開、merge、deploy、workflow_dispatchは実行していません。

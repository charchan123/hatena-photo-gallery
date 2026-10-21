# 不明キノコ研究室 コメント・返信・管理：非公開実装監査

## 結果と範囲

Cloudflare Workers＋D1を採用し、訪問者の投稿・本人削除・通報、管理人の公式返信・確認済み・非表示・復元・履歴、Windows管理室の接続、署名付きJSONバックアップとローカル復元を実装した。GitHub Pagesを維持。Supabaseは使用していない。

**本番Cloudflareへ接続・deploy・D1作成/書込・secret登録・受付開始を実行していない。main push・PRマージ・Pages公開も実行していない。** 公開側configとWorker側の受付flagは初期無効。placeholder DBを使い、公開承認と実設定を両側で行わなければ受付できない。

## 開始状態・過去成果

- 最新main：`1843440f0d7796c48c9a13e275eba94ac7ebe8ed`（PR #134マージ済み）。終了前fetchでも同一。
- gh-pages：`acd75e3c2b8850c8eef4ee760b2abdc612d01b4a`。終了前fetchでも同一。
- 過去設計ブランチ `design/research-comments-minimal-mvp-20261021` は `f493c6a81280fa2add7133bce3ddca5f6706b1e6` を指していた。履歴・tree・現在との差分を確認したが、コメント専用の設計/実装成果は見つからなかった。古いmainを現在のmainとして扱わず、最新mainから新ブランチを作成した。
- 写真933、Best17、通知14、研究66、退役7の基準を確認。実データの変更なし。[保護照合](protection.json)。

## 既存構造と恒久ID

`research_ui` は「gallery_name＋記事の識別子」のSHA-256先頭16桁からcase_idを生成していた。同定レジストリはこのIDを参照し、研究表示をopen/identifiedに分ける。今回この計算・既存66ケースのモデル・同定データは完全に維持した。

コメントの対応表 `comments/cases.json` を別に新設。恒久IDは既存case_idそのもので再採番しない。記事識別子と写真ID集合をアンカーとして保持し、表示IDは明示allow-listにする。名前変更・写真追加削除・統合分割・ID衝突では自動で付け替えず、そのケースの投稿を確認待ちにする。既存スレッドは独立の履歴保管欄で読める。判明済み展示は同じIDを使う。

旧→新の表示ID追加は、同じ全写真・同じ記事であると人間が判断した専用対応表変更でのみ許す。現行モデルにID重複がある場合も、片方だけに推測で紐付けない。DB側でも恒久ID・アンカー更新、alias付け替え・削除を禁止している。

公開生成の `research-comment-cases.json` はその時点で安全に一致するactive IDだけを含む。Workerは投稿前に固定Pages URLから取得し、registry hash・DB metadataと照合する。旧ケースが消えた場合、古いWorkerが投稿受付を続けることも防ぐ。API障害はギャラリー生成へ波及させない。

コメント対応表を既存の削除保護・未マージPR保護inventoryへ追加した。名前確定後もコメント履歴の写真が無参照扱いで自動削除されない。既存の独立2回観測・承認・保護解除条件は緩めていない。研究アーカイブ承認だけでこの新しい履歴参照を解除しない。

## UI

各ケースの折り畳みを開くまでコメントAPI・Turnstileへ接続しない。66件の一斉取得はない。20件ずつ古い順に読み、投稿した自分のコメントは直後に表示する。続きのページとの重複・順序逆転を防止。ニックネームは初回だけ提案し、保存済み値を上書きしない。APIエラーが起きても写真・撮影日・記事リンク・研究室本体は維持する。

管理室はケース名検索、件数/未確認/通報数、未確認絞込、公式返信、非表示/復元、通報・日本語操作履歴、検証済みbackup downloadを追加。ケース一覧のスクロールと本文を分け、66ケースの下までスクロールしないとコメントが見えない問題を避けた。管理者secretはブラウザへ出さない。

## セキュリティレビュー

| リスク | 実装・検証 |
|---|---|
| 認証偽装・管理者なりすまし | 一般payloadのrole/official/parentを拒否。予約名を正規化して禁止。公式バッジは認証済みAPIが保存したroleのみ |
| XSS / SQL injection | textContent表示・HTML不解釈。全入力検証・prepared bind。500文字/30文字/200文字・8KiBの要求上限をWorkerでも強制 |
| bot・連打 | Turnstileのサーバー検証、hostname/action/5分を確認。設定不足・test secret・検証失敗では閉じる。D1の原子的回数制限 |
| 二重投稿・通信失敗 | UUID要求IDとpayload hashをtransaction内で記録。再送は同じ結果を返し、違うpayloadは拒否。結果不明時の入力・キーを保持 |
| 他人の削除 | 256bitキーを投稿前に安全乱数で発行。DBはコメントIDに結ぶhashのみ。名前は削除権限にしない。使用後hashを消し再利用不可 |
| 本人削除の復活 | 名前・本文・hash・関連通報理由を消去。DB triggerとadmin APIで復元を拒否。古いbackupも最新の削除ledgerと元投稿の再送防止receiptを優先 |
| 管理API漏えい | Windows Pythonの環境変数→固定HTTPS proxy。Origin付きadmin要求拒否、admin CORS不許可。redirect不許可・timeout・応答size上限 |
| 個人情報 | 生IP/メール/登録情報を保存しない。日単位HMACのcounter/通報hashはmaintenanceで消去。backupには通報hashを含めない。アプリは秘密・本文・IP・SQLエラーをログへ出さない |
| 誤った復元 | schema・checksum・HMAC・installation ID・registry・FKを検証。新しいローカルDBだけへ復元。現在の署名付き削除ledgerが必須 |

アプリ全体の権限・CSRF・Host/Origin検証、管理室下書きのsave/recover、Draft PR作成、本番生成workflowは維持した。稼働中の既存下書きへアクセス・削除・初期化をしていない。

復元レビューで「古いbackup取得後に投稿・削除されたコメント」の再送に注意し、最新tombstoneだけでなく元投稿receiptも保持する回帰を追加した。古いブラウザ要求を再送しても消した本文を再登録しない。

## 実装とDB

Workers `comments/worker.mjs`、初回migration3本（表/制約、保護trigger、66ケース）、無効設定 `wrangler.jsonc`、公開側無効config、オフラインseed/restoreツール。テーブルはmetadata/cases/aliases/comments/requests/reports/audit/limits。設計・API・導入・費用・運用は[導入手順](../../docs/research-comments-workers-d1.md)。

バックアップは一貫したD1 batchで取得し、SHA-256とHMAC検証後だけ成功表示する。16MiBを超えたら不完全なJSONを返さず明示失敗する。大規模化した場合の公式D1 exportは別承認で行う。日常のモデレーションは論理非表示で、本人削除のみ内容を消す。

## 検証

- Python全件 **1079 PASS**。研究ID/衝突/変更、保護参照、Windows proxy、署名を含む新9件。
- Worker/実SQLite SQL・migration・API・auth・悪用対策・backup/restore **13テストPASS**。合成本文・一時DBのみ。Turnstile・Pages manifestの通信は隔離モック。
- 既存JavaScript13ファイルの全回帰・新旧JS構文検証PASS。
- 実ローカルWorker＋SQLite＋Python管理室＋Chromiumの結合 **21項目PASS**。無効状態、66件の非一斉読込、投稿、即時表示、nickname維持、owner key、paging順序、公式返信、通報、非表示、復元、backup、本人削除、APIエラー、PC1280・390・320幅。
- 初回ローカル全件では既存同期fixture33件のOUTPUT_INTEGRITY_ERRORが発生。既存guardを変更せず調査再実行し、最終の全件1079件を合格確認した。初回エラーを合格扱いにしていない。
- 新CIはNode24・Python3.11・Ubuntu/実Windowsで新API/DB/管理室を確認する。既存の全Python・スター・通知・管理室・削除監査CIも実行する。最終HEADの各workflow URL・結果・最終SHA・Draft PR URLはPR本文へ記録する。

ローカルSQL adapterはD1のprepared statement/batchを実SQLite transactionで再現する。**未接続の実Cloudflare D1・実Turnstileを確認済みとはしていない**。本番導入前の承認されたstaging smoke testが必要。

## 画面・保護証跡

[PCケース](case-1280.webp)／[スマホケース](case-390.webp)／[スマホ入力](compose-390.webp)／[管理室](admin-comments.webp)／[API障害](api-error.webp)／[結合結果](browser-result.json)。写真表示は合成画像に差し替えた隔離ブラウザfixtureで、元写真を変更していない。コメントも本番ではなく一時SQLiteの合成データ。

[保護hash](protection.json)は最新mainと公開portalを独立照合。写真ID/URL/EXIF、Best17件・順序・コメント・年間指定・手動日付、NEW!14件、研究同定、退役7枚、master/sources/facets/承認履歴の全保護ファイルがバイト単位で同一。研究66ケースモデルも旧コードと完全一致。

## 未公開事項・判断事項

- 本番Cloudflare/D1・Turnstile・ドメイン・secret登録・公開受付・本番復元は未実施。一般利用者同士の返信は対象外。
- 公開前に管理者がアカウント/料金プラン、公開origin・hostname、受付開始日、回数制限、通報対応、backup/履歴保持期間を決める。無料枠内で月額0米ドルを目指すが利用量次第。有料化は別承認。
- ケース統合/分割/不一致は自動処理しない。対応表修正は専用レビュー。稼働後registry変更とrestoreには別途手順確認が必要。
- PC側のPR #134反映・下書き保護更新は別タスク。旧ActionsのNode20 warning更新も混入していない。

Draft・未マージ・未公開で停止する。公開承認を得る前にflagsやplaceholderを実値へ変える作業をしない。

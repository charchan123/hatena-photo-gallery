# PR137 root限定Windows診断パッケージ（準備版）

**現時点では実行承認なし。Cloudflareへ実行しない。** 日時・絶対期限は空、approval.template.jsonはapproved=false。旧RUN_FIRST.ps1/first.mjsを含まない。Node24以上、PowerShell5.1/7を想定。npm/Wranglerのインストールやdeployは不要。

## 内容・整合性

runner.mjsは既存read-only preflight/コードreceipt/Access・D1照合と独立watchdog/URLoff処理をroot専用に統合する。preflight.mjsの純粋guardをNov4 packetから再利用し、期限固定値と旧CLIを除去、旧Service inventoryだけ5件へ更新。code-receipt.mjs/expected-seed.jsonは旧packetとバイト一致。Access snapshot/新readiness/診断adapterはrepositoryの正本をそのまま同梱する。Service資格情報・管理Bearerを受け取らない。

package-manifest.jsonに各同梱ファイルSHA256とGitHub source HEAD。公開されたZIP SHAとmanifest SHAを別経路のPR監査で照合する。内部manifestだけでは真正性を保証しない。API/本人メールを入力する前にPowerShellでmanifest SHAと全ファイルを確認し、その確認が終わるまでNode moduleをimportしない。SHA不一致なら再取得・調査し、値を合わせてごまかさない。

## 将来の承認設定（今は作らない/発行しない）

実施日時が決まってから、本人の明示承認内容に一致する新しいapproval.jsonを別ファイルとして作り、そのSHAをWorkと確認する。template自体は変更しない。

- approved=true、今回固有authorization_id（16〜32桁hex）、not_before_utc/expires_at_utcを秒までのUTC ISO形式（末尾Z）で指定。開始〜絶対終了は最大30分。JST表記も承認文で照合する。自動延長なし。
- 対象API token名 `kinoko-comments-origin-diag-build-<実施日YYYYMMDD>`、その非秘密ID。旧tokenは再利用しない。発行/契約はこのパッケージでは行わない。
- 専用Worker1件だけIndividual Workers Editor、同accountのD1/Access apps/policies/service tokensのRead-only。Billing/DNS/Pages/Turnstile/Access編集/他Worker編集なし。Editorにはdeploy能力も含まれるが、runnerの書込allowlistは対象WorkerのURL enabled boolean/preview=falseだけ。token自体の権限・実有効期限は管理画面の発行レビューを本人が確認する。runner単独で全権限を読み取れたとは扱わない。
- Free契約、PR138 Worker/Pages不変、custom domain/zone routeなし、本番コメントOFFを本人の正規Dashboard/GitHub読み取りで確認し、チェック時刻と最新PR/main/gh-pages SHAを設定。PR SHAはpackage source HEADと完全一致が必要。これらは**operator確認**として記録し、APIで自動検証した事実と区別する。10分以上古い確認やfalseなら拒否。
- Worker/D1/Access本人限定Allow・全app優先関係・旧5Service Disabled/expired・3migrations/66cases/66aliases/空・version/worker-first/配置code SHAはrunnerが読み取り再照合する。PR138等のAccess snapshotはNov4の独立した基準と比較する。他Worker/Pagesを編集できる権限は求めない。

## 新しい実行フォルダー・過去証拠

既存Nov4作業フォルダーをEvidenceDirectoryとして指定する。nov4-readonly-report-*.json、nov4-first-report-*.json、nov4-first-attempt.local.json等の指定名だけを読む。必要な成功baseline/閉鎖STOP/markerが欠けたら停止し、旧資料を削除・編集・作り直さない。本文や秘密値は取り込まず、限定した過去の事実とファイルSHAだけを使う。

新run directoryはLOCALAPPDATA/KinokoCommentsStaging/origin-diag-<承認ID>。同じ承認IDでの起動は同じfolderを使用し、markerがあれば再試行できない。承認IDだけ変えて無断再試行しない。coreの専用markerはroot-observations内に別途作る。markerは通信前、core markerはURL enable前に排他的に作成する。異常終了しても残す。

## 承認後にだけ行う順序

1. ZIP/manifest SHAと同梱ファイルをVERIFY_OFFLINE.ps1で確認。これは通信なし。
2. approval.jsonの期限・operator確認とSHAを確認。RUN_APPROVED.ps1 -Phase ReadOnlyでAPI token/本人メールを伏字入力。正規Cloudflare APIのGETと固定SELECT7本以外を拒否する。コード・Access・DB・過去証拠一致のread-only-reportを保存し、入力は毎回finallyで消す。
3. ReadOnly成功後に**別の明示実行指示**で同じ承認IDの-Phase Diagnose。再度伏字入力し、10分以内のread-only reportと新たなsnapshotを完全照合。残期限5分以上が必要。
4. core marker→独立watchdog起動→URLoffの冪等POSTとGET/settings読返しで閉鎖権限を証明→watchdog-armed保存→対象Production URLだけon。Preview=falseを維持。
5. 未認証GET `/`のみ。準備最大3回/15秒（1要求4秒、既定間隔3秒）、正規Access302が3連続した場合だけ独立root1回（4秒）。最大4要求。Cookie/Authorization/Service Authなし、redirect=manual、cache=no-store。301/303/307/308も停止。すべての404を成功にしない。302後の404再発、および404の繰返しは即停止。
6. 成否によらずURLoffをPOSTし、GET/settingsで確認。新しいsnapshotとAccess/D1/code/旧証拠の完全一致を照合。normal close確認後だけwatchdogを終了する。read/write=false、not-approvedは一度も解除しない。
7. API tokenを正規Dashboardで削除し、対象名/IDが一覧から消えたことを確認。CONFIRM_CLEANUP.ps1は本人による削除確認と閉鎖reportがある場合だけcleanup-receiptを新規保存する。**このreceiptはoperator確認であり、APIによる独立した失効証明ではない。** Token管理の追加編集権限は求めない。main reportが閉鎖不明の場合、同じ承認IDのwatchdog/CloseOnly成功reportをClosureProofFileとして明示指定できる。自動閉鎖証拠がすべて不成立ならreceiptを成功にせず、本人Dashboardの閉鎖/削除をWorkへ別途報告して記録する。

現在のPowerShell入力は各phase終了/例外時に消去し、SecureString/BSTRを破棄、環境変数を除去し、現在のclipboardを空白で上書きする。Windows clipboard履歴/同期の消去や.NET文字列の完全な物理ゼロ化まで証明しない。clipboard消去失敗は表示し、本人が手動で処理する。PowerShell強制終了/PC電源断ではfinallyの実行は保証されないが、process終了でそのメモリ保持は終わる。残存tokenはDashboardで必ず削除する。

起動用パラメーターはApprovalFile、ApprovalSHA256、ManifestSHA256、EvidenceDirectory、Phase。今回これらの実値・期限・tokenを用意しない。次回Workが承認済み日時とSHAを埋めた単一コマンドを提示する。出力例のREADY/STOP行をPowerShellのコマンドとして入力しない。

## watchdog・閉鎖失敗

watchdogはmainとは別Node processで、Windowsでもdetached=trueの独立process groupとして起動する。準備成功から90秒後に1回だけ対象URLをoffにし、結果をwatchdog-report.jsonへ保存。親のIPC切断でもtimerを止めない。main異常終了後の独立動作を模擬試験する。PC電源断/OSが両processを終了した場合まで保証しない。

enableの応答が失われた場合も、既に有効化されている可能性を捨てず、当座のoff読返しだけで閉鎖完了とせずwatchdogの遅延offを残す。main閉鎖失敗は最優先STOP、独立watchdogを切断/unrefして残す。URLを再開せず、同じ診断を再実行しない。本人がDashboardでProduction/Preview off・Access/flagsを即確認。必要なら既存承認tokenの有効中に-Phase CloseOnly（OFFのみ、観測0、再試行marker変更なし）を別の指示で実行できる。token期限切れ・権限不足・package異常なら新tokenを無断発行せずDashboardで閉鎖する。

安全上、閉鎖確認前に唯一の有効な閉鎖用tokenを先に削除しない。まずURLoffを確実にし、その後直ちにtoken削除。閉鎖不能・秘密漏出・設定不一致は通常の失敗として埋めず、最優先で報告する。

## 結果別の判断（自動続行なし）

| root診断 | 次の判断 |
| --- | --- |
| 404→302→404、302後の404、独立root404 | 停止・閉鎖。Ray/限定header/時刻を既存設定と照合し、伝播遅延を断定しない |
| 404のみ、初回404→302→302 | 準備未成立。閉鎖、同attempt再実行なし |
| 正規302×3＋独立root302 | root有限窓のみ成立。閉鎖し、全パス保護/CPU/OPTIONS合格としない |
| 不正redirect、未知HTML/JSON、timeout、error headers | 停止・閉鎖、body/Locationをチャットへ貼らない |
| Access/DB/registry/code/lease不一致 | public HTTP0で停止。推測で修正しない |
| post snapshot不一致/旧証拠改変 | STOP、変更箇所を調査。失敗履歴/marker保持 |
| 閉鎖不明 | 最優先でDashboard閉鎖、watchdog結果確認。token削除は安全な閉鎖の後 |

保存するHTTP情報はstatus/MIME分類/サイズ/SHA/UTC/経過wall time/正規redirect分類と許可されたheader分類/Ray IDだけ。Worker実行はnot-establishedのまま（Ray/Serverだけで断定しない）。生HTML、Cookie、JWT、API token、本人メール、生Location/クエリは保存しない。wall timeはCPUではない。

実試験・token発行/失効・現在のFree/閉鎖の実確認は今回未実施。過去CPU未達/OPTIONS403/404とmarkerは保持。CPU/Service Auth/全URL認証・コメント/Turnstile総合試験へは別承認なしに進まない。

Windows CIではPowerShell7とnative Windows PowerShell5.1、UbuntuではPowerShell7のwrapper試験を行う。承認JSONのUTF8 BOMも受け付けるが、承認SHAはBOMを含む元bytesに対して検証する。本人PCでの実行は未実施。

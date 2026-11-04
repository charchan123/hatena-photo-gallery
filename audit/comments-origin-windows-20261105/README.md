# PR137 Windows root診断：実行直前準備（オフラインのみ）

開始HEAD `ea27cf747dc1fd7d3c0fcb83b0543860701efd90`。開始main `cd51ca486c542ff6f33f2c9803397110b39893ec`、gh-pages `ac191df2c0537d32ee86bcc670bdfd3151f84082`。Draft/未マージを維持。前回11 workflows/13 jobs成功と404分析/CPU最適化は再利用した。Cloudflare account/API/Workerへの通信0、token発行0、URL有効化0、deploy/migration/seed0。

## 完成物・再利用

- [Windowsパッケージの全手順・次回判断表](../../comments/tools/origin-windows/README.md)
- [統合runner](../../comments/tools/origin-windows/runner.mjs)：別承認のhash-bound lease、read-only/diagnose/close-only、独立watchdog。
- RUN_APPROVED.ps1：PowerShell hash確認→通信なし承認validation→伏字入力→指定phase→finally消去。
- VERIFY_OFFLINE.ps1：manifest/全12ファイルをNode import前に検証。
- CONFIRM_CLEANUP.ps1：閉鎖reportと本人のDashboard削除確認を排他的receiptに保存。独立API失効検証とは主張しない。
- approval.template.json：approved=false、日時/絶対期限/新token情報は空。今は実行できない。
- [ZIP builder](../../comments/tools/build_origin_windows.py)：Git source HEADと12ファイルSHAを含む再現可能なZIPを新規出力。tests/shim/fixture/旧script/秘密値はZIPに入れず、既存出力の上書きを禁止。

Nov4 preflightの純粋guardを抽出し、期限固定と旧CLIを除去。旧Service inventoryだけ4→5へ更新し、すべてDisabled/expiredを要求。code receipt/66cases・66aliases期待値は旧packetとバイト一致。Access validator/core診断は正本をそのまま同梱。reuse-hashes.jsonが元SHAと変更理由を記録する。

coreは今回の指示に合わせ302のみへ厳格化。準備最大3回/15秒、正規302が3連続した場合だけ独立root最大1回/4秒へ進む。404再発は302後でも404連続でも即STOP。旧否定試験/署名/issuer/AUD/期限/D1/OPTIONS204条件の削除・skip・緩和なし。元positive/停止件数の期待変更は、より早く停止する仕様への厳格化だけ。

## 実行・閉鎖境界

公開ZIP/manifest SHAを次回のPR監査で照合する。内部manifestだけを真正性の根拠にしない。明示承認の開始/絶対終了（最大30分）・今回ID・PR/source HEAD一致・直近10分の本人Free/scope/PR138/routes/本番OFF/GitHub確認がなければ、秘密入力/通信前に停止する。実際のtoken権限・Free・PR138 Worker/Pagesはoperator確認として区別する。

ReadOnlyは固定GET/SELECTだけ。配置version/compiled SHA/worker-first、本人Allow/旧Service参照/全Access優先関係、D1/3/66/66/旧5tokensを再照合。旧STOPのbaseline_file/SHAで旧readonly bytesを結び、新旧report/markerを削除しない。raw API snapshotや本人メールを保存しない。

診断は新host/core marker→全snapshot再一致→別process watchdogのOFF POSTと読返しで閉鎖権限を確認→専用Production URLだけON→root GET最大4要求→必ずOFF/読返し/全snapshot/旧証拠不変照合。Previewは常にfalse、READ/WRITE=false・not-approvedを一度も解除しない。Service/管理Bearerを入力する経路は存在しない。

watchdogは親IPC切断でtimerを止めず、90秒後に1回OFFを試行。閉鎖確認後だけ終了する。enable応答喪失も既にONかもしれないため、当座のoffだけで完了宣言せずfallbackを残す。PC/OSが両processを終了する場合は保証しない。閉鎖不明は最優先STOP、再診断せず本人Dashboardで閉鎖し、必要なら既存承認tokenの有効中に明示指示でCloseOnly（OFF以外禁止/public0）。まず閉鎖、次にtoken削除。期限延長/新token自動発行なし。

## 試験と失敗履歴

実子process＋共有模擬APIで、302×3/独立404/404→302→404/全404/timeout/誤redirect/未知HTML/Access不一致public0/閉鎖権限なしpublic0/親kill後OFF/閉鎖二重失敗/enable応答喪失/CloseOnly/再実行拒否/旧証拠保全を検証。元compiled Worker 100,354bytesを圧縮test-only fixtureで再利用し、receipt SHA `0f363c931bd791aaa92b1b89d513fa4709b0ce5504ab5c1c206043c6d847d68a`も省略せず検証する。未知URLへのnative network fallbackなし。

PowerShell構文、未承認入力0、hash改変拒否、成功/例外時のSecureString/env消去、operator receipt重複保存拒否はWindows/Ubuntu両CIのpwshで実行する。PowerShell入力試験ではRead-Host/nodeだけを試験専用functionへ置換し、実認証/実HTTPは行わない。shim/functionを配布ZIPへ混入させない。ローカルにはpwshがないため、ローカルで実行済みと報告しない。

中間Node96件・Python41件/保護照合成功と、初回tamper fixture失敗13/14をtest-history.jsonに保持。改変fixtureの不正なtop-level codeでmodule importが先に失敗したため、byte不一致用fixtureは有効なcomment追記へ修正し、PowerShellのimport前hash検証と改変試験を追加した。失敗を消さず、期待条件を緩めていない。最終HEADの全CI/最終ZIP SHAはPR監査コメントを正本とし、未完了CIを成功と先書きしない。

重要runtimeと保護データは開始HEAD/最新mainとのバイト比較を維持。写真933/BestShot17/NEW14/研究室66/退役7/master141/sources419、本番コメントOFFはprotection.json。旧404、CPU未達、OPTIONS403・Service Auth401履歴も保持。

## 次回承認案

日時と絶対期限は今回設定しない。次回に本人が具体的JST開始/終了を指定してからUTCと照合する。API token名は`kinoko-comments-origin-diag-build-<実施日YYYYMMDD>`、専用Worker1件Editor＋同account D1/Access metadata Read-onlyのみ、最大30分、終了後即Dashboard削除。Service Token0、追加secret0、Access編集0。

| root結果 | 閉鎖後の判断 |
| --- | --- |
| 404再発/独立404 | Ray/限定header/時刻で発生層を絞る。伝播遅延と断定しない、再試行なし |
| 全404/3連続302未成立 | 準備未成立。設定資料を調査し、再開は別承認 |
| 302×3＋独立302 | root有限窓だけ成立。全パス・Service Auth・CPU・OPTIONSは別計画/承認 |
| HTML/JSON/redirect/timeout/error headers | 停止、機密本文を収集/貼付しない |
| Access/D1/code/Free/scope/期限不一致 | public0で停止、推測で修正しない |
| 閉鎖不明/enable応答不明 | watchdog＋Dashboard閉鎖を最優先。唯一の閉鎖tokenを先に削除しない |
| watchdogも閉鎖失敗 | セキュリティ上の未完了として報告、本人Dashboard閉鎖。成功へ付替えない |

限定メタデータとWorker execution not-establishedだけを保存し、wall timeをCPUにしない。root結果からCPU/OPTIONS/総合試験へ自動続行しない。**今回の到達点は実行直前準備とオフライン検証まで。本人の日時・絶対期限を含む明示承認待ち。** 前回閉鎖証拠を維持し、今回Cloudflareへ接続して再証明したとは報告しない。


本人Windowsの旧marker/reportの現在の存在は今回PCへ接続して確認したものではない。次回に指定されたEvidenceDirectoryで不足や不一致があれば停止する。今回証明したのは、保存済み正本の再利用と模擬旧ファイルの保全である。

ZIPは固定timestamp/Unix mode/順序とZIP_STOREDを使い、zlib版差を除く。GitHub最終HEADの全CI成功後に同じsourceから配布ZIPを生成し、Windows/Ubuntuのbuilder receiptとファイル/ZIP SHAを照合する。旧packet/markerは置換しない。

WindowsのCIはpwshに加えてnative PowerShell5.1でも同じwrapper試験を実行する。5.1のSet-Content UTF8が付けるBOMは、承認SHAを元bytesへ固定したままJSON decode時だけ扱い、通信なしの専用回帰も追加。初回CIのPowerShell assertionは全通過したが、意図した否定試験のLASTEXITCODE=1がshellへ残ったため失敗した。assertionを全通過した後だけ0へ戻すharness修正を行い、履歴とrun/job IDをtest-history.jsonに保存した。

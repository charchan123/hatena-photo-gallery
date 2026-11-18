# CI試行記録（2026-10-22 JST）

## 初回実装HEAD：8c2d16ac976c96ab71d58ed24917a3d65f8cb44c

Windowsコメント回帰run 39791115401の表面上のsuccessだけでは全合格としなかった。ログに新規テスト1件のUnicodeDecodeError（既定cp1252でUTF-8日本語を読取）を発見。後続コマンド成功がPowerShellのnative exit codeを上書きしていた。fc81f634で新規テストのUTF-8明示と、当該workflowの両OS fail-fast bashを実装。skip/削除/ゲート緩和は行っていない。

## 修正HEAD：fc81f63411a21b924578de2523c1f0968a8d8622

- ローカル通常Python全件：1107 passed in 113.04s。
- [Validate Admin Changes 39792386741](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39792386741)：success。
- [コメント 39792386648](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39792386648)：Windows/Ubuntu success。Windowsログでbash -e -o pipefail、Python37 passed、API24、ブラウザ21＋26を独立確認。
- [管理室PR 39792386732](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39792386732)：success。
- [手動撮影日 39792386508](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39792386508)：success。
- [削除画面 39792386473](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39792386473)：success。
- [読取専用削除監査 39792386308](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39792386308)：success。

### スターCIのインフラ停止

[39792386581](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39792386581) のjob 119871403023は、Ubuntu apt mirrorからPlaywright依存を取得中に時間切れ。実装テスト前であり、スター合格とは数えない。ログには以下を確認した。

- 開始：14:03:21 UTC。Install isolated Chromiumのapt依存取得が長時間継続。
- azure.archive.ubuntu.comからフォント/glib等の取得が遅延、再試行あり。
- 14:12:19 UTC：The operation was canceled。
- 以後のfixture/公式widget/interaction工程はskipped、証跡なし。

jobの取得工程はcancelledなのにrunはin_progressのまま残り、単一job再実行・failed-jobs再実行APIは403で「already running」と応答した。失敗を成功に書換えたり、本番スターを操作して回避したりしていない。

この監査追記だけのコミットで新しいランナーの全CIを起動する。アプリ・テスト・公開設定はfc81f634から不変。最終HEADに対するCI結果とURLはPR本文へ記録し、前のHEADの成功を最終HEAD成功の代用にはしない。Node20警告のActions更新、既存スター試験や安全条件の緩和は行わない。

# PR137：Validate Admin Changesの履歴不足修正

2026-11-02 JST。開始HEAD `c4728dd8b52687092bad48fc25f19b11c416305f`、main `b913ad7b07f689f14f5c8dcecea11b7c99363827`、gh-pages `3549e4ea9fa5619fe6eb53f7c5716d675250ce4f`。開始PRはDraft/open/unmerged、mainからahead9/behind0。

## 確定した失敗と原因

[失敗run 41305759613](https://github.com/charchan123/hatena-photo-gallery/actions/runs/41305759613)、validate job `124845686887` のログを確認。

- 最初のcheckoutは `fetch-depth: 1`、実際のfetchも `--depth=1`。PR merge refだけを浅く取得。
- Python結果は **1131 passed / 1 failed**。`test_cpu_runtime_pins_reject_unreviewed_changes` が固定の過去コミット `1766b1693ec87a2945b98abc5456f48fc9a13026:comments/staging/access.mjs` をgit showしてexit128。
- その後のJavaScript syntax/regression stepとsetup-pythonの後処理がskip。テストを意図的にskipしたものではなく、前段の失敗による。
- 元の履歴に対象ファイルが存在することを確認。ファイル欠落ではなく、checkoutで履歴を取得していなかったことが原因。

## オフライン再現

実アカウントに接続せず、ローカルGit objectから開始HEADをdepth1で新しい一時repoへfetch/checkoutした。

| 同一の未変更検査 | depth1 | unshallow後 |
|---|---:|---:|
| 過去のaccess.mjsをgit show | exit128 | exit0 |
| 既存assert_staging_sourceによる検査 | CalledProcessErrorを再現 | 正常/改変拒否の5 assertion成功 |

検査本体・テスト・runtimeのバイトを一切変えず、Git履歴だけで失敗/成功が分かれることを確認。5 assertionは、2 runtimeの正常一致と各改変拒否、Access JWT module改変拒否。pytest全件やCPUベンチをローカルで最初から再実行していない。

## 最小修正と保護

実行コードの変更は `.github/workflows/admin-validate.yml` の最初のcheckoutへ `fetch-depth: 0` を追加しただけ。既存PR merge refでの検証、persist-credentials=false、read権限、別checkoutの公開データsnapshot、全件試験・比較対象SHA・バイト一致・期待値を維持。

CPU最適化・OPTIONS設計・registry/manifest/migrations・JWT verifier・写真/EXIF・トップ・LightGallery・管理室・日次同期・削除保護・本番configは開始HEADから不変。新しいCloudflare token/権限/secretは追加しない。

## 再利用した旧HEADの確定CI

11 workflowsのjob/stepを読み、10 workflows /12 jobs success、Validate 1 workflow/1 job failureを確認した。以下の成功済み機能をローカルで再調査・再実装しない。

| workflow | 旧run | 旧結果 |
|---|---|---|
| manual capture date | 41305759621 | success |
| deletion audit | 41305759635 | success |
| deletion browser | 41305759629 | success |
| Hatena Star | 41305759641 | success |
| AI artwork | 41305759604 | success |
| shared LightGallery | 41305759573 | success |
| Hatena release preparation | 41305759611 | success |
| admin Draft PR（Windows/Ubuntu） | 41305759565 | 両job success |
| research comments（Windows/Ubuntu） | 41305759627 | 両job success、API/D1/Access、dry-run、実Chromium/localhost proxyを含む |
| layout tuning | 41305759566 | success |
| Validate Admin Changes | 41305759613 | Python 1件失敗、JS step未到達 |

修正後の新HEADで自動起動した必要な11 workflows /13 jobsと重要stepを最終確認する。最終結果はPR137の監査コメントにrun URL付きで保存し、この文書の更新によるHEAD循環を避ける。確認前に全件成功・本番公開可能とは報告しない。

## 境界と残作業

## 同日の追加CI：Windows CRLFの安全停止

履歴修正HEAD `8e40593d7980ab5d10bc0cde87d511fc709b9321` のValidateは成功し、Python1132 passed、後続JSも成功。一方、[comments run 41349627606](https://github.com/charchan123/hatena-photo-gallery/actions/runs/41349627606) のWindows job `124976807206` はPython40 passed/1 failedとなった。`registry.mjs`の作業コピーにCRLFが残り、固定SHAとの厳密比較が拒否した。Ubuntu commentsは30 Node試験・D1/API/Access・dry-run・ブラウザを含め成功。他10 workflowsも成功。失敗を削除・成功扱いしない。

ログ上、従来の `core.autocrlf=false` と既存作業コピーへの `checkout-index --all --force` は実行済みだった。そのWindows環境でCRLFが残った詳細要因（runner設定等）は未確定。テストに改行正規化を追加せず、comments workflowの準備stepだけを、新しい一時prefixへ `core.autocrlf=false` / `core.eol=lf` を明示してindexを出力し、そのバイトを作業コピーへ戻す方式にする。Git index/検査基準/ソースblobは不変。

ローカルの一時Git repoでCRLF入力を作り、新方式で元blobと完全一致することを確認。Linuxでは旧方式でもLFへ戻ったため、Windowsの旧方式の不具合をローカル再現できたとは主張しない。最終Windows CIで確認する。変更範囲はCI準備だけで、runtime・テストの削除/skip/期待値/SHA緩和はなし。

## 変更後も維持する境界

ローカルCPU既存結果2.13228→0.18148ms（91.49%減）、67→0 SHA、D1 3→3を引き継ぐ。初回負荷と実Cloudflare10ms達成は未確認。過去のOPTIONS403/CPU未達の実履歴は消さない。

今回Cloudflareアカウント接続・設定変更・実試験は0件。前回のURL閉鎖/READ・WRITE=false/not-approved/Service Token無効/構築API token削除の停止記録を維持し、再接続で確認したとは主張しない。実CPU cold/warm、実Accessの切り分け、実Turnstile、合成投稿/削除/返信/backup、実Windows/Androidは別承認後の作業。

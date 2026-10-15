# 実行環境切断による停止・復旧記録

GitHub状態の再確認: 2026-10-15T14:23:28.350Z

**依頼全体は未完了です。PR #113はDraftのまま、マージ・公開不可です。**

実行環境が `409 Conflict / environment_offline / Environment is not connected` となり、
通常起動、別ディレクトリ、PTYによる再接続も失敗しました。
最終実装の保存・最終CIが完了する前に停止しています。
未確認の実装を完成扱いにせず、この復旧記録と照合済みの明細をGitHubへ保存します。

## GitHubへ保存済みの範囲

- PR: https://github.com/charchan123/hatena-photo-gallery/pull/113
- 障害前の保存済みhead: `132d306b46421ad405833b35bb6a0315184bed29`
- 独立した削除判定プロトタイプ、履歴保存の基礎、全open PRのBest Shot参照取得、読み取り専用ライブ監査。
- **管理室UI・日次adapter・運用workflow接続の最終版はGitHub保存未完了。**
- 保存済みコードでは既存の日次削除拒否ゲートを変更していません。
- 今回の追記では読取り専用監査CLIに、認証情報や記事本文を含まない件数・照合キーのログ出力だけを追加します。

## 公開状態と既存PR

| 対象 | 再確認したSHA/状態 |
|---|---|
| main | `4f953c7f0723f8ab44d72a12fcaf00579776ee66` |
| gh-pages | `757cbfc868452d3bb892849fce0e2122cd8c566e` |
| PR #110 | マージ済み |
| PR #111 | Draft・未マージ、head `4448c3431a1c275ca686e9e2a0a7736fc67f0841` |
| PR #112 | Draft・未マージ、head `a8d5792ec2e62e3a630124743c0bffc1d8fa48a6` |

main・gh-pages・#111/#112への変更は行っていません。実データの削除承認manifestも作成していません。

## ライブ照合済みの事実

2026-10-15の読み取り専用Actions:
https://github.com/charchan123/hatena-photo-gallery/actions/runs/38742041771

artifact: `deletion-live-audit-38742041771-1`、ZIP SHA-256:
`adb5fc385dfba7fa58a51d7e9a29e7605cc77daeba525f0fc3b6cbcf0fdbdd07`。

12ページ・112エントリー・公開111記事・下書き除外1、全ページ完了。
これは独立した運用確認履歴の2回としては扱っていません。

| 母集団 | 前回公開 | このAPI取得 | 差分 |
|---|---:|---:|---|
| 公開記事 | 110 | 111 | 削除1・追加2 |
| 全DOM画像出現 | 976 | 980 | 削除16・追加20 |
| 図鑑観察写真 | 906 | 893候補 | 欠落16・新規候補3 |

新規20画像の内訳は図鑑候補3、未収録17。
新記事は9/22富士山（11画像、候補ドクツルタケ1）と10/3富士山（9画像、候補クロカワ・ベニテングタケ各1）。

16枚の元記事・Atom ID・観察ID・画像URL・名前は [missing-photos-16.csv](missing-photos-16.csv)。
最初の15件は監査commit `2ea454fa51e6b10febf77ea48a9c361a6b61bb44` の明細を保持し、
全件API取得で確認した新しい1件と照合run番号を追記しました。
新しい行では、実施していない直接HTTP確認の欄や未再読取の旧inventory stateを空欄にしています。

2025/9/2掛川市の記事hashは
`f4c1c839abafe71eb16494d0d921cd96df6cbf32aefce8eee19a8807a90a923e`。
削除画像1枚は `obs-10f29e7b04472ecb1e1d4fccfb060889cfa1dfc2012922b4c299d483a8647f01`。
執筆者の意図的削除確認があるのはこの1記事です。他の15枚を人間の承認済みにはしていません。

### 保護対象

- 公開Best Shot 3件・PR #111の12件（年間Bestを含む）と欠落16件の競合は0。
- `research-940496f1ccdb136f` カワリハツ？: **元1枚・欠落1枚**。無承認でケースを消してはいけない。
- `research-f9cb62e956fa8604` Lanmaoa angustispora(和名無し)？: **元6枚・欠落1枚・残存5枚**。
- 新たな1枚は `obs-87fa70cf88bf584c315b452899c54a1426d784d2fb6aa9beede5b38d2a98a7c6`、
  7/6掛川市の記事、画像末尾 `20250710220635.jpg`。ケース全体を退役させず、残存5枚と履歴を継続する判断が必要。

ローカルで実行した保護確認では、906枚の公開baseline、既存dataファイル、
旧7枚退役契約、141種・419出典・373特徴割当・overlay 0の変更なしを確認しました。
この確認資料の最終ファイル保存は、環境切断のため未完了です。

## 実装中の設計

厳密なAtom ID・記事URL・写真URL・出現番号で対象を特定し、
別runによる完全取得2回、6〜72時間間隔、全保護参照取得、残存順序・重複数確認を必須とする設計です。
自動削除上限は全DOM画像の3%かつ20枚、記事は5%かつ2件。
URL置換疑い・共有/重複変更・再出現・大量削除・履歴不整合は停止または個別確認です。

確認履歴は専用Git branchへ非forceで先に永続保存し、保存できなければ適用しません。
公開snapshotには最小receiptと履歴anchorを保持し、旧7枚契約を上書きしません。
保護写真が未承認なら部分公開せず、公開全体を停止して巡回・検出を継続する設計です。

管理室では写真単位の保留・代替案・承認、ケース継続と全体アーカイブ/退役を分離しています。
原子的なローカル保存・入力保持・二重送信防止・日本語エラーを試験しました。
代替提案だけで参照を書き換えず、正の承認は別のDraft PRをマージした後だけ有効にする方針です。

## 実際に確認した試験と未確認事項

| 確認 | 実施済み結果 |
|---|---|
| 開始mainのPython baseline | 840 PASS |
| ローカルの中間全Python試験 | 906 PASS、その後909 PASS |
| 最後に完了した新規関連fixture試験 | 74 PASS |
| 既存のJavaScript試験・構文確認 | PASS |
| Chromium Best Shot回帰 | 92項目PASS |
| Chromium削除承認UI | 29項目PASS（PC・キーボード・タッチ相当、隔離fixture） |
| production validator | 141種・419出典・373割当・overlay 0、PASS |
| 本番認証のGET取得 | 上記Actionsで全件取得PASS |
| 最終実装の全試験/CI/保存 | **未完了** |
| 本番履歴branchへの運用書込み・削除公開 | **未実施** |

74件と909件は異なる時点の結果です。最終版の全試験がPASSしたとは扱いません。
Chromium以外の実ブラウザー/実機タッチ、本番への削除適用も検証済みとはしません。

## 復旧時の確認事項

作業checkout: `/workspace/scratch/d2f9454413ea/hatena-photo-gallery`
作業branch: `feature/safe-photo-deletion-2026-10-15`。

1. working treeを先に確認し、未コミットの変更を保持する。強制resetやcleanをしない。
2. 管理室 `admin/deletions.py` / `admin/static/deletions.js` / HTML/CSS/server、
   `deletion_guard.py`、`deletion_approvals.py`、`article_sync.py`、日次workflowの差分を確認する。
3. 研究アーカイブ承認がmainへ入り公開待ちになった後の再レビュー、
   アーカイブを保留に戻す際の同定履歴復元、supersedesによる判断変更を重点確認する。
   最後の追加修正コマンドは接続障害で実行結果を確認できていない。
4. 管理室のPR検証は `isolated_generator` を使い、記事本文・生成ファイルをworktreeのstagingへ混入させない。
5. 既存840件を含む全Python、全JS、Chromium両試験、安全ゲートを最終コードで再実行する。
6. 読取り専用Actionsで最新APIと実adapterのfail-closedを再確認し、コードと証拠を追加コミットする。
7. 全件をレビューできる状態にしても、PRはDraftのまま停止する。

本番再開は不可です。#111/#112の扱いを含めfresh main/公開snapshotで再検証し、
運用履歴の独立確認と保護写真2件の明示判断・別Draft PRを経る必要があります。
今回の停止は環境障害によるもので、安全条件を緩めて回避しません。

# PR #114 本番導入前の最終安全監査

対象: `charchan123/hatena-photo-gallery` PR #114 head
`b8839dd1989500276bf4f0299c3f56094f163c4c`。
後継Draft: https://github.com/charchan123/hatena-photo-gallery/pull/115

**判定: #114をそのまま本番導入することは推奨しない。再出現検査の不足を修正した後継を、観測専用状態でレビューする。**
自動公開の解禁は別の明示判断が必要。今回の監査ではmerge/公開/実対象の承認を一切行っていない。

## 開始時の読み取り確認

| 対象 | SHA / 状態 |
|---|---|
| main | `4f953c7f0723f8ab44d72a12fcaf00579776ee66` |
| gh-pages | `757cbfc868452d3bb892849fce0e2122cd8c566e` |
| #111 | open Draft, `4448c3431a1c275ca686e9e2a0a7736fc67f0841` |
| #112 | open Draft, `a8d5792ec2e62e3a630124743c0bffc1d8fa48a6` |
| #113 | open Draft, `2d1ba75622f8df5314b1bb2c476d53dbb7a0b4b7` |
| #114 | open Draft, `b8839dd1989500276bf4f0299c3f56094f163c4c`, CI 3種類SUCCESS |
| sync-deletion-audit | 存在しない。本番の運用記録0回 |

open PR #2も含む参照保護を確認。#114のREPORT/RECOVERY/VALIDATION全文、既存の独立取得・保護・承認・アーカイブ・日次接続・履歴コードを再利用した。

## 指摘と修正

| ID | 重要度 | 確認内容 | 対応 |
|---|---|---|---|
| PF-01 | HIGH | 退役記事URLをreceiptに保持しておらず、翌回に別Atom ID/別写真で同じURLが再出現する場合と、翌回生成物の旧記事リンクを見逃す。**修正前の2試験でDID NOT RAISEを再現** | receiptへarticle_url_hashを保持し、全後続取得・出力で照合 |
| PF-02 | MEDIUM | per-target history_headと実履歴/候補、manual receiptと承認内容の対応検査が不足 | anchor存在/候補fingerprint/baseline/commit、承認action/日時を照合。resealされた不正receiptも停止 |
| PF-03 | MEDIUM | 履歴Git treeのblob形式を確認せず、Git通信に時間制限がなかった | 100644 blob限定、timeout 60秒、本文を返さない固定エラー。隔離bare Gitで形式破損・競合を検証 |
| PF-04 | MEDIUM | branch push/PR作成の応答が失われると、盲目的な再試行で別PRを作れる余地 | remote書込み前に試行をatomic/CAS保存。成功済みは同じURLを返し、結果不明は再起動後も停止。branchを管理室履歴で表示 |
| PF-06 | HIGH | 未マージPRの保護がBest Shot/保留に限定され、別のcurated JSON・個別移行・特集HTML/JS/Pythonの写真参照を収集していなかった | 全open PRの変更ファイル一覧を完全取得し、固定headの完全blobからID/URL/hash参照を保護。ページング/取得異常・3000ファイル上限は停止。非参照変更で不必要に承認を失効させない |
| PF-05 | 導入時の制御 | 実装マージだけで公開処理が有効になり、初回観測を公開から独立して制御する設定がなかった | checked-in公開スイッチをfalseに固定。実sourceの取得履歴は保存するが、明示的な別レビューでtrueにするまで削除/出力置換/Pages deployを禁止 |

PF-01の修正前再現はfixtureのみ。実写真の削除や本番history書込みはしていない。
新receipt項目がない古いgeneric deletion receiptは推測補完せず停止する。現在の公開snapshotにはgeneric deletion receiptがないため本番データ移行は不要。旧7枚の退役receipt/schemaは変更しない。

## 監査した安全契約

- 認証付きstrict GETの全ページ、記事一意性、下書き判定、HTML/DOM画像会計。取得異常は削除許可にならない。
- 同じbaseline/fingerprint/保護集合で別runの完全取得2回。6〜72時間、同一runのattempt違いを除外。取得異常・再登場・文脈変化で確認リセット。
- Atom ID/記事URL/画像URL/ordinal、共有URL・重複・順序/ラベル・下書き化・大量削除を個別に検査。通常の人間承認でも識別異常は解除しない。
- Best Shot/年間Best、全open PRの未公開選定/保留、研究/同定、既存移行・curated参照を保護。列挙失敗・途中変更は停止。
- 保存成功確認前に削除を許可せず、append-only/non-force/race/巻戻し/破損を検証。研究写真の無承認削除はない。
- 管理室のID再入力、個別判断、stale/競合/CSRF/Origin、supersedes、マージ済み公開前の研究判断取消しと同定履歴復元。
- Draft PRは隔離worktreeの厳密なmanifest/必要なregistryだけをstageする。生成物・ローカル状態を混入させず、最新main/APIと再照合してDraftで作成。生成/試験失敗、余計なファイル、main競合、push/応答消失では公開しない。
- 公開停止中も日次監査/差分記録を継続。履歴保存初期化が失敗しても独立read-only監査workflowは取得を試みる。
- 初回2回の観測が揃っても、公開スイッチfalseのままなら出力を作り替えない。実ジェネレーターで確認した。

## 検証結果と証拠

最終の件数・head・CI・API実測は `VALIDATION.json` を参照。
独立確認・履歴競合はfixture/隔離bare Git。本番認証APIはread-only Actionsのみで再取得した。
管理室のPR作成経路は隔離CLI fixtureで検証した。実対象の承認PR作成や、利用者PCでのgh認証は実行していない。
Chromiumは削除UI31項目 + Best Shot92項目。Safari/Firefox/実機タッチは未実施。
production contract 141種/419出典/373承認特徴/overlay0、公開906写真、Best Shot3/PR #111の12、研究ケース1/1欠落と1/6欠落を保護。

raw main.py単独のCI生成は既存ID調整を迂回するため、Best Shot解決失敗をログする場合がある。
このCIステップのSUCCESSを公開可能の証明に使わない。公開候補はarticle_syncのguardと既存validator、管理室の隔離previewでのみ判定する。

## 残るリスク・未実施

1. 本番token/branch規則でhistoryの作成・追記が成功するかは、導入後の実観測で確認する。拒否時は公開停止。現在の本番履歴は未作成。
2. 最新のブログ変更・未公開PR変更でfingerprint/参照集合が変われば、既存の2回確認/承認を流用しない。
3. Git権限を信頼境界とする。hash chainは管理者による全コード/履歴同時改変に対する電子署名ではない。
4. Git操作は60秒で停止。長期の履歴蓄積ではloadコスト/timeoutに注意し、履歴を勝手に間引かない。
5. 通知の実到達はGitHub Actionsの個人設定依存で未確認。
6. 結果不明PRは自動再作成を止める。管理室に表示したbranchをGitHubで確認し、既存PRの有無/内容/commitを確認してから復旧する。ローカル試行記録を盲目的に削除しない。
7. アーカイブはPages非表示であり、公開GitHubの承認capsule/履歴には残る。秘密保管/完全消去ではない。
8. リリース後のrollbackでも新receiptに対応するguardが必要。旧コードへ単純に戻すと安全停止するため、history/snapshotを消して回避しない。

推奨マージ順・導入後の最初の2回・研究2件の判断方法は `RUNBOOK.md` に記載。

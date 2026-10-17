# 本番観測の確認と公開再開までの残作業（2026-10-17）

**2回目の独立観測は未成立。公開再開の条件は未達。公開・削除・研究判断は実行していない。**

## 最新状態

確認時刻 2026-10-17 09:55 JST。main は `4b95bd9e9e44f225027858c5dd4fd4b7cd865f59`（PR #115導入済み）。
`generate.yml` の `SAFE_PHOTO_DELETION_PUBLISH_ENABLED` は文字列 `false`。gh-pages は `757cbfc868452d3bb892849fce0e2122cd8c566e` のまま、906写真を保持。
09:00 JST以降の定期実行はActions一覧に存在しない。直近の本番同期は初回run [38922030976](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38922030976)。
Open PRは #111/#112/#2。いずれも変更していない。#113/#114/#115はopen一覧にない。

新規workflow_dispatchの起動を試みたが、GitHub連携はGET/既存job再実行のみで新規dispatch機能を提供していない。接続ブラウザーはこの会話から利用できず、クラウドブラウザーのGitHubは未ログイン。安全なログイン要求後、GitHubが「Incorrect username or password」を表示したため認証の再試行を停止した。**dispatchは未送信であり、新run IDは存在しない。** 同一runのRe-run jobsを2回目として代用していない。

## 初回証拠の再利用・検証

既存実装・前回の946 Python / 123 Chromium検証は繰り返し実装していない。今回の変更は監査文書と証拠のみ。

| 確認項目 | 実証した結果 |
|---|---|
| 初回fetch | `2026-10-16T15:13:04.820724+00:00` = 10/17 00:13:04.820724 JST |
| 独立ID | `actions:38922030976`、attempt 1 |
| API | 認証precheck成功、12ページ、112 entries、下書き1除外、公開111、HTML111、ページング完了、表現差0 |
| 差分 | 記事削除1、記事追加2、DOM写真欠落16、追加20、URL変更疑い0、分類変更0 |
| 候補 | 前回CSVと16 observation_idが完全一致。識別異常0、一括大量削除判定0 |
| 履歴 | `sync-deletion-audit` head `7d31346fddd1b01b0515614cd24128be3947c1bd`、fetch/resultの2イベント・2コミット |
| 完全性 | 本番の `GitHistory.load` でhash連鎖、seq、head index、tree mode、1イベント1コミット・追加専用差分を検証 |
| fetch event seal | `c949591fb222ca9a103fb40873a5ff4519f7998610a81c24df4671ebf186ba76` |
| 結果 | `DELETION_CONFIRMATION_OR_APPROVAL_PENDING`、pending16、eligible0、applied0 |
| 公開 | Pages deploy SKIPPED。初回runのfailureは安全停止 |
| Artifact | `12054976764`、ZIP SHA256 `b2e80e3b8405d1e7ae3dfa25353d49b0e80dfb5b705ee2e067ec31c9fd3c0aa3` と照合済み |
| 保存済み契約 | 導入前mainとの `data/`、旧7枚manifest、`sync_retirement.py` 差分なし。実削除承認manifest 0件 |
| 今回の限定再検証 | `test_sync_deletions.py` / `test_deletion_guard.py` / `test_deletion_workflow.py`: 82 PASS |

原API本文・認証情報は保存しない。PR作成後の読み取り専用監査で、新しい認証付き完全API取得も成功した（下記）。ただし本番履歴に保存される第二観測とは区別する。

## 最新の読み取り専用API監査

PR #116に伴う [run 38988628365](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38988628365) は成功。
取得時刻 `2026-10-17T00:56:32.162085+00:00`（09:56:32 JST）、初回から9時間43分27.341361秒。12ページ/112 entries/公開111/下書き1除外/完全取得/表現差0。
欠落16枚のID・candidate fingerprint・保護sha256 `66995ea14ae7c242b49bbdab6d8d275fd89f49e9b8b987305b37aed1e2925e1a` は初回と完全一致。研究2件は引き続き保護、残0/残5。
main Best Shotおよび未マージPR #111/#112/#2/#116の参照検証成功。IDの読み取り専用シミュレーションは既存890 ID保持＋新規3 ID、公開未実行。全削除の承認ではない。
実guarded previewも成功し、安全停止 `DELETION_CONFIRMATION_OR_APPROVAL_PENDING`、eligible0/pending16/applied0、`history_persisted=false` を確認した。
Artifact `12083849224` のZIP SHA256 `8d1de465fdb7905c910d598c46cda9b2f6cb3ebdf831cd546af42760c6375ea0` を照合済み。
**このrunは異なるIDで時間差も範囲内だが、本番履歴へ記録しない監査なので2回目成立とは扱わない。履歴への手動転記もしない。**
同じ文書headのChromium CIも成功。次の文書追記では製品コードを変更していない。

## 2回目の実行・照合

[Build & Deploy Photo Gallery](https://github.com/charchan123/hatena-photo-gallery/actions/workflows/generate.yml) の **Run workflow / branch main** で新規runを1件起動する。起動直前に定期runが既に走っていないか確認し、重複起動を避ける。公開スイッチはfalseのまま。

初回と組にできるfetch時刻の範囲は **10/17 06:13:04.820724〜10/20 00:13:04.820724 JST（両端含む）**。09:00定期runの遅延はあり得るが、未実行のまま完了扱いにしない。

1. 新run IDが38922030976と異なること。同runのattempt違いは無効。
2. API完全性の全条件と認証precheck、取得件数・下書き除外・異常なしを読む。
3. 実fetch時刻差6〜72h、同一baseline/protection、各候補fingerprint一致、途中に不健康fetch/再出現/参照変更がないことを履歴で検証する。対象が変われば確認は取り直す。
4. Artifactの `deletions.history_persisted=true` とfetch sealを、履歴branchの追記・最終headに照合する。通常は新fetch/resultで計4イベントになる。履歴へ手動で証拠を作らない。
5. 同じ16候補・保護集合なら通常14 `automatic_eligible`、研究2 `approval_pending`、pending2が目安。**実測結果を優先し、この期待値を承認に流用しない。**
6. 適用0・Pages SKIPPED、gh-pages不変を確認する。

10:30 JSTのRead-only deletion auditは履歴を書かず、この独立観測の回数には数えない。

## 研究2件の個別判断

最新mainのローカル管理室「写真の削除・承認」→「公開記事を取得して再照合」で、現時点の写真と履歴を確認する。再照合は独立観測として加算しない。

| ケース | 保存済み写真状態 | 管理室の選択肢と影響 |
|---|---|---|
| カワリハツ？ `research-940496f1ccdb136f` | 1枚中1枚欠落、残0 | 「削除を保留」なら公開全体停止を維持。「研究履歴を保持して非公開アーカイブ」ならケース・写真情報・同定履歴をcapsuleで保存しPagesから除外。「研究ケースの退役」は研究終了の明示判断がある場合のみ、履歴は保持。通常承認・写真だけ削除してケース継続は不可 |
| Lanmaoa angustispora(和名無し)？ `research-f9cb62e956fa8604` | 6枚中1枚欠落、残5 | 「削除を保留」、または「研究写真の削除を承認（ケース・履歴は継続）」で欠落1枚だけを外し、残5枚と同定履歴を継続。ケース全体のアーカイブ/退役は不可 |

各対象IDは `PHOTO_REVIEW.csv` に完全形を保存。選ぶ場合は写真IDの再入力・理由・その1件のローカル保存が必要。**本作業では判断を選んでいない。** 代替写真は提案であり、それだけでは削除許可にも既存参照の自動変更にもならない。
アーカイブはPages非表示であり公開GitHub履歴からの秘密化・完全削除ではない。
判断変更は新manifestのsupersedesで履歴を維持し、公開前なら必要に応じregistryを復元。過去manifestを消さない。

## 通常14枚と必要なPR

通常14枚は初回時点で識別問題・保護参照・mass reviewなし。独立2回条件を満たせば自動退役の対象になり、個別の人間承認は不要。ただし現在は実証1回のためeligible0。
現行同期は全対象の条件が揃ってから一括適用する原子的な設計なので、研究2件の未解決中に通常14枚だけを部分公開しない。日次巡回・監査は停止しない。

1. **今回の証拠専用Draft PR**：本資料、機械可読証拠、写真一覧。公開スイッチ・実データ変更なし。マージは必須ではない。
2. **研究判断のDraft PR**：ユーザーが2件を個別に判断した後、管理室で差分確認・隔離生成・検証し、専用PRへ保存。保留/代替案の共有PRは可能だが、それでpending0にはならない。通常14枚の一括承認manifestは作らない。
3. 研究判断PRのユーザー承認・レビュー・マージ（本作業ではしない）。falseを維持し、最新の候補・保護集合で独立確認を満たす新規観測を行う。保護hash等が変われば新しい6〜72hの2回が必要になる場合がある。
4. **pending0を実測**し `DELETION_OBSERVATION_ONLY`、適用0・Pages SKIPPEDを確認する。残りの分類・旧7枚・写真ID・Best Shot/未マージ参照・研究履歴の生成検証も成功させる。
5. この段階で初めて、ユーザーの公開方針を確認して別の**公開スイッチ変更Draft PR**を準備する。今回は2回目と研究判断が未成立なので作成していない。
6. 最終の明示許可・レビュー・マージ後だけ公開実行。run中も安全条件を再検査し、適用receipt/残存ID/研究残5枚/旧7枚/各ページを確認する。

未解決0への操作を自動承認で埋めない。今の阻害要因は、第二観測の起動・実証と研究2件のユーザー判断である。

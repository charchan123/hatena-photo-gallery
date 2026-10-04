# Phase 4C.9 feature v2 implementation package

**READY — Codexのv2 validator実装へ進める固定入力が揃った。** 130/130 cited sourceの全文snapshotが存在し、欠損sourceは0件。元の候補373件・保留10件・明示未収録12種は変更していない。再調査、Web再取得、PDF画像化、GitHubアクセス／書き込みは今回行っていない。

これは「実装を開始できる」というREADYであり、validator実装・CI・画面検証・production投入が完了したという意味ではない。

## 今回の4成果物

| ファイル | 内容 |
|---|---|
| phase4c9-feature-source-snapshots-2026-10-03.jsonl | 130 source、各1行のJSON。保存済みUTF-8抽出全文、取得メタデータ、固定identityとhash |
| phase4c9-feature-evidence-ledger-approved-2026-10-03.json | 採用373 assignmentと377支持証拠。保留10件と撤回引用1件は別セクション |
| phase4c9-feature-approval-manifest-2026-10-03.json | 今回の会話での承認、固定した入力・証拠のhash、承認対象ID、禁止・保留範囲 |
| phase4c9-feature-v2-implementation-package-summary-2026-10-03.md | 本書。実装時の入力、検証結果、hash、production条件 |

前回4成果物は取得した現行版と作業領域の前回出力がbyte単位で一致した。その内容を再生成して置き換えず、そのまま固定した。master、sources、元facet candidateも変更していない。

## 承認の正確な範囲と日時

承認元は **conversation explicit approval**。個人名・役職・本人確認済みという主張は追加していない。

承認メッセージの送信日時は **2026-10-04T00:27:57+09:00**（UTCでは2026-10-03T15:27:57Z）。これは会話に提供されたメッセージ時刻であり、推測した取得日時ではない。ファイル名の2026-10-03は既存の監査パッケージ名として維持した。

- 373 assignmentを既存runtime candidateの採用候補として承認。
- 10 assignmentは保留のままruntimeから除外。
- Option Bのv2 provenance設計を採用。
- IA-029 タマゴタケモドキringは承認対象外。
- 未収録12種に推測によるassignmentを追加しない。

前回candidate/decisionsの`human_approval: null`等は当時の履歴として変更していない。新manifest/ledgerが、**その正確なファイルhashに対する後続の限定承認**を記録する。ユーザーが全原資料を自ら読み直した、あるいは菌類学専門家として確認した、とは記録しない。既に与えられた採用候補承認を取り直す必要はない。

manifestは承認を記録した候補であり、電子署名・本人証明書ではない。Codexの実装時には、本書記載のmanifest SHA-256を信頼する設定／レビュー工程で固定する。候補JSON内の`approved: true`だけで自己承認できる設計にしない。

## 373 / 10 / 12 と証拠の対応

| 検証対象 | 結果 |
|---|---|
| 元assignment | 383 |
| 採用候補 | 373 |
| 保留 | 10 |
| 373＋10 | 383、重複・漏れなし |
| 採用assignmentが参照する証拠 | 377 evidence records、全参照が存在 |
| 前回証拠全体 | 388＝採用377＋保留10＋撤回引用1 |
| summary保有のeligible | 139 |
| included | 127 |
| excluded | 12 |
| 127＋12 | 139、集合も一致、相互に重複なし |
| cited source snapshots | 130 / 130 |
| 欠損source | 0 |
| IA-029 ring | なし。既存4facetのみ |
| 保留10件のruntime混入 | なし |
| 未収録12種への新規assignment | なし |

複数sourceを持つassignmentがあるため、373 assignmentと377 evidence recordは別の数である。元source_idを別のURLへ付け替えていない。

`mycoscience-myc590`は前回decisionsが固定した全文用 `audit-morchella-full.txt` を使用した。同じDOIのabstractだけのcacheへ戻していない。snapshot identityはsource_idと抽出本文SHA-256で構成し、runtime側のevidence_refから一意に辿れる。

## hashの検証範囲と限界

**今回の全入力ファイル・新bundle・ledger・manifest、130抽出本文、388の旧quote、377の採用quote、373のassignment digestは保存bytesから再計算した。** 前回の本文hash、quote hash、行・offset、source URL、取得URL、titleに一致する。

`original_response_sha256`は130件すべて前回decisionsと保存取得メタデータに一致する。ただし、元応答bytesそのものから再計算できたのは保存済みPDFの1件とHTMLの3件、合計4件。残り126件の元HTML bytesは保存されていないため、**原応答hashは継承値であり、126件を再計算済みとは扱っていない。** 抽出全文snapshotは全130件が揃い、機械的にquoteを再検証できる。

特に`research-fukui-amigasatake`と`research-chiba-yanagimatsutake`は、保存スクリプトに後続のcp932再デコード／本文上書き処理があった。福井の処理には画像altを抽出する実装も含まれる。今回のquoteは前回固定済みの本文位置と完全一致するが、当該後続取得では元応答メタデータを更新していないため、本文がそのhistorical response hashのbytesから抽出されたことまで暗号学的に再証明できない。この限界を各snapshotのextraction_methodに明記した。原文判断をやり直したり、再取得で埋めたりしていない。

このパッケージの機械検証対象は**承認された固定抽出本文と証拠の一致**。元HTTP応答からの抽出再現までを保証するものではない。将来、raw HTTP応答の独立再計算を新しい必須要件にする場合、その要件については126件がBLOCKEDとなる。現行の全文snapshot/quoteベースのv2実装開始はREADY。

取得日時がcache metadataにないものは`retrieved_at: null`とし、source台帳のaccessed_atを別欄へ保存した。ファイルmtimeを取得日時へ代用していない。ソフトウェアの当時のversionも未記録ならnullとした。

## Codexへ渡す必須入力

1. 前回の `feature-facets-runtime-candidate-2026-10-03.json`（373件、version2）。
2. 前回の `phase4c9-feature-facet-reconciliation-decisions-2026-10-03.json`（全383件の判断履歴）。
3. hashが一致するmasterとsources（今回参照した添付名は`mushroom-master-final-candidate-2026-10-03(1).json`、`sources-final-candidate-2026-10-03(1).json`）。
4. 今回のsnapshot JSONL、approved ledger、approval manifest。
5. 前回validator-planとreconciliation-report、本書。

repositoryの`data/mushroom-master.json`／`data/sources.json`を使う場合も、まずmanifestのbytes hashと一致するか確認する。今回GitHub上のファイルを読み直して同一性を主張したわけではない。JSONの意味が同じでも整形によってbytesが異なれば、黙ってhashを更新して通さない。

今回snapshot bundleに含むのは抽出全文とメタデータで、PDFや元HTMLのbinary本文ではない。全文照合はネットワークなしで実行可能。前回の入力ファイルはこの4成果物へ再同梱していないため、併せてCodexへ渡す必要がある。

## 機械検証の規約

- JSONLの各行をJSONとして読み、`full_extracted_text`を取り出してUTF-8 encodeしたbytesをhash化する。JSONのエスケープ表現そのものをtext hashに使わない。
- file hashはファイル全bytes。末尾改行を含む。quote hashはquoteのUTF-8 bytes。Unicode正規化・strip・改行変換をしない。
- `char_start`は0始まり、`char_end`はexclusive。**Unicode code-point単位**であり、UTF-8 byte offsetやJavaScriptのUTF-16 code-unit offsetではない。Pythonなら通常の文字列sliceで照合可能。
- 行番号はLFだけを数える1始まり。PDF抽出のform-feedを追加の改行へ変換しない。
- source_id→snapshot identity→本文hash→quoteと位置→evidence_id→decision_id/mushroom_id/facet_id→runtime assignmentの鎖をすべて確認する。
- source集合は当該assignmentが参照する採用evidenceのsource集合と完全一致する。master.features.source_idsとの一致は要求しない。
- `evidence_kind=source_supported_paraphrase`はevidence_text自体の原文完全一致を意味しない。今回固定した承認対象digestで意味対応の判断を束縛し、必ず原文quoteを別に検査する。
- `evidence_kind`は前回candidateのassignment単位の値を保持する。複数sourceではすべてのquoteとevidence_textが同じ表記とは限らないため、各証拠の`evidence_text_exact_substring_of_this_quote`も検査する。source_quote型は少なくとも1つの採用quoteとの完全一致を要求し、他のsourceの支持は固定されたreview_resultにより束縛する。
- ledgerのheld_decisionsとretired_citationsは履歴専用。activeのevidence_refs解決先として使わない。
- 候補側の歴史的`human_approval: null`を機械的に置換せず、最新の外部manifestによるhash単位の承認を解決する。

## production gate

採用候補のユーザー承認と固定snapshotの準備は完了。これから必要なのは以下の実装・検証であり、今回未実施である。

1. v1契約を残したversion2専用validatorを実装する。
2. manifestの外部hash固定と、全入力hash・証拠束縛・quote/offset・coverageを検証する。
3. 保留、別種quote、sourceすり替え、hash改変、自己承認、未使用facet等のnegative testsと既存回帰を通す。
4. 湿時、成長段階、脱落性、つぼの形態等のqualifiersをUIまで保持し、表示を確認する。
5. 公開／GitHub書き込みはその工程で許可された場合にだけ行う。今回の承認はGitHub書き込みや即時公開を含まない。

未解決の生物学的判断は前回保留10件とIA-029 ringのまま。未収録12種への新規証拠・新規facetは追加していない。

## 検証結果

**31項目PASS**。これはbundle/ledger/manifestの整合性検証。v2実装テストやGitHub CIのPASSとは区別する。

| 検査 | 結果 |
|---|---|
| JSON/JSONL構文 | PASS |
| 130 cited sources全snapshot存在 | PASS |
| snapshot identity一意 | PASS |
| 130全文UTF8/text hash/bytes/identity一致 | PASS |
| 再取得・再抽出なし | PASS |
| 前回388証拠のquote hash/本文hash/原応答hash継承一致 | PASS |
| 前回388証拠のUnicode offset/LF行番号一致 | PASS |
| source URL/取得URL/title前回一致 | PASS |
| 373採用assignmentの一対一 | PASS |
| 373採用assignmentの全377 evidence_ref存在 | PASS |
| ledger全sourceにsnapshot存在 | PASS |
| 原runtime assignment完全保持 | PASS |
| evidence/facet/種/source/qualifiers束縛とdigest一致 | PASS |
| candidate373+held10=original383、重複なし | PASS |
| 保留10件runtimeに存在しない | PASS |
| 証拠388=承認377+保留10+撤回引用1、排他的 | PASS |
| 非支持quoteがruntime evidenceに紛れない | PASS |
| coverage139=127+12、排他的 | PASS |
| coverageの3成果間完全一致 | PASS |
| IA-029 ringなし/4facet維持 | PASS |
| 未収録12件への新規assignmentなし | PASS |
| manifestが固定する9ファイルhash/サイズ再計算一致 | PASS |
| candidateの旧decisions/master/sources hash再計算一致 | PASS |
| manifest主要6hashとfile records一致 | PASS |
| ledger inputとsnapshot bundle hash再計算一致 | PASS |
| manifestの承認範囲373件とledger一致 | PASS |
| 承認日時・非個人識別provenance・OptionB一致 | PASS |
| 過去candidateのnullを変更せず外部承認を追加 | PASS |
| 保存済み原応答4件のresponse hash再計算一致 | PASS |
| 原bytes不在126件を再計算済みと偽らない | PASS |
| 保護対象の前回成果物・master・sources・元facet・本文130不変 | PASS |

## 固定hash一覧

すべてSHA-256。入力の整形・再保存でも変わるため、exact bytesを渡す。

| ファイル | SHA-256 |
|---|---|
| feature-facets-runtime-candidate-2026-10-03.json | `6d4d987a535dca9c1d0d3668b65de245fbdc281f56c546af436c6fb853bdd84d` |
| phase4c9-feature-facet-reconciliation-decisions-2026-10-03.json | `e0dbbee4e8bb794d4d4f6306a44ba0bea3fd9879419087a11455fd48c42ed7d2` |
| mushroom-master-final-candidate-2026-10-03(1).json | `2ce8cfc61726ef04bb6f4bba26c42511e2c0bf1d4017b9e87e0a359d61decca4` |
| sources-final-candidate-2026-10-03(1).json | `d5213f1cf0881af1c60ea949c0321ae0eb854daa3f300135dae9e9f9ad2fdb66` |
| feature-facets-final-candidate-2026-10-03(1).json | `57d1ba6b700e1dbff6d3980a55d9bc8718ab8508006c747c0d1c72800d7fb5f4` |
| phase4c9-feature-facet-reconciliation-report-2026-10-03.md | `9314f4df6f6ee5348e675cfa7b64c44b5cd814fc3cd830fb32c8ee2504282889` |
| phase4c9-feature-facet-validator-plan-2026-10-03.md | `b20e9118158769eccbb3ec34e2f4689db1f1413cbd1299fefee207e974fd6ce3` |
| phase4c9-feature-source-snapshots-2026-10-03.jsonl | `5583716324d8ba2600352241c47ff5b61f5f2cef0bea9180f34f4315e2ec048e` |
| phase4c9-feature-evidence-ledger-approved-2026-10-03.json | `0253787fb1bc0cea03cc5aba5759e08c2b0fcfa9fd37e194986011573c926ee7` |
| phase4c9-feature-approval-manifest-2026-10-03.json | `2d6f21f31d7e0e33a513c02a5188f563baa4a8e8bbe1f40866501c3780521d05` |

manifestの自己hashは自己参照を避けるためmanifest内部には入れず、この表で提示した。本summary自身はvalidatorのhash依存関係に含めない。生成順序はsnapshot→ledger→manifest→summaryで、循環依存はない。

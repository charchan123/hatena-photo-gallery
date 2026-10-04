# Phase 4C.9 feature facet validator変更案

2026-10-03。**Option Bを推奨する。** この文書は関数・検証条件単位の設計案であり、GitHub、feature_ui.py、テストコードに変更は加えていない。

検討対象：`charchan123/hatena-photo-gallery`、base `a1ba1c6d247291615378609dd82f0a3c1f0343e0`、branch `phase4c9-141-knowledge-expansion`。branchのfeature_ui.pyを読み取り確認したblobは `e672989c1a9b1d957c2389b40ccfb55bc4f5bfaf`。

## 採用理由と対象データ

現v1は「読者向けsummary」と「facetの証拠」を同じ文字列・source集合へ拘束する。これはsummaryに省略された正しい特徴を拒否し、逆にsummaryと同じ誤った意味付け・過剰引用を通す。今回A 18件は原文に根拠がある一方、summaryにfacetの根拠がない。Bの安全な同等表現があっても、それだけを理由に原文寄りの証拠を要約へ書き換える必要はない。

候補はversion 2を明示し、373 assignment / 127 entries / 4 groups / 20 facets。保留10件は候補のassignmentsに入れない。現在のv1へ直接入れるとversion違反になることが正しい。v1と同じversion番号で契約を黙って緩めない。

候補はassistantによる原文照合済みで、人間承認は未取得。`human_approval: null` を埋めたふりをしない。production検証は承認前の現在の候補を拒否し、レビュー用の構造検証だけは可能にする。

## v1から削除／置換する検査

| 現在の条件 | v2での扱い | 代替／追加条件 |
|---|---|---|
| version == 1 | v1経路には保持。v2経路を別実装 | 未知version、真偽値型のversion、暗黙のdowngradeを拒否 |
| evidence_text in master.features.summary | v2では削除 | 非空、quote/paraphrase区別、facet・種・sourceに束縛したevidence_refs、原文snapshot内のquote/offset/hash、レビュー記録 |
| set(assignment.source_ids) == set(master.features.source_ids) | v2では削除 | source_ids内の型・重複・非空、全IDがsources.jsonに存在、支持済み証拠のsource集合と完全一致 |
| entry集合 == summary保有master集合 | v2では置換 | eligible集合 == included集合 ∪ 理由付きexcluded集合、両者は排他的、全IDがmasterに存在、漏れなし |
| defined group/facet/master、duplicateなし | 保持・型検証を強化 | bool/int/文字列の取り違え、空白だけのID、同一source重複も拒否 |
| 全facet利用 | 保持 | activeな20facetをすべて使用。未使用なら失敗。根拠なしの割当てで埋めず、明示的な定義版更新で扱う |

summaryの非空検査はこの移行では残す。独立証拠を認めることと、読者向けsummaryを無制限に欠損させることは別に扱う。

## 関数単位の変更案

### `load_feature_facets(path)`

既存はJSON読取りだけなので維持できる。ただし重複JSONキーを拒否する共通ローダーへ寄せる。未知versionをここでv1へ変換しない。明示的な入出力の分離を維持する。

### `validate_feature_facets(...)`：version dispatcher

既存2引数呼出しはv1で引き続き有効。v2は不足した引数を無視せずエラーにする。

```python
# 設計擬似コード。既存ファイルへのpatchではない。
def validate_feature_facets(
    feature_data, mushroom_master, *, sources=None,
    evidence_ledger=None, source_snapshots=None,
    approval_manifest=None, mode="production"
):
    version = require_integer_version(feature_data)  # boolを拒否
    if version == 1:
        return _validate_feature_facets_v1(feature_data, mushroom_master)
    if version != 2:
        raise FeatureFacetError("unsupported feature contract version")
    require_present(sources, evidence_ledger, source_snapshots)
    _validate_feature_facets_v2_structure(
        feature_data, mushroom_master, sources, evidence_ledger
    )
    _validate_source_evidence(feature_data, evidence_ledger, source_snapshots)
    _validate_coverage(feature_data, mushroom_master, evidence_ledger)
    if mode == "production":
        _validate_approved_manifest(
            feature_data, evidence_ledger, approval_manifest
        )
    elif mode != "review":
        raise FeatureFacetError("unsupported validation mode")
    return True
```

実装時は上記の補助関数とerror contextを定義する。未定義の擬似関数をそのままcopyして動くコードという意味ではない。review modeの成功をproduction mode成功として扱う呼出しは禁止する。

### `_validate_feature_facets_v1(feature_data, mushroom_master)`

現在のvalidate本体を分離する。既存26種向けのexact substring・source set equal・coverage equalの契約とnegative testsを残す。v2データをv1へ渡した場合は拒否し、例外をcatchして緩い経路へ再試行しない。

### `_validate_feature_facets_v2_structure(...)`

1. root/groups/facets/entries/assignmentsが所定の型。group_id、facet_id、mushroom_idを非空文字列として検証し、それぞれ重複禁止。
2. facet.group_idは定義済み。entry.mushroom_idはmasterに存在。master IDとsources IDの重複も検出する。
3. assignment.facet_idは定義済み。同一mushroom_id内で同じfacet_idを2回使わない。全active facet利用を維持。
4. evidence_textはstrip後非空。source_idsは空でない文字列配列で、重複を許さない。すべてsource台帳に存在。
5. evidence_refsも非空かつ重複なし。台帳の各参照のmushroom_id/facet_idがassignmentと一致し、source_idがassignment.source_idsにある。
6. `set(source_ids) == {ledger[ref].source_id for ref in evidence_refs}`。sourceだけ余分に付けることも、参照を隠すことも拒否。
7. 引用URLとsource台帳URLの整合を検証。DOI→全文HTMLなどの派生取得URLは別欄に記録し、監査で確認した対応だけを許可する。任意のredirect先を同じ出典として自動承認しない。
8. root provenanceにmaster/sources/input facetのSHA-256があり、期待入力と一致する。台帳自身のファイルSHA-256も候補側のdecisions_sha256と一致する。正当な変更も再レビュー／新しい承認manifestを必要とする。
9. evidence_kindは`source_quote`か`source_supported_paraphrase`。quote型は対象quoteに含まれる。paraphrase型は原文との意味対応を承認済み判定で確認する。形態キーワードの出現だけで意味対応を自動承認しない。

### `_validate_source_evidence(feature_data, ledger, source_snapshots)`

- source snapshotは実行時Web取得でなく、レビュー時に固定したUTF-8抽出本文を入力する。取得URL、取得履歴、元応答SHA-256、抽出方法、本文SHA-256を保持する。
- 本文hashを検証し、指定offsetのsubstringがquoteと完全一致すること、quote hash、行範囲が一致することを確認する。Unicode正規化や改行除去を黙って行わない。抽出方法を変えたら再固定する。
- source側の対象種見出し、比較表の列、形態の部位、湿時・成長・脱落・変異の条件は判定台帳の必須項目とする。snapshot全文内の別種の同一語が一致しても通さない。
- runtimeに入る参照は`supports_facet`だけ。`does_not_support_this_facet`、`insufficient_for_current_facet_semantics`、未確認、競合未処理は拒否。複数sourceを挙げるときは各sourceについて当該facetの支持を記録する。
- evidence_textだけを差し替えても、source、facet、qualifiers、判断、snapshotを含む承認対象digestが変わるようにする。
- HTTP 200、タイトル一致、LLMのスコア、単語の出現は意味上の支持を保証しない。validatorが自力で「原文は実際にこのfacetを支持する」と証明できるわけではない。担当者による原文照合とその承認の不変性を機械検査する。

現在4成果物には短い原文quoteと各hash/locatorを含むが、130出典の全文snapshot一式は同梱していない。再監査で利用した保存済み本文を、実装工程で固定した監査資料として管理する必要がある。quoteの自己hashだけで原サイト由来を証明したと扱わない。全文bundleを用意できない場合はproduction gateを通さない。この前提を満たさず参照存在チェックだけへ縮退することは禁止する。

### `_validate_approved_manifest(...)`

承認済みと書かれたJSONそのものを無条件に信用しない。信頼されるレビュー工程で固定したmanifestに、承認担当者、日時、candidate/decisions/sources/master/snapshot集合のdigest、対象assignment一覧を記録する。CIは管理された承認manifestのdigestと照合する。データファイルと一緒に自由に書き換えた`approved: true`では通らない。

reviewer_kind=assistant_source_readingは原文照合の履歴であり、人間の承認署名の代替ではない。現在のnull値を埋めるのは承認実施後に限る。

### `_validate_coverage(feature_data, mushroom_master, ledger)`

この移行ではeligibleを非空summaryのmaster ID集合から計算する（現在139）。candidateに書かれたeligibleをそのまま信用せず、再計算して照合する。

- includedは実際に1件以上の採用assignmentを持つentry ID集合（現在127）。空entryでcoverageを水増ししない。
- excludedはeligible内の未収録ID（現在12）と理由・状態の台帳。includedと重複不可。eligible外のIDも不可。
- `eligible == included | excluded`、`included & excluded == empty` を必須にする。
- 今回は12件が元の383 assignmentに含まれないことを明記している。既存の特徴を否定した意味ではない。採用証拠を追加してincludedへ移すには新たなレビューが必要。
- assignment単位では元383＝採用373＋保留10を検証する。保留一覧はruntime assignmentに混入できず、削除して保留履歴も消すことはできない。
- 将来masterのsummaryを追加・削除して対象集合が変わる場合、coverage manifestも理由付きで更新されるまで失敗させる。

### `build_feature_search_model(...)`

既存の`subject.mushroom_master_id`による明示joinとAND検索を維持。名前の類似一致でjoinしない。

v2では事前にproduction検証したデータだけを渡す呼出しを固定する。戻り値にassignmentのevidence_text、限定条件、sourceリンク、決定IDを渡せる構造を追加する。facet_labelsだけに落として、湿時・成長段階・変異の条件を失わない。

coverage_countは現在どおり表示対象subjectの実数であり、データの127 entriesや141 masterをそのまま表示しない。subjectがない種にfacetがあっても、表示種数へ足さない。sourcesや内部hashは通常の一覧で露出させず、根拠の詳細表示に必要な項目だけを出す。

### `render_feature_page(model, ...)`

既存の「特徴だけで種類を判定しない」という注意を維持する。v2の条件を根拠詳細として確認できる表示にする。

中実後中空などを両facetで検索する場合、種に記載された特徴の集合であって一個体の同時状態を保証しないと分かるようにする。つぼの名残／環状／襟状を袋状の完全なつぼと表示しない。鱗片の脱落、湿時粘性、変色部位を省略しない。今回保留した4つのringは条件表示を追加しただけで自動復帰させず、別の明示承認を必要とする。

### `generate_feature_page(...)` と呼出し元

生成開始前にvalidatorをproduction modeで実行する経路を必須にする。v2用のsources/evidence ledger/snapshots/approval manifestの入力がなければ生成を停止する。既存の呼出し元は実装工程で全件検索し、同じ入力を渡すよう更新する。失敗をcatchして未検証データでページを生成しない。

この監査ではfeature_ui.py本体を確認したが、repository全体の全呼出し元や全テストファイルの変更を実施・検証したわけではない。

## 実装工程で必要なテスト

契約変更の具体的な危険を捉えるテストだけを追加する。既存の全体テストは維持する。

| ケース | 期待 |
|---|---|
| 元v1の正常26種 | 既存契約でPASS |
| v1のsummary不一致/source集合不一致 | 引き続きFAIL |
| v2でsummaryにないが承認済みの独立証拠 | PASS |
| v2のsourceがmaster sourceの部分集合／別集合、直接支持あり | PASS |
| source未知、空、重複、余分な非支持source | FAIL |
| 別mushroom／別facetのevidence_ref流用 | FAIL |
| 同じページの別種の記述や比較表の列の取違え | 未承認判定を拒否。レビューfixtureで正しい対象を固定 |
| 文字列に「つば」があるが「なし」「痕跡」の例 | キーワードだけでは承認しない。今回の保留ring fixtureはFAIL |
| quote/offset/hashの改変、本文snapshot欠落 | FAIL |
| evidence_textだけの意味変更／source_idすり替え | 承認digest不一致でFAIL |
| candidateが勝手にapprovedへ変更 | 管理されたmanifest不一致でFAIL |
| source_quoteとparaphraseの混同 | FAIL |
| 同一facet重複、未知ID、空entry、未使用active facet | FAIL |
| eligible139=127収録+12理由付き未収録 | PASS |
| 12未収録の理由を削除／1ID欠落／includedとexcluded重複 | FAIL |
| 元383と採用＋保留の数・ID集合不一致 | FAIL |
| IA-029にringを追加 | 既存保留decisionとの不一致でFAIL |
| UIに湿時・成長段階・つぼの限定が届かない | UI契約テストFAIL |
| 現在のcandidateをproduction modeに入力 | 人間承認未取得のためFAIL |

上記はテスト仕様であり、実装済みPASSと混同しない。本監査で実行したのは成果物内の32項目の整合性検証と現行v1の期待した拒否の確認である。

## 投入順序

1. 4成果物を人間がレビューし、保留10件と採用373件の境界、sourceごとの証拠を確認する。
2. 保存済み本文・原資料とhashを固定し、特に比較表、原著、名前表記差のlocatorを再現可能にする。
3. v1を維持してv2validatorと条件表示を実装する。既存テスト＋上表の差分テストを通す。
4. 人間の承認manifestを固定する。master/sourcesの今回未変更という境界と、v2候補の4定義群・20facet不変を確認する。
5. production modeで承認済みcandidateを検証し、ページ生成と実表示を確認してから、別途許可された工程で投入する。

現時点ではGitHubへ反映しない。validatorを先に緩めて383件を全採用することも、CIだけを目的に全sourceをmasterへ合わせることもしない。

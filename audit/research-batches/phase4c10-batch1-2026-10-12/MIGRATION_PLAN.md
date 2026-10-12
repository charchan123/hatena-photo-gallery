# 本番反映の境界と独立移行案

現在の成果は全件pendingで、人間の承認0件。以下は移行設計案であり、実装・承認・promotionではない。

## 既存契約で扱える範囲

P4C10-P-001の既存20条件へのadditive assignment、京都府sourceの追加、対応snapshot・evidenceの追加は既存 `admin/knowledge.py` と `feature_overlay.py` の形にできる。本バッチのintakeにはその1件だけを入れた。検証時の内部合成承認は既存validate_batchの一時的な契約検査であり、実際のhuman approvalを保存していない。

取り込み例（このPRでは実行していない）：

```bash
mkdir -p admin/inbox
cp -r audit/research-batches/phase4c10-batch1-2026-10-12/intake/phase4c10-batch1-2026-10-12 admin/inbox/
```

本番候補を作る前に、source URL・本文・掲載学名範囲を人間が確認し、取得サービス経由の範囲限定snapshotを承認に使用できるか判断する。原サイトHTTP応答ハッシュとは異なるという取得制約を隠さない。より完全な原本取得が必要と判断された場合は、新snapshotと新manifestを作り直し、旧candidateのレビューをリセットする。

基準mainが変わっていれば、base SHAを現在値に無条件差し替えて終わりにしない。既存のID・facet・source・prior overlayとの競合を再確認し、intake manifestを再生成したうえで、人間レビューをリセットする。

すべての判断が終わった後に、既存Admin workflowがfresh mainの一時worktreeで承認済み候補だけを再構成・検証し、独立promotion PRを作る。研究PRのマージにこの操作を含めない。IA-029 ringや既存保留10件は対象外。

## 既存master9件は独立契約が必要

現契約は既存mushroom_idの上書き、既存source・snapshotの置換を拒否し、immutable baseline＋additive overlayでproductionとdeep equalityを要求する。masterのfeature/alias/taxonomy/habitat修正をmushroom_additionsに入れることはできない。

提案する後続設計は、immutable Phase 4C.9資料をそのまま残し、**既存masterの項目訂正だけを検証する独立した訂正層**を追加する方式。設計レビュー前にvalidatorへ例外を追加しない。

必要な要件：

- 専用の訂正registry、訂正manifest、変更delta、独立の人間decisionを追加し、各ファイルのhash鎖を固定する。
- 訂正deltaは既存mushroom_id、allowlistされたfield、正確なold_value、new_value、source/evidence参照に限定する。全record置換、種ID・和名の暗黙移動、削除・並べ替えは禁止。
- baselineと既存additive overlayを先に現行validatorで検証し、その結果のコピーに訂正層を適用する。基準値とold_valueが違えば失敗させる。
- 新sourceは固有IDで追加し、既存sourceを更新しない。同URLの二重登録・snapshot置換を禁止し、必要な新しい取得記録は別versionの設計により保持する。
- aliases_jaの根拠はsourceを持つ訂正evidence台帳で追跡し、既存スキーマがalias別sourceを持たない制約を明記する。
- food_safety、toxins、scientific_name、ring禁止の変更は今回の訂正allowlistから除外する。学名競合は資料別注記として保持する。
- 専用validatorで型・ID・参照・snapshot・文字位置・hash・人間decisionを検証し、productionのmasterを最終再構成と照合する。既存featureの373件と保留10件も再検証する。
- master訂正が特徴検索の条件付与へ暗黙伝播しない。facetは別の承認・additive契約を継続する。
- 写真906枚、Phase 3C、Best Shot、研究室、同期、名前変更、手動採用、通知、UIに差分がないことを確認する。

この設計が承認されるまでは、master補完9件は研究候補のまま。dataや固定SHAを書き換えたり、production validatorを迂回して反映したりしない。

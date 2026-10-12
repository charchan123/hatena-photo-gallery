# Phase 4C.10 第1バッチ

調査成果専用。候補はすべて人間未承認で、本番データ・overlay registryを変更しない。

対象は特徴未収録12種およびIA-019/020/029、スギヒラタケの計16種。

既存Phase 4C.9 Option B v2を再利用する。master補完は独立した移行案とし、additive assignment候補とは分ける。

入口は [REPORT.md](REPORT.md)。本番反映の境界は [MIGRATION_PLAN.md](MIGRATION_PLAN.md)。

- `species-research.json`：16種の既存値点検・今回の調査・留保。
- `partial-gap-triage.json`：partial 139件の不足フィールド点検（全件再調査ではない）。
- `proposals.json`：10提案と完全なold/new値・根拠・pending状態。
- `master-completion-proposals.json`：独立master移行が必要な9提案。
- `source-candidates.json`：新規source 3件。既存台帳を上書きしない。
- `research-source-snapshots.jsonl`、`retrieval-provenance.json`：本文の範囲限定断片22件と取得の限界。
- `intake/phase4c10-batch1-2026-10-12/`：既存Admin形式の未承認1facet候補。
- `prior-review-continuity.json`：過去の採用・保留・追加調査判断との連続性。
- `unconfirmed-materials.json`：本文未確認で提案に利用しない3資料。
- `baseline.json`、`validator-report.json`、`test-results.json`、`javascript-tests.json`、`validation-logs/`：保護・検証の証跡。
- `verify.py`：本番・既存ファイルを変更しない再現監査。

再現監査：リポジトリrootから `python audit/research-batches/phase4c10-batch1-2026-10-12/verify.py`。

`original_response_sha256`は取得サービス応答のhashであり、原サイトHTTP本文の取得証明ではない。full_extracted_textも全HTMLではなく保存対象の断片全体。詳細はREPORTとretrieval-provenanceを確認する。

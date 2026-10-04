#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-/tmp/phase4c9-v2-input}"

rm -rf "$OUT"
mkdir -p "$OUT"

for f in \
  feature-facets-final-candidate-2026-10-03.json \
  phase4c9-feature-approval-manifest-2026-10-03.json \
  phase4c9-feature-facet-reconciliation-report-2026-10-03.md \
  phase4c9-feature-facet-validator-plan-2026-10-03.md \
  phase4c9-feature-source-snapshots-2026-10-03.jsonl \
  phase4c9-feature-v2-implementation-package-summary-2026-10-03.md \
  sources-final-candidate-2026-10-03.json
do
  cp "$ROOT/files/$f" "$OUT/$f"
done

for f in \
  feature-facets-runtime-candidate-2026-10-03.json \
  mushroom-master-final-candidate-2026-10-03.json \
  phase4c9-feature-evidence-ledger-approved-2026-10-03.json \
  phase4c9-feature-facet-reconciliation-decisions-2026-10-03.json
do
  cat "$ROOT/parts/$f"/part-* > "$OUT/$f"
done

(
  cd "$OUT"
  sha256sum -c "$ROOT/SHA256SUMS.txt"
)

echo "Phase 4C.9 v2 input package reconstructed and verified at: $OUT"

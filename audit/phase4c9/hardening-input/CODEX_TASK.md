# Phase 4C.9 overlay hardening input

This branch is an INPUT-ONLY handoff branch. Do not merge or deploy it.

Base GitHub main:
- commit: f5ab9a8510a8c4cfd4741d39b3b8f2b20da94e66
- tree: 02b778ab6fad5dd6cbaed3c897c25c01328ee305

Payload:
- audit/phase4c9/hardening-input/phase4c9-incremental-overlay-contract.patch.gz
- gzip bytes: 9655
- gzip SHA-256: a2c91405593e8abba37875fdf1b311f88b856a9391e8998c8eba25e45caaa3dc
- decompressed patch bytes: 41907
- decompressed patch lines: 678
- decompressed patch SHA-256: 899ecf8229cb774346b31c2649e8ba75ba649b7d5195cf9af8a31235efc06eaa

Required first steps in Codex:

```bash
sha256sum audit/phase4c9/hardening-input/phase4c9-incremental-overlay-contract.patch.gz
gzip -dc audit/phase4c9/hardening-input/phase4c9-incremental-overlay-contract.patch.gz > /tmp/phase4c9-incremental-overlay-contract.patch
wc -c /tmp/phase4c9-incremental-overlay-contract.patch
wc -l /tmp/phase4c9-incremental-overlay-contract.patch
sha256sum /tmp/phase4c9-incremental-overlay-contract.patch
```

Expected patch SHA-256:
899ecf8229cb774346b31c2649e8ba75ba649b7d5195cf9af8a31235efc06eaa

Only continue if all identity checks pass.

# Phase 4C.9 v2 — temporary Codex Cloud input package

This branch exists only to make the 11 audited Phase 4C.9 artifacts available to Codex Cloud through GitHub.

The source artifacts are preserved byte-for-byte. Large text artifacts are split into line-preserving parts only because the transfer path has per-read limits. Reconstruct them before use.

## Required first command

```bash
audit/phase4c9/v2-input/reconstruct.sh
```

The script rebuilds all 11 files under `/tmp/phase4c9-v2-input` and runs `sha256sum -c`.
**All 11 entries must print `OK` before any implementation work begins.**

Do not edit, reformat, reserialize, or normalize these files before verification.

## Fixed approval boundary

- approved runtime assignments: 373
- held assignments: 10
- eligible species: 139
- included species: 127
- explicitly uncovered/excluded species: 12
- cited source snapshots: 130/130
- Option B v2 provenance model
- IA-029 タマゴタケモドキ ring: NOT APPROVED
- no inferred assignments for the 12 uncovered species

## Branch use

Use this branch as the starting point for the Codex v2-validator implementation branch.
Do not merge this temporary input package directly to `main`.
Do not deploy it as production data.

The Phase 4C.9 production cutover remains a later, separately reviewed step.

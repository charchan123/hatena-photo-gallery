# 研究写真2件の正式な個別承認提案（2026-10-17）

**Draft PR #117。マージ・本番適用・公開は未実行。公開スイッチfalseを維持。**

## 承認根拠と対象

[ユーザーの個別承認記録](https://github.com/charchan123/hatena-photo-gallery/pull/116#issuecomment-6228088094)をGitHubから取得し、投稿者OWNER/charchan123、対象ID・ケース・actionを照合した。
コメント本文SHA256: `dc580b456284e621d96d15e2026eec3f968e1f2b4a21fe130237f0a7720d09ca`。

| 対象 | 正式処理 | 保全・適用範囲 | approval_id |
|---|---|---|---|
| カワリハツ？ `obs-b65bc66594a331b3fb0e79f41dbfe9d2b8c5e94bdd826c49b1a6b26472f12e51` | `archive_research` | `research-940496f1ccdb136f` の元写真情報1枚、ケース全体、同定履歴をcapsuleに保存。公開候補の研究一覧から除外。研究終了のretire_researchには変更していない | `5f32b7cac402a67fd52ec373a98ec85393e7dfb3617197884c3d10a8027736e4` |
| Lanmaoa angustispora(和名無し)？ `obs-87fa70cf88bf584c315b452899c54a1426d784d2fb6aa9beede5b38d2a98a7c6` | `approve_research_photo` | 欠落1枚だけが手動退役対象。`research-f9cb62e956fa8604` の残5枚とケースを継続。元6枚の写真情報・ケース・同定履歴もcapsuleに保全 | `f272a6ef45f86f6faf587e18dc49204b2667dbecdc2519ca06cc3751ebcff6e9` |

通常14枚の承認manifestは**0個**。2件以外に人間承認を与えていない。
現在の同定registryは0件。元registryと対象ケースの同定履歴（現状ともに0件）を正確に保存し、架空の履歴を作らず、data/research-identifications.jsonを変更していない。

## 独立2回の本番観測

main `4b95bd9e9e44f225027858c5dd4fd4b7cd865f59`、公開baseline `757cbfc868452d3bb892849fce0e2122cd8c566e`。
`sync-deletion-audit` の `88bb6447cd07dbb012e145d2144af202b25a2be0` を既存GitHistory.loadで再検証。4イベント/4コミット、hash連鎖・連番・head・tree mode・1イベント1追記が正常。

- 初回 [38922030976](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38922030976): 10/17 00:13:04.820724 JST。
- 2回目 [38990433068](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38990433068): 10/17 10:20:57.840121 JST。
- 差は **10時間7分53.019397秒**。異なる独立ID、両方healthy、同baseline/protection/16 candidate fingerprints。
- 2回目artifact `12085295696` のZIP SHA256 `accb2c156baf16477a18486f526013c2033918bca666c9065e8f1e4c30fe9124` を照合。12ページ/112 entries/公開111/下書き1除外/完全取得/表現差0。
- 2回目の本番停止は通常14 eligible、研究2 pending、実適用0の安全停止。今回は新しい観測イベントを作成・転記していない。

## 正式管理室処理・差分プレビュー・隔離実生成

[専用GET-only CI 38992403765](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38992403765)で、製品コードをmainから変更せず、既存 `DeletionReview.refresh(live=True)` → `decide`（対象ごとに完全な写真IDを再入力）→ `preview_changes()` → `assert_fresh()` を実行した。
画面クリックの代行ではなく、管理室と同じサーバー処理を直接呼んでいる。各判断保存前・プレビュー前後に最新API/公開snapshot/全open PRの保護参照を再取得し、一致を確認した。
生成した公式JSONを手で組み立てたり編集したりしていない。

- 更新されたAPIも12ページ/公開111、下書き1除外、欠落16件、識別異常0。初回との候補fingerprint・保護hash一致。
- プレビューready=true。公式出力は上記2manifestだけ。`decision-preview.json` にbefore/afterを保存。
- 一時worktreeへ公式出力を適用し、既存 `generate_in_worktree(..., deletion_preview=True)` で実際のguarded generationを検証。
- 結果 **PREVIEW / automatic 14 / manual 2 / pending 0**。report内の applied 14/2 は隔離生成のシミュレーションであり、本番適用ではない。
- 写真893枚（既存906−欠落16＋新規3）、既存890写真ID維持。カワリハツはアーカイブ、Lanmaoaは残5枚、研究ケースは計66件を維持。Best Shot3件、未マージPR参照の検証成功。
- 317 HTMLページを実生成して検証。旧7枚はALREADY_APPLIED/退役計7/今回旧7枚適用0。旧7枚の出力検査PASS。
- 出力先置換なし、Pages公開なし、history_persisted=false。main/gh-pages/本番履歴refが開始前後で同一。

Artifact `12085313025` ZIP SHA256 `a70a067ae9bc120b62b603c5162a7a426e19a837ef9a241af8663cf8d526ad7d` をダウンロード時に照合。
`evidence.json` / `guarded-preview.json` / `decision-preview.json` と、公式出力そのものの2manifestを保存している。guarded-previewは無関係な分類待ち558件の個別一覧だけを省き、件数・全生成判定・保持結果を保存。完全なレポートは照合済みartifactに残る。
一時workflowは最終差分から除去。再現用 `verify.py` と実行済みコミット `2cc73bad8a830839f0b659365a1fffa3f2ba116e` は監査証拠として残す。
PRの保存にはGitHub連携を使用し、管理室のgh依存create_prによるremote書込みは実行していない。既存メソッドによる判断・previewと、同じ生成ゲート・差分allowlistを検証してから専用branchへ非force保存した。

## 回帰試験

公式manifestを適用したPython全946件PASS（80.32秒）。compileall、JavaScript全syntax/回帰試験PASS。承認ファイルを保存したhead `86d4583b37612bf99c2a0c03f8bef97d70312be3` のCIも全3種類成功：

- [Validate Admin Changes 38992708265](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38992708265)：Python全試験・compileall・全JavaScript・生成と公開分離。
- [Chromium 38992708276](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38992708276)：Best Shot92＋削除承認31＝123項目PASS。
- [Read-only API audit 38992708348](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38992708348)：新しい完全取得とguarded PREVIEWで自動14/手動2/pending0、history書込み0を再確認。artifact 12086230105 のZIP SHA256 `3be38b58a7ad65181a04e16fb3add1b32c0126443ad2a312e1a296f0cd3df114` を照合。

以降の差分は監査報告のみで、承認manifestと製品コードはこの検証済みheadから不変。詳細はVALIDATION.json。
製品コード、既存data全体、旧7枚manifest、公開workflowは変更していない。原API本文、下書き本文、認証情報、生成サイト、ローカル管理室状態はPRに含めていない。

## 残る管理者判断・制約

1. 本PRの対象2件・capsule・差分・最終CIをレビューし、マージはユーザーが別途明示許可した後に行う。本作業ではマージしない。
2. main反映後もfalseのまま新しい本番観測を行い、pending0かつDELETION_OBSERVATION_ONLY・Pages SKIPPED・実適用0を確認する。今のpending0は承認branchのプレビュー結果に限定される。
3. 証拠の期限（直近の連続healthy fetchが6〜72hの有効な組を持つこと）、再出現・ソース・参照変更は毎回再検査する。古いmanifestだけで安全ゲートを迂回しない。
4. その後に別の公開スイッチ変更Draft PRをレビューし、最終公開は別途明示許可が必要。今回はスイッチ変更PRを作成しない。
5. 既存アーカイブは元写真の**URL・完全な観察レコード・研究ケース・同定履歴**を保存する方式。画像バイナリの独立バックアップは作らない。元CDN画像の将来の配信継続は保証しない。
6. 非公開アーカイブはPagesからの非表示を意味する。capsuleは公開GitHub repositoryに保存されるため秘密化・完全削除ではない。

# 2026-10-16 旧Work救出記録

旧環境 `/workspace/scratch/d2f9454413ea/hatena-photo-gallery` にアクセスできた。
旧HEADは `132d306b46421ad405833b35bb6a0315184bed29`。管理室UI、承認処理、研究アーカイブ、日次adapter、workflowおよび関連テストが未コミットで残っていた。
元ディレクトリに対してreset/clean/checkout/commit/pushを行っていない。旧実行プロセスの停止状態は断定していない。

まず `.git` と未追跡・生成物を含む全123MBのディレクトリを別のtar.gzへ保全した。
アーカイブSHA-256: `43eb1610a7da9d1b9dbf2ed6325d05ce0f73642e84b24635e72a4d3cb7951e2c`。
別ディレクトリへ展開し、救出したコード23ファイルをローカルコミットした後、GitHub保存head
`2d1ba75622f8df5314b1bb2c476d53dbb7a0b4b7` のRECOVERY/監査記録も統合した。
ローカル救出履歴は `recovery/local-rescue-20261016` に保持している。

旧Workとの重複書込みを避け、独立branch
`feature/safe-photo-deletion-recovery-2026-10-16` / Draft PR #114 を作成した。
PR #113のbranchとmain/gh-pages/PR #111/#112は変更していない。
CLIによるpushは認証エラーで失敗したため、GitHubコネクタのGit tree/commit APIへ切り替えた。
作成したtreeがローカルコミットのtreeと完全一致することを確認し、既知のheadをexpected SHAとして非force更新している。

## GitHub保存チェックポイント

- `b80cc18a9ce8a059b1fd47703b8e0df38ba3ebd9`: 救出実装の最初の保全（未検証）
- `50419b06336454b6c42070664d657c7e36794fab`: 研究判断の差替え、識別/出力保護強化、独立日次監査。関連78試験PASS
- `7f174c52d556cfbb3bef987a92951fe5e3849de5`: 実ジェネレーターの独立確認後削除/翌日再実行、およびChromium CI

後続headと最終CIはPR #114を参照。元の調査/判定コードを作り直していない。
今回の運用用独立確認履歴追加、実対象の承認、マージ、公開、はてなブログへの書込みは0件。

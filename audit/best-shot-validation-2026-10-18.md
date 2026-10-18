# Best Shot CI生成経路の修正

対象警告: `observation_id must resolve exactly once: obs-a8b693fc53149d44b115b8bdcb259b815f9378f4b455d1ff167668da434a5b04`。

旧admin-validateは `python main.py` を直接実行していた。生のportal生成は記事ローカルパスを含むIDを計算するため、API順序・生成先が変わると公開済みBest Shot選択IDを解決できない。ページ生成関数は互換上best-effortなので、警告だけでCIが成功していた。これはPR #124時点でも存在し、40枚追加が原因ではない。

本番の `article_sync.SyncRun.reconcile` はAtom記事ID・URL・出現番号から公開済みIDを引き継ぐ。変更後の検証も同じ経路を通り、同一gh-pagesコミットから復元したsnapshotに対して `--safe-deletions --deletion-preview` で隔離生成する。Best Shot・研究室・退役・全ページ・全既存IDの検証が失敗すればCIも失敗する。承認待ちによる停止もValidateでは成功に変換しない。

選択12件・写真URL・写真ID・研究履歴・削除条件・日次workflowは変更しない。read-only権限、履歴非永続、候補出力破棄を確認し、監査reportだけをartifact保存する。マージ・公開・実データ承認は実施しない。

PR #124/#125とは独立し、mainを基点とした最小限の検証修正。各PRの最新mainへの再検証が必要。

## 検証結果

実装head `8aa8b85ac4e9f27dd6e19804a5a3ce1b6e5f3d51`:

- [Validate Admin Changes 39110078388](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110078388): SUCCESS。最新認証付き完全APIからguarded PREVIEW、Python **951 passed**、JavaScript構文・全回帰PASS。旧Best Shot生成警告なし。
- [Chromium 39110078393](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110078393): SUCCESS。
- [読み取り専用削除監査 39110078359](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110078359): SUCCESS。
- ローカルのworkflow・同期テスト69件PASS（cacheディレクトリを用意して実行）。

PR #125の独立した実データ隔離生成でも、上記IDは「ベニテングタケ」、2025年10月5日の観察記事、元画像URL `/20261004/20261004221847.jpg` として一意に解決し、Best Shot選択12件を保持した。IDの書き換えや選択データ修正は不要。

この追記は監査記録のみ。最終headのCIはPR Checksで確認すること。

# PR #139: 最終安全修正・追加回帰検証（2026-10-31）

前回監査は `audit/mobile-stars-shared-gallery-2026-10-31/REPORT.md` に保存したまま保持する。
既存PR #139 / `fix/mobile-stars-shared-lightgallery` だけを更新し、Draftを維持する。

## 開始状態

- GitHub再取得main: `8007a72708aff2dfa14e2e9638f44720bb449b76`
- 開始HEAD: `d903207f457042ba165633162bf2772cc20738a1`、3 commits、17変更ファイル
- Draft・未マージ・mergeable。直近10ワークフロー/12 jobsの全step成功を確認。
- 公開gh-pages: `3de2dc74d1d48813d9ed411e88e4ce74f3d9784c`。同じmainからの既存デプロイであり、この作業では変更しない。

## ① 画像読み込み待ち

**再現した問題。** 197枚の隔離ページに取得未完了の画像を置くと、ページのreadyStateがcompleteでもLightGalleryは未初期化のままだった。
`imagesLoaded(elem, callback)` は全対象画像が成功または失敗確定するまで待つ。404等で失敗が確定した画像だけならalwaysコールバックは完了するため、「1枚壊れただけで必ず永久停止する」という解釈は誤り。未完了・長時間待ちの画像が問題。

さらに、同梱2.8.3のthumbnail pluginは `init → build → setThumbMarkup` でストリップ画像を取得する。単にDOM準備直後へ移すと、カードのlazy指定を保ってもストリップが画像取得を先行する。

Best Shotだけ全画像待ちから切り離し、**最初の通常の写真操作時**に図鑑と同じ初期化関数を呼ぶ。最初の操作は同じクリック処理へ再送し、親ACKより先にLightGalleryを開かない。図鑑のimagesLoaded処理・レイアウト・初期化順は維持。高さ同期の既存ResizeObserverは画像完了やlightbox生成に依存しない。

追加試験は180枚を追加した197枚ページ、未完了画像/失敗画像、初回操作前に全lazy画像を取得しないこと、表示可能な写真の拡大・閉じる操作を320/360/390/430/1280pxで確認する。取得不能な写真そのものは正常画像へ置換せず、ライブラリの既存エラー表示と切替を維持する。

## ② 親通信前の操作

**危険な経路を再現。** 初期requestHeightが届かない環境で、認証付きphotoOpening要求0件のままLightGalleryを開けた。全環境で位置喪失が毎回発生するとは断定しないが、親が位置を保存するという設計条件を満たさない。

Best Shotの初回および起動後のcapture handlerで、埋め込み時は認証済みorigin/sourceからのoverlay対応とphotoOpeningProtocol=1を必須とする。未確立・非対応の旧親はvendor handlerを止め、既存href/targetの通常写真リンクへ進む。単独表示は親待ちをしない。

ACK正常時の順序・ID/origin/source照合・2秒タイムアウトは保持。拒否/タイムアウト時は準備をキャンセルし、同じ写真の**次の操作から通常リンク**へ戻す。非同期失敗時に勝手な遷移はしない。研究室写真の既存dialogと旧親互換経路は変更しない。

追加試験: 初回/遅延初期メッセージ、旧親、正常ACK、拒否、タイムアウト、連打、偽source/stale ACK、×/Esc、写真切替後の完全な位置復帰、通信不能時の通常写真リンク、単独表示、遅いscriptと遅い親メッセージを組み合わせた後の復帰。縦横切替・通常スクロール・履歴・ズーム・実ブラウザtouch入力は既存共通ブラウザ試験も維持する。

## ③ CDN遅延

**再現した問題。** 旧Best Shotの外部script応答を未完了にするとreadyState=loading、カード0件となり、HTMLパーサーがhead内で止まった。

`defer`をCDNに付けるだけではDOMContentLoadedまで外部応答を待つため、初期化の無期限待ちが残る。一方、mainとgh-pagesには同じ2.8.3 vendor一式（fontsを含む）がすでに存在する。新しいライブラリの追加・更新なしでこれを再利用し、Best Shotだけ同じタグ定数から同一originの順序付きdeferタグを導出する。不要になったBest Shot側imagesLoaded読み込みを削除。図鑑側CDNタグはバイト一致で維持する。

部分JS失敗やCSS失敗では拡大を横取りせず通常写真リンクを維持する。ChromiumではCSS取得失敗時にもtruthyなlink.sheetが見える条件を追加試験で確認したため、同一originのCSS規則が読み取れることも確認する。

追加試験: 通常、script低速/未完了、core/zoom単独失敗、CSS失敗、全依存遮断、外部script要求0件。図鑑の通常拡大は既存試験で継続。図鑑側の既存CDN障害時のパーサー待ちはこのPRの変更で増減せず、今回のBest Shot局所修正の対象外として残る。同一origin自体が不通なら写真も取得不能であり、通信成功を保証しないが通常リンクは残る。

## 検証記録

- `before-probes.json`: 開始HEADで3点を再現した観測記録。
- `local-core-safety.json`: 中間ローカル追加試験 2,849 assertions PASS（30条件）。
- `local-timing.json`: 追加の低速script・親メッセージ遅延組合せ 85 assertions PASS。
- focused Python 44 PASS、認証/高さ/ナビゲーションNode 59 PASS、既存共通ブラウザの中間確認1,180 assertions PASS。
- これらは隔離SVG画像/メッセージ故障注入を使う。スター追加を実サービスへ送信しない。Android実機・はてな未公開保存・本番反映の成功ではない。
- 最終合格は**修正後の最終HEADのCIだけ**で判断する。最終run/job/step・コミットSHA/tree・スクリーンショットはPR説明/Actions成果物に追記する。旧コミットCIや上記中間値を流用しない。

## データ保護

`protection.json` に独立比較の件数とSHA-256を収録。開始HEADのGit内容と作業ツリーの303ファイルを比較し、最新mainのdata/同期承認/管理室/コメント/親候補/vendorも別途比較して一致。

| 対象 | 実測 |
| --- | --- |
| 公開写真 | 933 |
| Best Shot | 17（公開全年度ページのselection ID集合とも一致） |
| 年間Best指定 | 1 |
| NEW!通知定義 | 14（現在表示されるバッジ数とは区別） |
| 研究室 | 66 |
| 退役 | 7（公開同期snapshotのretirement台帳） |
| master / sources | 141 / 419（mainと公開portalの両方） |
| 研究室コメント | enabled=false、API URL空欄 |

保護303ファイルのパス別SHA-256集合のdigest:
`b4ecea3b24d347e82e3ed3b904b5777e99768fb49a49aa808d7cbe26c4a9143c`

公開portal全体のSHA-256（写真ID/URL/EXIF等を含む）:
`32a9d26af57f4a99df07ecc6820bbca9c908f0664d47632084f373db52eec929`

## 変更区分・停止条件

製品コードは `assets/gallery.js`、`best_shot_ui.py`、`gallery_dependencies.py` の3ファイルだけ。スターのコード/CSS、図鑑データ、vendor自体、親3欄は今回変更しない。

テスト: 共通ブラウザの準備完了条件/ローカル依存遮断を実態に合わせ、専用安全試験・保護比較・タグ順序検証を追加。従来のカード全文比較も新しい正確な依存タグを検証してから比較し、安全条件を削らない。workflowは追加試験と成果物保存だけを追記する。

旧監査と証拠は保持し、別フォルダーへ今回の監査を追加する。Draft・未マージで停止。本番生成・Pages公開・はてな保存/復元・Cloudflare変更・実サービスのスター追加は行わない。

最終判断でAndroid実機未確認を必ず区別する。実機確認とmainマージ/Pages公開の承認は次段階。

根拠: https://imagesloaded.desandro.com/ （callback/always仕様）、リポジトリ同梱 `lightgallery/lg-thumbnail.min.js` / `lightgallery.min.js` 2.8.3（実際に使用する版。最新3.xドキュメントの追加仕様は根拠にしない）。

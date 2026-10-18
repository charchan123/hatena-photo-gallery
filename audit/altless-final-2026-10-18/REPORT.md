# PR #123・#124・#125 引き継ぎ後の最終安全監査

**最新結果は末尾「最新main統合後のマージ前監査」を参照。** 以下の既存章は#124/#126公開前の記録として保持する。JSONは `latest_validation_key` が指す `main_integration_2026_10_18` が今回の結果。

## 保存成果と現在の基準

main `bb5ddbd61865117b2a58b12e30b81e80ac628946`。gh-pages `3e6d278b877e8e153dc25a8753505eddeb96a5ce`（引き継ぎ記載のf29e355から更新されていた）。Git履歴 `sync-deletion-audit` は `82a465fd297a23b343aed6feed3590f8b9bf7a71` を読取確認。

- #123: Open/Draft、head `789994cffcf04cc9d8ba52ef1ba4b2df45a0499b`。将来の通知表示レイアウト4ファイル。変更せず独立維持。
- #124: Open/Draft、head `07d199f9aed14a0570cd6e79ca7c79964083ebf0`。taxonomy2名称と回帰3ファイル。変更せず維持。
- #125: Open/Draft。#124を含む40枚のtaxonomy・複数種参照実装を再利用し、以下の表示修正と受入監査を追加。
- #126: main基点の独立Draft。Best ShotのCI生成経路を修正。写真・ID・選択データは変更しない。

## 収録判定

認証付き完全API取得12ページ、112エントリー、非公開下書き1件除外、公開111記事、pagination_complete=true。APIへの操作はGETのみ。下書き本文をartifactに保存しない。

直近7記事は73画像、既収録23枚、未収録50枚。最新guarded隔離生成は **893 → 933枚（追加40枚）**。既存893件のID・gallery_name・srcを全件比較し保持。欠落0、URL変更0、削除候補0、保護対象削除候補0。

| 未収録50枚の処理 | 枚数 | 内容 |
|---|---:|---|
| 図鑑の登録候補 | 40 | #124の4枚を含む。本文・taxonomy・既存安全条件を通過 |
| 複数種のHTML参照専用 | 3 | 同じ画像URLを両方の詳細ページに表示。登録件数・観察IDは追加しない |
| 保留 | 6 | オオジョウゴタケ？3、フモトニガイグチ1、アブラシメジモドキ1、ニガイグチの仲間1 |
| 植物として除外 | 1 | フジアザミ、taxonomy_non_mushroom |

40枚の名称別内訳は同梱 `summary.json` の `additions_by_name`。ブドウニガイグチ2・マツタケ2が#124、残り36が#125。

アンズタケ(広義)は最新本文でも修正後表記を2枚から検出した。アンズアケ(広義)は互換aliasのみで新ページなし。既存アンズタケ4枚は名前・ID・URLを一切変えず、広義名に統合しない。

## taxonomyと根拠

mainとの差分31名称＝#124の2＋外部名称資料26＋project_seed2＋植物1。合計79（キノコ75、非キノコ4）。重複・alias衝突・広義名の区別・曖昧な名称の不採用は既存回帰を再利用して確認。

追加名称の根拠URLは先行監査 `../recent-altless-mushrooms-2026-10-18.md` を維持。石川県・林野庁・環境省・京都府の原資料、出版元図鑑の名称表示、地域きのこ会自身の記録を確認した。キンチャワンタケは林野庁の同じ写真一覧にも掲載。これは名称・分類の根拠で、ユーザー写真の個体を独立に同定する証拠や食用判断ではない。

保留2名称の追加資料を発見したが、この作業では写真を自動確定・追加しない。

- フモトニガイグチ: 京都府菌類目録 https://www.pref.kyoto.jp/kankyo/mokuroku/bio/fungi.html
- アブラシメジモドキ: 山梨県森林総合研究所研究報告（柴田、2006） https://www.pref.yamanashi.jp/documents/67330/byfri_2006_25_13_98_shibata_part3.pdf

オオジョウゴタケ？の疑問符や「ニガイグチの仲間」を除去して推測同定しない。追加2名称を将来taxonomyへ登録する場合も、記事の個体判断・既存名との衝突を別途確認する。

master141種・sources419件は公開データと完全一致。feature facets・承認/保留ルール・食毒情報を変更しない。知識未整備のブドウニガイグチ等は「図鑑情報は現在整理中です」「名称や根拠資料を確認できた情報から順次追加しています。」を維持。

## 複数種写真と管理室

直近はニガイグチモドキ＆ヤマドリタケモドキ2枚、ムラサキヤマドリタケ＆アカヤマドリ1枚。双方の詳細HTMLに同じURLが各1回だけ表示される。portalは933件・URL933個で重複登録なし。トップ・検索・観察記録は登録写真の件数を維持する。

全記事では上記3枚に加え、過去記事の登録済み写真2枚にも他方への参照が追加される。元のgallery_name・観察ID・URLは保持する。

今回の修正:

- 参照専用表示と登録件数の関係を詳細ページに明記。
- portal未登録の参照写真はサムネイルと拡大表示の両方でお気に入りを無効化。登録済み写真の星は維持。
- 新しい生成先で元記事から参照が消えれば両方の参照も消えること、第三の種類への誤関連付けを拒否することを回帰検証。

管理室は既存SyncReviewを使い、同じ最新GET取得から73行を作成。未収録フィルタで仮同定3枚・根拠待ち2枚・曖昧見出し1枚・複数種3枚・植物1枚を確認できる。植物はnon_mushroomとして自動追加対象外。未収録・保留・人間分類・除外の既存機能を重複開発していない。人間による保留と自動判定上の未収録は異なる状態。今回、判断・承認・採用manifestは作成していない。

40枚はまだ公開前であり、管理室の既存比較では「以前からの確認待ち」等として表示される。未収録フィルタ件数だけを公開への追加件数と解釈しない。guarded PREVIEWの追加40件が実際の適用判定。

管理室の同期一覧はPCで確認した。既存のスマートフォン用レイアウトは同期一覧では列幅が狭く、表示改善の余地がある。今回の公開ページ4種のスマートフォン検証とは区別し、写真の判断操作はPCで行うことを推奨する。データ処理・保留・除外の機能を変更する必要はない。

## Best Shot・研究室・削除保護

Best Shot参照12件、研究ケース66件を本番と同じSyncRunの最終検証で保持。旧公開ベストショット記事7枚の退役はALREADY_APPLIED、今回0枚、合計7枚。退役済み記事の再収録・生成物への復活を既存退役検査が拒否する。

Best Shotの既知の警告は、通常ValidateがID引き継ぎなしのmain.pyを直接実行していたことが原因。独立Draft #126で本番と同じimmutable baseline＋article_syncのPREVIEWへ修正し、ページ・参照検証失敗をCI失敗にする。該当ベニテングタケIDは実データで一意に解決。12件の選択データ修正は不要。詳細は#126の監査記録。

毎日1回のgenerate.yml、削除の独立複数回確認・6〜72時間条件・承認履歴・研究アーカイブ・Git監査履歴は変更しない。すべてpreviewでhistory_persisted=false。main/gh-pages/監査履歴への試験書込みなし。

## 検証と残る作業

検証結果・Actions・artifactのdigestは `VALIDATION.json` に保存する。監査用の一時workflowは最終差分から除外し、再現用capture.py/browser.cjsと公開済み情報だけの監査結果を残す。

- Python **962 passed**、JavaScript構文・全回帰PASS: https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110875937
- 既存Chromium回帰PASS: https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110875948
- 最新API読み取り専用削除監査PASS: https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110875932
- 実API隔離生成＋実ページChromium **310項目PASS**: https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110875955

実ページは1280px/390px、実CDNの複数種画像とBest Shot全12件のデコード、全選択ID、未登録参照の拡大表示のお気に入り無効化、検索の正規リンク、観察記録83記事分の枚数・種類数を確認。管理室は実際の読取行をGETのみで表示し、判断書込み0。スクリーンショットを目視確認した。一時workflow削除・監査追記後の最終headはPR Checksで確認する。

#126最終head `c208edec1df0439d80eb9766ce97df78532493cb` もPython951件・JavaScript・Chromium・最新APIの3系統SUCCESS。通常Validateに旧Best Shot警告なし。

- https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110435385
- https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110435477
- https://github.com/charchan123/hatena-photo-gallery/actions/runs/39110435314

推奨順は **#126 → #124 → #125**。#123は独立。各マージはユーザー承認が必要。#124反映後は#125を最新mainに対して差分・CI・guarded API・保護件数を再確認する。#126反映前の#125の通常Validateには旧警告経路が残るため、緑だけで公開を判断しない。

mainへのマージは既存generate.ymlのpushトリガーを起動し得る。公開を別判断にする場合は、マージ前に管理者が公開ゲートの状態を確認し、公開しない運用を確保する。今回スイッチの読取はコネクタの許可endpoint外で取得できず、変更もしていない。最終公開は実施していない。

## 最新main統合後のマージ前監査（2026-10-18 JST）

### 基準と統合

- main: `bc9e3d4e7adb62b8e8da8e26a9009f07db5fb5a2`。#126/#124はマージ・公開済み。
- gh-pages: `b265b70b8ba872751d26dd38201d91fbe023f90e`。本番897枚・Best Shot12・研究66・退役7、削除候補0。直近本番同期 [39129092368](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39129092368)、Pages [39129152305](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39129152305) はSUCCESS。新たな日次同期による基準変更なし。
- PR #125変更前: `1a28fb326fdc7f0d801263af341ce9748e5f0d23`。main統合commit: `3dfd883a1c8b98263018078f9ffd24800bab7d06`。親は変更前headと最新mainの2つ。force/rebase/squashは使わず、既存Draftブランチを継続。
- #124のsquash重複によりtaxonomyとテスト2件が競合。最新main側の3ファイルが保存済み#124とbyte-identicalであること、mainの50 taxonomy項目が#125の79項目に完全一致で含まれることを確認して解消。#124の2名称・4枚を再追加するコードは作っていない。
- #126のguarded CIをそのまま取り込んだ。`.github/workflows/admin-validate.yml` と `generate.yml` は最新mainと完全一致。本番workflow・公開スイッチは変更していない。PR #123も未変更。

### 最新APIと既存保護

実装検証head `329c45ef0cbea2dc5e2c616781b89a3a4f9bd360`。認証付きGET完全取得は12ページ/112エントリー、下書き1件除外、公開111記事/980画像、pagination_complete=true。固定した公開commitと最新取得を照合し、公開記事のID集合・updated hash・画像URL hash/出現番号・DOM順序は全件一致。取得・生成は隔離し、履歴refへの書込みなし。

| 項目 | 最新確認結果 |
|---|---:|
| 公開済み写真 | 897 |
| 今回の新規登録候補 | 36（27名称） |
| 隔離生成候補 | 933 |
| 既存ID・名前・URL・capture/EXIF・記事情報保持 | 897 |
| 欠落・意図しない改名・URL変更・削除候補 | すべて0 |
| Best Shot参照/選択 | 12 |
| 研究ケース/各ケースの写真ID・URL対応 | 66、完全一致 |
| 退役済み写真 | 7、復活0、生成物検査PASS |
| 既存の自動追加履歴 | 7件を完全保持、新規36件のみ追加 |

新規36件はすべて本文のaccepted_subject、taxonomy canonical_exact、high、confirmed_named_mushroomの既存条件を通過。ID/URLは一意。前回保存候補の同じ36写真とIDが一致する。#124の4枚は既存897件としてID・URL・EXIFを保持。36件のID・名称・記事・URL・分類根拠は `summary.json.main_integration_2026_10_18.new_photos` に永続保存。

記事情報の比較では隔離生成の内部パス `article_path` だけを除外し、記事ID・出典URL・タイトル・公開/更新日時・カテゴリー・抜粋を全897件で一致確認した。

snapshotの分類記録変更は71件。内訳は **新規収録36、既存写真の分類判定更新34、フジアザミの非キノコ判定1**。34件はtaxonomy追加で機械的な分類根拠が更新されるもので、写真の改名・差替え・生物学的な再同定ではない。画像の追加・削除や記事更新ではないことを全980記録で比較した。既存写真名・ID・URL・EXIF・出典情報は変わらない。

master141・sources419・feature facets/承認状態・Best Shot選択データ・研究履歴・削除承認データは最新mainから変更なし。退役ledgerと削除receiptは公開snapshotと完全一致。Git監査履歴branch `9b53922a4c265a3436b6556f0596a0fa60dc0962` は読み取りのみ。

### 表示と保留

- 既存310項目の実ページ検証を再利用・補強し **Chromium599項目PASS**。1280px/390pxの双方で新規36枚すべてを実CDNからデコードし、詳細ページに各1回表示されることを確認。
- 複数種は直近3枚が双方の4種類のページに表示され、過去の登録済み2枚も参照表示。portal933件/URL933個を維持し、検索・観察記録83記事分の件数は登録データと一致。第三種の誤関連付け防止と元画像消失時の参照除去は既存回帰で確認。
- 未登録参照はサムネイル/拡大表示のお気に入り無効。過去の登録済み参照2枚は拡大表示の星を操作し、隔離localStorage保存→観察ノート表示を確認して消去。本番・管理室への判断POSTは0。
- Best Shot全12選択・実画像、研究66カードと全写真URLを両画面幅で確認。退役写真は356ファイルの検査で不在。旧9/2記事を復活させない既存ゲートは変更なし。
- 保留6枚とフジアザミ1枚は新規収録しない。アンズアケ(広義)はaliasのみ、実APIは修正後のアンズタケ(広義)2枚。既存アンズタケ4枚は別名のまま保持。名称資料を個体同定・食用保証に流用しない。

### テストと承認待ち

- Python **963 passed**（ローカル、CI）。Python構文検査PASS。JavaScript20ファイル構文・全11回帰suite PASS。分類辞書、既存ID、Best Shot、複数種の既存正負テストを含む。
- [Validate Admin Changes 39131628953](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39131628953): SUCCESS。#126の本番相当PREVIEW経路を使用し、旧Best Shot警告なし。
- [Deletion review browser regressions 39131628970](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39131628970): SUCCESS。
- [Read-only deletion audit 39131628956](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39131628956): SUCCESS。
- [実API隔離生成・実ページ599項目 39131628945](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39131628945): SUCCESS。artifact `12138431646`、SHA-256 `9f6b5b0b8c030ad10e1953325ea32d51b303b0b914eea1f2789ab617aa3d2244` を再計算して一致確認。

既存監査を保持して本節とJSONの同名keyを追記。受入用一時workflowは最終差分から除外する。最終監査追記headの3CIはPR本文/Checksに保存する（自己参照を避けるため本ファイルにそのcommit SHAは書かない）。

重大な不一致・未保存の実装修正なし。残る保留6枚と管理室同期一覧の既存モバイル列幅制約は従来どおり。マージ直前にmain/gh-pages/APIの再変化を確認する必要がある。**検証基準に変更がなければマージ可能と判断し、Draftのままマージ承認待ちで停止する。** マージ・本番再生成・Pages公開にはユーザーの別途明示承認が必要。本作業では一切実施しない。

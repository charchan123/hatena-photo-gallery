# PR #123・#124・#125 引き継ぎ後の最終安全監査

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

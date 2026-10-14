# 意図的な記事削除と未承認の写真欠落：停止監査（2026-10-14）

**判定：BLOCKED_REVIEW_REQUIRED。削除移行の実装・承認manifest・Draft PRは作成しない。日次同期を再開できない。**

監査資料だけを独立ブランチへ保存する。本番データ、同期コード、旧移行履歴、ワークフロー、PR #111/#112は変更しない。mainへのpush、merge、Pages公開、Hatena書き込みはしない。

## 固定した基準と照合範囲

- main: `4f953c7f0723f8ab44d72a12fcaf00579776ee66`
- 直前の成功済みgh-pages: `757cbfc868452d3bb892849fce0e2122cd8c566e`
- snapshot SHA-256: `7212389cdc412bf3577c78c3e0be5c91926ecc398930427b775f2459071adcb0`
- 最終成功: 2026-10-13 06:12:37 UTC（15:12:37 JST）。公開906枚、110記事、記事内画像976件。
- 失敗run: [38405555480](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38405555480)。報告時刻2026-10-13 13:31:10 UTC（22:31:10 JST）。公開候補891枚、109記事、記事内画像961件。
- 失敗artifact: `article-sync-report-38405555480-1`、ID `11819246247`。ダウンロードZIPのSHA-256がGitHubのdigestと一致。
- 認証付き取得の既存記録：PR #112のread-only CI run `38413084049`でも、2026-10-13 14:24 UTCに111件取得・画像961件・候補891枚を記録。CI成功は日次同期の削除安全ゲート成功を意味しない。

## 15枚の内訳と承認状態

|元の記事|欠落写真|枚数|承認|
|---|---|---:|---|
|[2025年9月2日 静岡県掛川市](https://exsudoporus-ruber.hatenablog.jp/entry/2025/09/02/234739)|Lanmaoa angustispora|1|ユーザーが意図的な記事削除を確認。今回の承認範囲|
|[2025年9月13日 富士山(山梨県)](https://exsudoporus-ruber.hatenablog.jp/entry/2025/09/15/103432)|ミヤママスタケ、カワリハツ？、アカツムタケ、オオキツネタケ、ケシロハツ、ホテイシメジ、スギタケモドキ、コゲエノヘラタケ、シロヌメリイグチ、ハナイグチ、キサマツモドキ|11|未承認|
|[2025年7月5日 静岡県浜松市](https://exsudoporus-ruber.hatenablog.jp/entry/2025/07/08/230930)|不明アワタケ|1|未承認|
|[2025年6月29日 静岡県浜松市](https://exsudoporus-ruber.hatenablog.jp/entry/2025/07/06/222231)|ミドリニガイグチ|1|未承認|
|[2025年6月21日 静岡県静岡市](https://exsudoporus-ruber.hatenablog.jp/entry/2025/06/22/133910)|アイタケ|1|未承認|

[missing-photos.csv](missing-photos.csv)と[missing-photos.json](missing-photos.json)に、15枚すべての元記事・Atom ID・観察ID・画像URL・キノコ名・hash・承認区分・確認時刻を収録。

承認済み記事はHTTP 404。旧Atom記事IDのhashは指定の`f4c1c839abafe71eb16494d0d921cd96df6cbf32aefce8eee19a8807a90a923e`と一致。対応する観察IDは`obs-10f29e7b04472ecb1e1d4fccfb060889cfa1dfc2012922b4c299d483a8647f01`、画像は`20250902233255.jpg`の1枚のみ。

他4記事はHTTP 200で記事自体は公開されているが、記載した旧画像URLが本文にない。理由・編集意図・削除承認は確認していない。本文の写真品質に関する記述だけでは削除を承認しない。

## 証拠の厳密な区別と制約

現在の公開本文で確認した欠落15枚の状態は、named_mushroom 5 / ambiguous 8 / conflict 2。これを旧snapshotから除外した投影は、失敗報告の全状態別件数、記事減少1、画像減少15、新規0、更新0、分類変更0と一致する。

ただし失敗artifactに保存されているのは全件の最新inventoryではない。review状態の10枚はpending_classificationから個別の欠落を直接照合できるが、named_mushroomの5枚について、失敗時点の個別削除キーが保存されていない。5枚のID特定は、現在の公開本文の欠落と状態別集計の一致による照合であり、失敗時点の認証付きAtom本文そのものを照合した証明とは区別する。

この環境にHATENA認証情報がなく、`live_capture()`は`LOCAL_HATENA_CREDENTIALS_UNAVAILABLE`で停止する。新しい認証付きAPI全件取得・ライブ同期生成は未実行。公開本文の補助GETは旧公開写真に対応する89記事を対象に、HTTP 200が57、404が1、ReadTimeoutが31。取得失敗を削除とは判定していない。89記事全体の現時点での完全な保持や、さらに別の変更がないことは保証できない。原文HTML・下書き・資格情報は成果物へ保存せず、対象の画像URL一覧・HTTP状態・本文hash・確認時刻を保存した。

この制約も、個別削除移行の実装へ進まない理由となる。

## 保護対象

- main Best Shot 3件とPR #111の12件：すべて基準906枚に1件ずつ解決し、欠落15枚とのID交差は0。年間Bestの指定も維持。
- PR #111 head: `4448c3431a1c275ca686e9e2a0a7736fc67f0841`。PR #112 head: `a8d5792ec2e62e3a630124743c0bffc1d8fa48a6`。両PRに書き込み操作は行わない。
- 不明キノコ研究室：未承認のカワリハツ？1枚が`research-940496f1ccdb136f`を参照し、このcaseの写真は1枚だけ。無承認の削除はcaseを失わせるため保護上のブロッカー。
- 同定履歴：現行registryは0件でvalidator成功。registry自体は変更なし。
- 分類データ：141種、419出典、373特徴割当、overlay 0を維持。食毒・学名・分類を補完・変更していない。
- 公開906観察ID・旧migration・snapshotのretirement receiptは変更なし。

詳細：[protection.json](protection.json)。この確認は欠落15枚との参照競合監査であり、31記事の取得失敗もあるため、最新API全件に対する参照検証を実行済みとは扱わない。

## 既存契約と、再開に必要な実装

既存`sync_retirement.py`は、2026-10-12に承認された別の下書き記事からの7枚退役のみを固定manifest/hashとreceiptで検証する。今回の1枚に流用したり、manifest/hash/履歴を書き換えたりしない。

現在の`article_sync.py`はinventoryの削除を個別承認より前にfail-closedで拒否する。今回の移行が必要になった場合は、旧7枚receiptを保持する独立した削除移行契約と、以下の証明が必要になる：

1. 最新の認証付き全件取得と、記事・全画像・全観察IDの再照合。
2. 未承認14枚の編集意図確認。復元するか、明示的に個別承認するかを写真単位で判断。カワリハツ？の研究室case維持／退役方針も別途確認。
3. baseline gh-pages commit、snapshot/hash、観察ID、画像URL/hash、Atom記事ID/hash、記事URL、exact件数を結ぶ追記専用manifest。承認対象外の差分があれば必ず停止。
4. 証明済み対象だけを比較用inventoryとpreviousへ除外してから、元の新規写真・URL・重複・名称・参照・ID継続性ゲートを実行する。旧retirement、name migration、manual adoptionの合成時に退役対象を復活させない。
5. 再実行時のreceipt検証、対象の再登場の保留、出力への旧記事・ID・URL漏れ検査。対象以外の旧観察IDと本番設定を保持。

これらは設計上の要件だけで、実装や承認manifestを今回作ったものではない。

## 検証結果と停止条件

- 全Python：840 passed。
- Node回帰：10スクリプトPASS。JS構文・Python compileall成功。
- 公開snapshot・Phase 4C.9 production validator・Best Shot 3件/12件・同定registry：PASS。
- 隔離した既存ゲートの投影試験：承認済み記事1枚だけを除外した905枚候補も、観測欠落15枚の891枚候補も、現行コードは`DELETION_OR_URL_CHANGE_REQUIRES_REVIEW`で拒否。期待した停止を確認したのであり、本番同期SUCCESSではない。
- 投影試験は公開snapshotと証拠に基づく隔離モデル。新しいライブAPIのreplayではない。

[validation.json](validation.json)、[baseline-and-reconciliation.json](baseline-and-reconciliation.json)、[logs](logs/)に記録。

**人間の判断が必要な対象は上表の未承認4記事・14枚とカワリハツ？の研究室case。確認が済むまで、同期の成功扱い、実装PR作成、マージ、公開をしない。**

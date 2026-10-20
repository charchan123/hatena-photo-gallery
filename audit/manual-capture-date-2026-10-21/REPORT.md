# Best Shot 手動撮影日 監査（2026-10-21）

## 分離と開始基準

main `78d8cb8249d45185869a22939d84139fee3833ba` を起点に `feature/best-shot-manual-capture-date-20261021` で実装。PR #131の変更を混入していない。Best Shot CSS・トップCSS・スター・日次同期・削除判定・公開workflow・管理室下書き保存とGitHub CLI処理はmainとバイト単位で同一。

gh-pages `e74c709bcd25f1f68584222aeef1bbe8613ff03b` を別途取得し、最新remoteも同一であることを確認。公開写真933／既存選択16／通知13／研究66／退役7／master141／sources419／削除候補0／公開111記事・980画像が現在の基準。元の `capture.date` がない公開写真は30枚だが、今回それらの写真の撮影日を推測・登録していない。UI試験は架空の写真ID・画像・日付だけを使用した。

## 日付の取得経路と保存契約

現行portal_data._captureはEXIFキャッシュの日付を正規化してcapture.dateへ格納する。新しい判定はEXIFの有無を直接使わず、有効なcapture.dateがあるかを見る。EXIF以外の確かな経路で設定されたdateも従来どおり扱う。

schema version 1を維持し、Best Shot選択レコードだけに次の任意項目を追加。既存16件は書き換え不要。

| 項目 | 用途 |
|---|---|
| manual_capture_date | 厳密なYYYY-MM-DD。年月分類・順序・年間指定・公開日付に使用 |
| manual_capture_date_origin | 管理室が元写真の日付未確認を検証して発行するowner_confirmed_undated_source |
| manual_capture_source_ack | 後に確認された元写真の日付との差を、管理人が明示確認して維持した場合の元日付 |

写真ID・URL・元capture・EXIF・記事・全体ギャラリーは無変更。公開日の流用、ファイル名からの推測、自動日付補完はない。manual_capture_dateのnullや空文字は登録値として拒否。更新APIの明示的なnullだけは「新たに有効となった元写真の日付を採用」の命令として使い、手動日付と由来情報を選択レコードから除去する。

共通Python validatorは形式・実在日・うるう年・型・JSTの今日を超える未来日・由来の整合を検証。フロントもUTCによる暦の検証とJSTの今日を用い、日付表示・年月はISO文字列から扱ってタイムゾーンで日をずらさない。有効な元日付がある写真への新規手動上書きはChangeSetで拒否。由来なしの手動日付は共通validatorも拒否する。既存の未知項目禁止は、指定した3項目だけを加えた厳密なallow-listのまま。

## 後から元日付が確認された場合

手動日付を有効日付として維持し、resolved modelにowner_manual・source_capture_date・capture_date_conflict・capture_date_review_requiredを出す。元captureも手動値も自動変更しない。管理室一覧に両方の日付と警告を表示する。

- **元写真の日付を採用**：明示確認後、共通validatorで年月・重複順序・年間Bestの年を再検証。衝突した場合は保存せず、確認ダイアログ内に理由を表示。
- **手動日付を維持（確認済み）**：今回の元日付をackとして保存。元日付が再度変われば警告が再び必要になる。

日次同期の参照validatorを使ったテストでも、元日付が後から現れてもID・URL・Best参照を維持して通ることを確認した。競合のために同期全体を停止させたり、写真を削除したりしない。年間Bestの年が変わる編集は従来どおり拒否し、自動修正しない。

## 管理室・保存

通常の撮影日がある写真では手動欄を隠す。日付がない写真だけdate入力を表示し、未入力・無効・未来日は保存不可。既存の手動選択を再編集すると保存済み日付を復元する。後日元日付が現れた手動選択では手動欄を読み取り専用にして由来と元日付を表示する。

写真差し替え時は古い手動日付・由来・ackを除去し、別の未確認写真には再入力を必須とする。かな・カナ検索、プレビュー、ID、順序の整数制限、枚数無制限、保存中ロック、失敗時入力維持を保持した。新規date欄に専用hidden CSSを設け、一般labelのdisplay指定により隠せなくなることも防いだ。

Best ShotとNEW!通知の原子的な保存はPR #130の既存トランザクションのまま。DraftStoreの形式・サイズ・hash・atomic replace・再起動復元・main変更時の安全停止は変更していない。新しいフィールドもfiles()からそのまま保存・復元・PR用JSONへ渡る。GitHub PR writerの隔離テストで実際の保存JSONに日付と由来が残ることを確認した。

## 検証と画面

[日付未入力](date-empty.webp)／[正しい入力](date-valid.webp)／[未来日で拒否](date-invalid.webp)／[後日の元日付警告](source-conflict.webp)／[採用時の順序競合エラー](source-reconcile-error.webp)。すべて実際の管理室とHTTP APIを、合成データ・一時保存先・127.0.0.1だけで動かした画面。元写真を登録した画面ではない。

主要Python回帰99件PASS（新機能25件を含む）。JavaScriptの新日付・月内順序helperと既存回帰、構文検証PASS。実管理室Chromium21項目PASS。

| 要件 | 検証 |
|---|---|
| 元日付あり・EXIF以外のdate | 従来どおり登録、手動欄非表示 |
| 未入力・空・null・数値・不正形式・2/30・非うるう年・未来 | Python／JS／実HTTPで拒否、既存状態維持 |
| 正常日・うるう年 | 2024/2/29・2000/2/29を受理、年月と公開表示を検証 |
| 順序・年月・枚数 | 同月重複・写真重複を拒否、年月変更を再検証、上限なしを維持 |
| 年間Best | 手動日付で指定可能、撮影年不一致・無断移動を拒否 |
| 写真差し替え | 古い日付を継承しない、別写真は再入力 |
| 再編集・再起動 | 実UI／実ローカル下書きで復元 |
| PRデータ | writerへ渡るJSONに手動日付・由来、元dataファイルは無変更 |
| 後日の元日付 | 手動値維持・警告・明示採用／維持・安全な日次参照確認 |
| 既存16件 | mainの旧コードと公開モデル全体が完全一致、JSONバイト不変 |

全件Python・既存Chromium・スター・読み取り専用API・追加実画面を、最終コミットの独立CIでも必須とする。最終SHA・新Draft PR URL・CIの全実行URLと結果はPR本文に記録する。ローカル全件試験では既存同期フィクスチャのOUTPUT_INTEGRITY_ERRORが出たため合格とは扱っていない。主要99件と新機能21項目の結果を分け、クリーンなCI checkoutで全件合格を確認してから完了報告する。安全判定・既存条件を緩めていない。

## 実装ファイル

- best_shot_ui.py：任意3項目・共通date解決・由来と競合メタデータ。
- admin/core.py：新規日付の許可条件、写真差し替え時の除去、年間Best、明示採用／ack。
- admin/server.py：管理室状態に日付解決メタデータを追加。保存トランザクションは不変。
- admin/static/admin.js・admin.css：date入力・近接エラー・出典・競合確認とhidden表示。
- tests/test_manual_capture_date.py・.js：暦、型、順序、年、復元、PR writer、安全参照。
- tests/test_best_shot_ui.py：schema v1の厳密allow-listに任意3項目を追加。
- tests/browser/manual_date_server.py・manual_capture_date.cjs：一時データだけで実管理室を検証。
- .github/workflows/manual-capture-date.yml：読取専用の追加CIと証跡保存。
- このaudit：画面、ログ、独立保護照合。

## マージ順序と注意

推奨はPR #131を目視確認して個別承認・マージ後、この機能PRへ最新mainを通常マージで取り込み、再検証して別途承認する順序。両者はbest_shot_ui.pyを変更するため将来の統合確認が必要。#131は_cardだけ、このPRはvalidatorと日付解決が中心で、CSSは別PRに混入していない。

機能承認・mainへの導入前に新形式の選択JSONだけを先にmainへ入れない。古いvalidatorは新任意フィールドを受理しないため。実際の30枚に日付を推測して追加していない。既存16件の選択・順序・コメント・年間指定、通知、研究・退役・知識・同期・削除承認を変更しない。

Draft・未マージ・未公開で停止。main直接push・force push・自動マージ・本番再生成・Pages公開・本番スター追加削除・管理人未選択のBest追加を実行しない。

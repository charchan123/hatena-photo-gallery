# 正式トップ切替準備：監査（未公開）

確認日：2026-10-24 JST。**本番切替・設定保存・記事投稿・Cloudflare操作は実施していません。**

本作業の準備コードと手順書は作成しましたが、現行管理画面の生の設定が未取得のため、公開可能との最終判定は保留です。バックアップ照合、実はてなStaging、Android実機の受入れを残しています。

## 開始状態と保護

- main `090eac16c25129695452a10a076532c752d8bd27`
- gh-pages `8cef60f355790e1a57a97b324e901ca816c8aed3`
- 日次同期 [2026-10-23 run 39898325765](https://github.com/charchan123/hatena-photo-gallery/actions/runs/39898325765)：成功。10/22も成功。
- [baseline.json](baseline.json)：公開データの独立集計、ID/URL/captureのhash、保護ソース71ファイルのhash、公開DOMの取得元/sha/native件数を保存。

| 保護対象 | 現在値 |
|---|---:|
| 公開写真 | 933 |
| Best Shot | 17 |
| NEW!イベント | 14 |
| 研究ケース | 66 |
| 退役写真 | 7 |
| master / sources | 141 / 419 |
| 削除候補 / 意図しない削除 | 0 / 0 |
| 公開記事 / 記事内画像 | 111 / 980 |
| コメント受付 | enabled=false |

portalのarticle_count=90は写真の出典記事、トップの観察記録83は探索日記対象記事。公開記事全体111とは集計範囲が異なります。古い件数へ戻す操作はありません。

既存trackedファイルはmainとbyte単位で一致。新規の候補・ツール・試験・監査・読取専用workflowだけを追加します。写真・EXIF・選択データ・通知・同定・retirement・master/sources/facets・admin・日次生成workflow・assetsの本体は無変更です。

## 採用候補と判断

[系譜と方式比較](../../hatena/release-2026-10-24/PROVENANCE.md)に根拠を整理。公式資料には固定ページをrootへ指定する機能を確認できませんでした（絶対に不可能と断定はしません）。現行DOMを調査し、root限定で既存#contentの前にiframeを加算する方式を採用候補にしました。

- 正式URLとnative記事一覧、sidebar、検索、pager、広告、system header/footerを維持。通常記事一覧も下に残るので全ページは長くなります。
- 原点origin/path/page-index/別の起動マーカー/実DOMの一致が必要。root以外、ページ送り、native bypassは起動しません。
- iframe childは現在公開済みのnew-top.html。新しいPagesデプロイも本PRの事前マージも実行要件ではありません。
- 同一iframeの二重初期化を防止。source/origin/遷移先・ID検証、ACK前の即時scroll、Window/BODY判定を再利用。
- metadata、canonical、OGP、feed、記事の保存先や配信設定は変更しません。

## CSS・フッターの整理

過去CSSは完全置換候補と追加パッチを区別しました。PR #121の両カテゴリCSSファイルだけをレビューして再利用し、そのコミットは取り込みません。#121との将来統合ではこの後継候補を重複適用しないでください。

最終候補design.cssは**56,303 bytes**、64KiBより9,233 bytes小さく、CSS parserにエラーなし。system sectionを保持。320/360pxの通常記事Heroタイトルが説明へ重なる問題を小画面の1行タイトルで改善しました。

フッターはmainの最新内容を再利用（ファイル名の日付で過去版へ戻さない）。配布するfooter-managed.htmlは管理対象scriptだけであり、現行Footer全文の代用品ではありません。PAGE TOP/MENU/解析など既存の他処理は照合後に保持します。

公開配信CSS 77,415 bytesは取得できましたが、サーバー生成の配信CSSと管理画面の生入力は同一とは確定できません。64KiB制限の違反や現在の未公開設定値をそこから推定していません。

## 検証

- Python：**1,086 passed**。初回baseline実行では既存同期fixtureのOUTPUT_INTEGRITY_ERRORが33件発生。安全条件は変更せず、該当2ファイル34件合格後に全件を再実行して成功。初回失敗をなかった扱いにしません。
- JavaScript：**14ファイルの構文・回帰合格**。新しい起動テスト12件と既存iframe親テスト17件も合格。
- 配布Footer中の各script：node --check合格。CSS UTF-8サイズ/構文確認合格。
- Chromium：最終結果と比較画像は追補予定。ローカルreplayを実はてなStaging合格とは扱いません。
- GitHub Actions：Draft PR最終HEADの結果を確認後、PR本文に確定記録を追補します。

再現試験は公開HTMLのsnapshotを元originのURLでrouteし、公開済み子HTMLを別originとして実Chromiumで描画します。外部トラッキング・認証・social操作scriptは試験fixtureから除外し、GET以外を拒否します。外部プロフィール等の一部画像/スターはこの試験で欠ける場合があり、本番サービスの完全表示保証には使いません。公開用payloadにこの除外処理は含みません。

## セキュリティと運用レビュー

入力HTMLをfetchして挿入しない、document全体を書き換えない、定数DOMをcreateElementで作成。origin/sourceの検証を緩和せず、sandboxも実new-topと同じ。公開コメントconfigはfalse。秘密情報を必要とせず、新workflowはcontents:readのみでデプロイ・編集・投稿を行いません。

オフライン組立てツールは原本hash・レビューhash・旧通信script一意性・theme section・CSSサイズ・重複設置を検査。不一致なら出力前に停止し、原本・既存出力を上書きしません。レビュー雛形は承認falseです。

## 公開・復元資料と残るゲート

- [配布ファイル一覧](../../hatena/release-2026-10-24/README.md)
- [初心者向け公開・復元手順書](../../hatena/release-2026-10-24/RUNBOOK.md)
- [読者・通知・RSS等12項目の保護/未検証一覧](../../hatena/release-2026-10-24/FUNCTIONS.md)
- [配布物サイズ/sha](release-manifest.json)

現行公式UIは「保存する」=未公開保存、「プレビュー」=確認、「変更を公開する」=本番公開。Staging保存にも別途承認が必要です。実UIやpreview originが異なれば停止し、ガードを緩めません。

残る必須確認：①公開中/未公開の生CSS/Header/Footer/固定ページ/設定を別々にバックアップし照合、②実Stagingで8幅とAndroidを受入れ、③公開対象hashと本番反映の個別承認。通知は次の正規記事の公開後、SEOは公開後の監視が必要です。

PR #136/#137はDraft・未マージのまま。本PRに両ブランチの変更を含めません。最終HEADとCIは本PRのhead/Checksおよび最終報告を参照してください（自己のcommit SHAを同じcommit内ファイルへ埋め込むことはできません）。

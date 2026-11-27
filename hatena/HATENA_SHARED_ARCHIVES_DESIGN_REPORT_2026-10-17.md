# 「キノコ探索日記」を「日常の記録」の一覧デザインへ揃える — Hatena CSS候補 (2026-10-17)

## 原因と対象

PR #119 で「観察記録をもっと見る」は正しいHatena `/archive/category/キノコ探索日記` に遷移するようになりました。しかしリンク先の**見た目はリンク変更では統一されません**。2026-10-11 の保存済みDesign CSS候補は、全71ルールが `body.page-archive-category.category-日常の記録` の**日常カテゴリ専用**でした。探索日記にはマッチしません。

> **適用状況は未確認:** 2026-10-11のレポートは「Hatena本番・Preview・Stagingに適用していない」と明記しています。ユーザーが後から手動適用した可能性はありますが、このGitHub作業から現在のHatena Design CSSの実内容は取得していません。**候補を無条件に全文置換しないこと。**

## 変更内容（候補のみ、Hatenaへの保存・公開なし）

- 入力：`hatena/hatena-design-css-daily-archive-2026-10-11.css`（49,662 UTF-8 bytes）。
- 提案：`hatena/hatena-design-css-shared-daily-field-archives-2026-10-17.css`（52,636 UTF-8 bytes。65,536 bytes上限内）。
- 元のmobile baseline 35,442 bytesはバイト単位で保持。既存の71 archiveルールの73回のscope接頭辞のみ、下記に置換：

```diff
- body.page-archive-category.category-日常の記録
+ body.page-archive-category:is(.category-日常の記録, .category-キノコ探索日記)
```

- 日常カテゴリの小見出し `DAILY NOTES` は変更せず、キノコ探索日記にのみ `FIELD NOTES` の上書きルール1件を追加。
- 写真カード、記事本文抜粋、サイドバー、メニュー、スマホ幅、native Hatena Star/bookmark、カテゴリ・タグ・記事のリンク、公開/非公開の条件はそのまま。URL判定JSは不使用。
- 他のカテゴリページ、通常記事、`new-top`、GitHub Pages/写真同期/Best Shot/研究室は変更しない。
- 実際の探索カテゴリのbody class `category-キノコ探索日記` は**実ブラウザDevToolsで最終確認が必要**。日常カテゴリのbody classは10/11の既存ブラウザ観測で確認済み。

## 安全な手動適用方法

1. はてなブログ **デザイン → カスタマイズ → デザインCSS** の現在の内容をまず全文ローカル保存（元へ戻せるようにする）。
2. 現在のCSSが10/11候補と同じであることを確認できれば、本ファイル全文をプレビューで試す。**現在のCSSに独自修正がある場合は、全文置換しない。**
3. 異なる場合は現在のCSS内の**archive専用セレクタ73箇所だけ**を上記の `:is()` 表記へ差し替え、末尾に下記を加える。別のスタイルに影響しないよう、単純な `category-日常の記録` 全体の一括置換はしない。

```css
body.page-archive-category.category-キノコ探索日記 .archive-heading::before {
  content: "FIELD NOTES";
}
```

4. PC 1440pxとスマホ390pxで**両カテゴリ**のカード、写真、サイドバー、MENU、PAGE TOPを比較し、他カテゴリ・個別記事・new-topに差分がないか確認。ページ送りが出る探索日記一覧では元の「次のページ」「新着順／人気順」を維持する。10/11の検証は日常カテゴリ全8記事で**ページ送りが存在しない**ため、探索日記のページ送りは別途実画面で確認が必要。
5. 異常があれば公開せずバックアップCSSに戻す。問題なければユーザーの判断でHatenaへ保存・公開する。

## 証拠・リリース制限

- 旧調査：`hatena/HATENA_DAILY_ARCHIVE_DESIGN_REPORT_2026-10-11.md`。10/11のローカルChromium（360/390/430/768/960/961/1440）で、日常専用デザイン・既存機能維持は確認済み。
- 本差分は**探索日記の実ブラウザ上の最終視覚テストではありません**。同じHatena一覧DOMを利用する前提のCSSスコープ修正であり、ページ送り・記事数増・サムネイル数差を別途確認すること。
- Draft PRの対象は文書・候補CSS・focused regressionのみ。GitHub mainへの直接push、PRマージ、はてなDesign CSSへの書き込み、本番公開はしない。

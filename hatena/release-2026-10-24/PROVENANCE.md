# CSS・フッターの系譜と採用判断

## CSS

| 過去成果 | 性質 | 今回の扱い |
|---|---|---|
| `hatena-article-newtop-preview.css` | 通常記事だけの追加パッチ | 全文候補に既に含まれるため追加しない |
| `hatena-design-css-slimmed-2026-10-07.css` | 完全置換候補、35,041 bytes | 系譜の記録のみ。後続の前へ再結合しない |
| `hatena-design-css-mobile-optimized-2026-10-09.css` | slimの後継、35,442 bytes | mobile調整を含む基準として後続に包含 |
| `hatena-design-css-daily-archive-2026-10-11.css` | mobile基準＋日常カテゴリ、49,662 bytes | 両カテゴリ化の入力。単独追加しない |
| PR #121のshared-daily-field CSS | 上の後継、52,636 bytes | CSSファイルだけ独立レビューして再利用。PRのコミットはマージしない |
| 本パッケージ `design.css` | shared候補＋rootと小画面の最小調整 | 全文候補を1本に統合 |

PR #121の入力commitは `2329fdf1c906189139147ba619c26c9365f66c6d`。ファイル `hatena/hatena-design-css-shared-daily-field-archives-2026-10-17.css` のGit blobは `ab36e0961dd40633080bdbd6cce49d8fecb61fd4`、実取得bytesのSHA-256は `2c2ce8cbee92a86c2dcf5e249749a4b0d0b1d2afaefabd2b0e664c22ab837e68`。過去文書に記載された別段階のhashと混同しない。

今回の変換は `body.static-page-new-top .header…` のprefixだけを `body:is(.static-page-new-top, .kinoko-home-ready) .header…` へ広げ、rootに同じHeroを再利用します。固定ページのタイトル非表示、sidebar非表示、記事カード透明化等のルールをrootへ広げません。後ろに `home.css` を追加します。rootのiframeは全幅にして、子ページの900px/899px切替を親側の余白でずらしません。320/360pxの通常記事で旧候補のタイトルが説明文へ重なったため、記事と2カテゴリのHeroタイトルを1行に収める小画面調整も追加します。画像・文言は同じです。

元のテーマimportとbackgroundのsystem sectionは元bytesのまま保持。CSSサイズと全配布物hashは監査のmanifestに記録します。64KiB（65,536 bytes）以内であることを実測します。管理画面に保存されたsystem sectionが違えば、組立てツールは停止します。

## フッターと起動

基準はmainの `hatena/hatena-footer-iframe-handler-candidate-2026-10-09.html`。名称は10/09ですが、mainの内容は後日のBODY scroll host・ACK前スクロール修正を含みます。日付だけで古い実装に戻さないでください。

- 高さ、余白予約、上方向スクロール時の解放、Window/BODY判定、origin/sourceチェック、内部html遷移/ID検証、ACK前スクロールをそのまま再利用。
- 追加はroot作成、同じiframeへの二重初期化防止、認証済み高さ受信時の読込表示終了のみ。
- sandboxは実 `/new-top` で観測した権限一覧と同じ。新しい権限を増やさない。
- PAGE TOP、MENU、解析やその他フッター部品を置換対象に含めない。
- iframe子の `assets/gallery.js`、高さ計測、LightGallery、スター・通知は変更しない。既存の子側互換経路や120ms fallbackを変更しない。

公開HTMLで配信されているCSSとinline scriptは読み取れましたが、**管理画面の生の保存値・未公開デザインの実値と同じと確定したわけではありません**。公開DOMを使う試験と、管理画面からの復元用バックアップを明確に区別します。

## 方式比較

| 方式 | 判断 |
|---|---|
| 固定ページ `/new-top` をトップへ直接指定 | 公式の固定ページ・詳細設定資料にその指定機能を確認できない。通常記事の先頭固定とは別。未確認機能を前提にしない |
| root限定の加算iframe（採用候補） | 既存originと子ページ、通信を再利用。通常記事・配信を維持、マーカー除去で起動停止できる |
| HTML全文置換／固定ページ本文をfetchして注入 | はてなnative UI・広告・script・SEOを壊す可能性があり不採用 |
| GitHub Pagesへ転送 | 正式URL・購読導線の要件に合わず不採用 |

公式根拠（2026-10-24 JST確認）：
- https://help.hatenablog.com/entry/pages
- https://help.hatenablog.com/entry/config/detail
- https://help.hatenablog.com/entry/pinned
- https://help.hatenablog.com/entry/blogparts
- https://help.hatenablog.com/entry/design/design-css
- https://help.hatenablog.com/entry/design-staging

「直接指定が絶対不可能」との断定ではなく、公式に確認できた機能と実DOMから選んだカスタマイズ方式です。管理画面の仕様が違えば、推測で設定せず停止します。

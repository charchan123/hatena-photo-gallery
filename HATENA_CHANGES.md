# Hatena 側変更手順（Phase 1 では未実施）

## Phase 1 の判定

Phase 1 の article 抽出修正に Hatena 管理画面側の変更は **不要**。以下は将来 Phase で子側 iframe 高さ同期と通信を整理する際に必要となる、未実施の具体的手順である。本番へはまだ貼り付けないこと。

## 変更が必要になる Phase

- Phase 2/3：子側が `#gallery-root` + `ResizeObserver` に移行し、親子を staging 検証する段階。
- 別の保守 Phase：ヘッダHTMLとデザインCSSの既知マークアップ誤りを直す段階。ギャラリ改修と同時に行わない。

## 対象別の判定

| 対象 | Phase 1 | 将来の対応 |
|---|---|---|
| ヘッダHTML | 変更しない | 余分な `</i>` / `</li>` を別保守で除去 |
| フッタHTML/JS | 変更しない | message の source/origin を厳密化、無効な親 click 監視を除去 |
| デザインCSS | 変更しない | `h1:before` 付近の不要 `</div>` を別保守で除去 |
| 記事本文 iframe | 変更しない | id/src/sandbox は原則維持 |

## 変更理由

親は `setHeight`, `scrollToTitle`, `lgClosed` を受信するが、origin 文字列だけでなく `event.source === iframe.contentWindow` も確認するべきである。子の `postMessage("*")` は将来、Hatena 親 origin を確定して限定する。親 window の click で `#galleryWrapper a` を見ても iframe 内部クリックはバブルしないため、子からの `scrollToTitle` に一本化する。

## 現在コードの検索目印

- フッタ：`photoGallery`, `requestHeight`, `setHeight`, `scrollToTitle`, `lgClosed`, `#galleryWrapper a`
- ヘッダ：メニュー末尾付近の連続する `</i>` / `</li>`
- デザインCSS：`h1:before` とその周辺の `</div>`
- 記事本文：`id="photoGallery"`

## フッタ：削除するコード

1. `window` の click listener から `#galleryWrapper a` を探すブロック全体。
2. `photoGallery` 用の旧 `message` listener と、旧 `load` で `requestHeight` を送るブロック。

## フッタ：追加/置換する完全なコード

子側 staging と組み合わせて検証した後、前項の旧2ブロックを以下の1ブロックで置換する。

```html
<script>
(function () {
  "use strict";

  var frame = document.getElementById("photoGallery");
  if (!frame) return;

  var galleryOrigin = "https://charchan123.github.io";

  function requestGalleryHeight() {
    if (!frame.contentWindow) return;
    frame.contentWindow.postMessage({ type: "requestHeight" }, galleryOrigin);
  }

  window.addEventListener("message", function (event) {
    if (event.origin !== galleryOrigin) return;
    if (event.source !== frame.contentWindow) return;
    if (!event.data || typeof event.data.type !== "string") return;

    if (event.data.type === "setHeight") {
      var height = Number(event.data.height);
      if (!Number.isFinite(height) || height <= 0) return;
      frame.style.height = "0px";
      void frame.offsetHeight;
      frame.style.height = Math.ceil(height) + "px";
      return;
    }

    if (event.data.type === "scrollToTitle") {
      frame.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    if (event.data.type === "lgClosed") {
      requestGalleryHeight();
    }
  });

  frame.addEventListener("load", requestGalleryHeight);
})();
</script>
```

## ヘッダ / CSS：削除と完全な追加コード

これらは別保守 Phase で、削除だけを行う。

- ヘッダ：HTML validator で対応する開始タグがないことを確認した余分な `</i>` と `</li>` の各1個を削除。**追加コードなし**。
- デザインCSS：`h1:before` 付近で CSS 宣言の外にある文字列 `</div>` の1個を削除。**追加コードなし**。

元コード全体はこの Git リポジトリに存在しないため、対応開始時に管理画面からバックアップし、削除対象が本当に余分な閉じタグであることを validator で再確認する。

## 変更しない部分

iframe の `id`, GitHub Pages URL, style, loading, scrolling, `allowfullscreen`, sandbox 権限、ギャラリ以外のフッタ処理、ヘッダのメニュー項目と見た目、CSS の `h1:before` ルール本体は変更しない。

## 管理画面での手作業

1. Hatena 管理画面のヘッダ、フッタ、デザインCSS、対象記事本文をそれぞれテキストファイルへ全量コピーし、日付付きで保存する。
2. まずテスト/プレビュー用ブログまたは下書きで、フッタの指定ブロックだけを置換する。
3. 子側 staging URL が別 origin なら `galleryOrigin` をその origin にし、iframe src も staging に向ける。
4. 完了した子側コードが明示 origin 宛てで送信することを確認してから保存する。
5. マークアップ修正は通信変更と別日/別変更とし、削除対象だけを削除する。

## 本番反映前の確認

- DevTools で不正 origin と別 window からの偽 `setHeight` が無視されること。
- PC / iOS Safari / Android Chrome で初回表示、検索、五十音遷移、favorite 追加/削除、LightGallery 開閉、fullscreen 解除後の高さを確認。
- コンテンツが増える場合と減る場合の両方で iframe 下に過大な余白やスクロールバーが出ないこと。
- Console に origin、postMessage、HTML/CSS parse エラーがないこと。

## ロールバック

管理画面の変更箇所ごとに、手順1で保存した全文をそのまま貼り戻して保存する。子側も同時に変更した場合は、先に GitHub Pages を直前の確認済み commit に戻し、次に Hatena フッタを戻す。ブラウザキャッシュを無効化して再確認する。

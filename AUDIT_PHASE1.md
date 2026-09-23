# Phase 1 構造監査

## 監査の範囲と前提

本文書は `efb2e0935760d15b0258c14c85811dd36e283c5b` の実ファイルを調査した結果である。このコピーには `main` / `origin` ref が存在しなかったため、開始時 HEAD をベース SHA とした。GitHub Pages や Hatena API にはアクセスしていない。

## 現在の構成

- `main.py` は設定、Atom API 全ページ取得、記事本文保存、BeautifulSoup による `img` 抽出、リモート JPEG の EXIF 取得/キャッシュ、名称別・五十音・ index・ favorite HTML 全生成を一括している。
- API は Atom `entry` の `content.text` だけを `articles/article_<n>.html` に保存する。今回、その呼び出しが実際に保存したパス一覧を返すようにした。
- 画像抽出は `alt` と `src` の両方がある `img` をエントリにする。ラベルは現在も `alt` 依存である。一部テキスト除外はあるが、full-page HTML 全体の UI 画像を分類できる仕様ではない。
- `generate_gallery` が alt 別詳細ページと五十音ページ、`generate_index` が検索データ/おすすめ付き index、`generate_favorite_page` が localStorage から JS 描画する観察ノートを作る。
- `STYLE_TAG` / `SCRIPT_TAG` / `LIGHTGALLERY_TAGS` は生成されるほぼ全ページに埋め込まれる。LightGallery 2.8.3 と zoom/thumbnail/autoplay/share は CDN 参照である。
- お気に入りは `lg_favorites` を保存し、件数は新構造 `lg_items` を優先しつつ旧構造にフォールバックする。`favorite.html` はキャッシュと src-to-alt を埋め込む。
- `output/` は生成先であるが、リポジトリ上では `.gitkeep`, 旧 `gallery.css`, 旧 `gallery.js`, `test-thumbnails.html` の4ファイルだけが tracked で、生成物全体は保存されていない。

## 確認した問題と Phase 1 で修正したもの

`articles/article1.html` (92 KiB) と `article2.html` (64 KiB) は Atom 記事本文ではなく Hatena ページ全体で、`.entry-body` もない。それぞれ 71 / 24 個の `img` を含み、プロフィール、関連記事、グループ由来の alt/src がある。旧実装は `articles/*.html` を全走査したため混入した。

Phase 1 ではファイルを削除せず、次の最小修正を行った。

1. `fetch_hatena_articles_api()` が「その呼び出しで保存した本文ファイル」の一覧を返す。
2. `fetch_images(article_files)` は指定ファイルだけを読み、ディレクトリの glob は行わない。
3. 通常実行は API が返した一覧をそのまま抽出に渡す。このため旧ファイルだけでなく、前回取得の `article_*.html` も今回の一覧になければ対象外になる。
4. Secrets 確認は import 時ではなく API 呼び出し時に限定し、値を捏造せず fixture テストを実行可能にした。

## 回帰テスト

小さな記事本文 fixture と Hatena full-page の特徴を再現した fixture を追加した。正常なムキタケ、同名連続画像、別の正常キノコ、旧ファイル併存時の非混入、画像抽出から HTML 生成手前/詳細ページまで、既知誤ページ6名が生成されないことを検証する。

## 今回修正していないもの

見た目、抽出ルール自体、LightGallery、お気に入り、検索、五十音、iframe 通信、fullscreen、CSS/JS 外部化、メタデータ化、差分生成、schedule、EXIF 永続化、workflow を変更していない。現行の `SCRIPT_TAG` には `highlight` 宣言の重複に見える箇所もあるが、Phase 1 では挙動変更を避けた。

## EXIF キャッシュ調査

`cache/exif-cache.json` を読み、URL ごとに未キャッシュの JPEG を `requests.get` して書き戻す。しかし現在 `cache/` は存在せず tracked ファイルもない。Actions に `actions/cache` の restore/save も artifact/branch からの復元もなく、checkout した clean runner で毎回空から取得する構成である。Phase 2 では、まず cache key と restore key を指定した `actions/cache` を採用し、キャッシュ消失時も完全生成可能な派生データとするのが安全。同時実行の上書きや空データ固定化を防ぐキー/保存条件と、HTTP エラー時の再試行方針を先にテストする。

## CSS / JS 重複状況

`main.py` は約 3,249 行、埋め込み CSS は約 1,130 行、JS は約 1,260 行の範囲である。一方ルートの `gallery.css` / `gallery.js` は 81 / 80 行で、前者は2列/1列レイアウトと独自 `#lb-overlay`、後者は公開 index を fetch して独自 lightbox を作る旧方式である。現行の LightGallery、お気に入り、検索、五十音、EXIF、iframe 通信と一致せず、代替として有効化できない。`output/gallery.*` も同様の旧資産である。Phase 2 の外部化は埋め込み内容を機械的にそのまま `assets/` へ移し、生成 HTML のスナップショット/ブラウザ確認後に参照を切り替えるべきである。

## iframe 高さ同期調査

子の `sendHeight` は body/documentElement の scrollHeight/offsetHeight の最大値を二重 `requestAnimationFrame` 後に `postMessage("*")` する。load 後の複数 timer、resize、非 favorite の body `MutationObserver`、親の `requestHeight` で再計測する。親 iframe の既存高さが documentElement 側に影響すると縮小を検出しにくい。Phase 2 で実コンテンツルートを追加し `ResizeObserver` でその高さを送る案を、現行親との後方互換性を保って検証する。Phase 1 では変更していない。

## LightGallery / fullscreen 調査

ギャラリー画像クリックで documentElement を fullscreen にし、モバイルの標準閉じるボタンは `forceMobileBuiltinClose()` および `lgAfterOpen` 内の両方で `closeLGAndExitFullscreen()` へ結び付けようとする。統合関数は `closeGallery`→fullscreen 解除→再 `closeGallery`→`lgClosed` 通知を行う。別に `lgBeforeClose` も fullscreen 解除と `lgClosed` 通知を行い、`fullscreenchange` は解除時に再び統合関数を呼ぶ。したがって close、fullscreenchange、`lgClosed` は複数経路/重複の可能性がある。Phase 2 以降で一度だけ実行する状態フラグと通知窓口に集約し、モバイル実機回帰テスト後に切り替える。

## GitHub Actions 調査

`.github/workflows/generate.yml` の trigger は `main` push と手動実行だけで schedule はない。Python 3.11 で requirements を入れ、3 Secrets の非空を確認し、`python main.py` の後に local LightGallery を output へコピーする。最後に `JamesIves/github-pages-deploy-action@v4` で `output` を `gh-pages` へ `clean: true` でデプロイする。よって将来の差分ファイルだけの output は既存ページを削除する。Phase 1 で workflow を変更・実行していない。

## 画像メタデータと差分生成の次 Phase 案

記事 ID / updated / content hash を article manifest に持ち、画像ごとに `url`, `detected_label`, `gallery_name`, `subject_type`, `article_id`, `source`, `confidence` を持つ。候補名は画像より前の独立段落を優先し、記事カテゴリは強い補助だが必須にしない。`mushroom` / `non_mushroom` / `review` を明示し、キノコ候補の `?`、`？`、`不明` は detected_label を保ったまま gallery_name を `不明` にする。「変更 article の解析」と「影響ページの計算」を分けるが、デプロイ前には完全な publish tree を staging で構築する。`clean: true` に部分 output を渡さない。

## 次 Phase の推奨順序

1. 現行出力のスナップショット/ブラウザテストを追加し、EXIF Actions cache を安全に導入。
2. 埋め込み CSS/JS を挙動不変で `assets/` へ移し、旧 `gallery.*` と明確に分離/廃止判定。
3. 子の実コンテンツ高さと親の origin/source 検証を staging で同時検証。
4. LightGallery/fullscreen 終了経路と親通知を単一化。
5. article manifest / 画像メタデータを先に導入し、完全生成と一致することを確認。
6. 完全 publish tree を保つ差分解析/生成を導入。
7. 変更なし時に deploy しない判定後、JST 0:00 相当の schedule を追加。

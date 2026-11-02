# 「キノコを探す」AI画像1用途の全階層差し替え

2026-11-02 JST。基準main `b913ad7b07f689f14f5c8dcecea11b7c99363827`、公開入力gh-pages `46043baa2b27c99e946d1352f838f51bbf4b1d72`。branch `feat/guide-artwork-refresh-20261102`。Draft PRまで。マージ・本番公開・はてな設定・Cloudflare・PR137への操作なし。

## 前回成果の再利用

マージ済みPR140（HEAD `3a7b1cf9b885ad9b0c33b3d35c81bd1560f026b6`）の7用途/21参照対応表、変換条件、全ページ生成・保護ソース比較・11ページ×8画面の実画像ブラウザ試験を再利用。`audit/ai-image-refresh-20261031/`の過去監査は変更しない。

今回の対象はmushroom-guide用途だけ。別用途の図鑑入口/季節/特徴/観察記録/研究室/Best Shot、共通大バナー、実写真は維持する。本文・件数・リンク・CSSの画像URL以外・Python生成コード・同期/削除保護・コメント実装/configに変更なし。

## 変換と保存先

- 入力：添付PNG `2ec29d1b-187a-4386-8b9b-8af83fe5e175(1).png`、1672×941、4,051,998 bytes。
- RGBAだがalphaは全画素255（完全不透明）。RGBへ変換し、リサイズ・切り抜き・色調整を行わずWebP化。
- 品質90/92/93を比較。前回と同じquality92/method6を採用、597,074 bytes（PNGから約85.3%減）。
- 実参照先：`assets/ai-mushroom-guide-20261102.webp`。新しい日付名で画像キャッシュを分離。
- 元PNGとWebPを目視比較。PSNR37.66dBは補助指標であり、視覚確認の代用にしない。
- 原本・変換後SHA、codec情報、品質別比較は[conversion.json](conversion.json)。元PNGは添付を正本とし公開assetへ重複追加しない。
- 旧 `ai-mushroom-guide-20261031.webp` は原バイトのまま残し、キャッシュ済みCSSとの互換を保つ。現在の表示参照は0。

## 全参照の差し替え

| ソース | 場所 | 変更数 |
|---|---|---:|
| assets/portal.css | トップの「キノコを探す」大枠 | 1 |
| assets/guide.css | 図鑑index共通バナー | 1 |
| assets/aiuo.css | 五十音一覧共通バナー | 1 |
| assets/detail.css | キノコ別・写真別詳細共通バナー | 1 |

合計4ソース参照。CSS以外のHTML/Python/JS/JSONに当該画像を直接指定する現在の製品経路はなかった。既存 `copy_shared_assets()` がPNG/WebPを配送するため、main.pyの変更不要。

公開済み入力を固定し、日次同期を実行せず、main/候補を同条件で再生成。333 HTMLは全文が前後一致。CSSを辿る全ページ監査で、新しい「キノコを探す」画像の継承先は325ページ（トップ・図鑑index・五十音・各詳細）。別用途だけの残り8ページも含め、333ページで参照漏れを検査した。ページ別一覧は[reference-audit.json](reference-audit.json)。旧表示画像名はHTML/CSS/JS/JSON全出力で0件。

## 保護と検証

- 画像/トップ/公開準備の既存Python48件成功（用途限定・他6画像不変の追加検査1件を含む）。
- 親子通信/iframe/高さ/ナビゲーションNode59件成功、fail/skip0。
- 全333 HTMLバイト一致。対象4CSSはURL以外一致、その他CSS不変。
- 基準mainの保護対象302ファイルが完全一致。旧画像・他6枚・写真/データ/同期/管理室/コメントを含む。main.pyも全文不変。
- 公開portal/同期snapshot/ケースmanifest/コメントconfigは生成前後一致、enabled=false。写真933、Best Shot17、研究室66、NEW14、master141、sources419を再取得した公開入力で確認。
- 現行7用途の検査manifestを本監査へ追加。過去の7画像監査は保存し、他6assetのレコードはそのまま継承。各画像hash・寸法とCSS全文の非画像hashを厳密比較する。
- テスト変更は新assetのパス/寸法・現在manifestの参照先のみ。ブラウザfixtureは基準mainに既にある6画像を削除せず、新assetだけをbefore出力から除くよう修正。これがないと前回用fixtureがbefore画像まで削除するため、正しい比較にならない。期待値緩和・skipなし。
- CIには新監査フォルダのpath trigger1行だけ追加。既存のread権限・全ページ/実ブラウザ検証を維持し、公開処理を追加しない。

### ローカル環境での未完了・失敗履歴

- ローカルChromiumがないためPlaywright1.58.0の公式ダウンロードを1回試行したが、取得ZIPのcentral directory不備でインストール失敗（CLI内の再試行も失敗）。ローカルのブラウザ試験は未実施。最終HEADのGitHub Actionsの実Chromium比較で確認し、CI結果と目視用artifactをPRに保存する。
- 同期関連の追加ローカル実行は68 passed/5 failed。5件はいずれもOUTPUT_INTEGRITY_ERROR。未変更mainの隔離worktreeでも同じ日次同期テスト1件がOUTPUT_INTEGRITY_ERRORで再現したため、今回の画像差し替え特有の失敗ではない。詳細なローカル基盤/生成物依存は未確定。同期コードや検査を変更せず、クリーンCIの全件結果を別途確認する。
- その前の試験指定では存在しないglobを渡して0件で終了。実ファイルを確認して上記へ訂正。テストのskipや合格扱いはしていない。

最終HEADのCI実行URL・全job/重要step・ローカル全件結果・表示確認はPRの最終監査コメントを正本とし、本資料自身の更新でHEADが循環することを避ける。未確認のCIを成功と記載しない。

## 公開境界

画像は既存background-size:cover/background-positionを維持するので、表示枠では元PNGの一部が切れる。画像自体を加工したものではない。Android実機・本番はてなでの候補画像表示は未実施。Draft・未マージで停止し、本番反映は別承認。前のCloudflare認証情報案は未発行のまま、本タスクではCloudflare画面・API・デプロイを操作しない。

# 比較画像（ローカル再現・実はてなStagingではありません）

公開HTML・同じ写真・同じ記事を同じ画面幅で再現。左が現在の配信デザイン、右が未公開候補です。外部の認証・広告・social操作scriptは両方の試験fixtureで除外しています。一部外部プロフィール等の欠けを本番の欠けとは解釈しないでください。

| 正式トップ | 比較画像 |
|---|---|
| 320px | [前後](home-320.webp) |
| 360px | [前後](home-360.webp) |
| 390px | [前後](home-390.webp) |
| 430px | [前後](home-430.webp) |
| 768px | [前後](home-768.webp) |
| 900px | [前後](home-900.webp) |
| 1280px | [前後](home-1280.webp) |
| 1440px | [前後](home-1440.webp) |

| その他 | 比較・現状維持の証跡 |
|---|---|
| 通常記事 | [320px](article-320.webp) / [1280px](article-1280.webp) |
| 探索日記 | [390px](field-390.webp) / [1280px](field-1280.webp) |
| 日常の記録 | [390px](daily-390.webp) / [1280px](daily-1280.webp) |
| 開発用固定ページ | [1280px](new-top-1280.webp) |
| rootに残した従来記事一覧 | [スクロール後1280px](native-articles-1280.webp) |
| Best Shot・年間Best（子のファイル無変更） | [390px](child-best-shots-2025-390.webp) / [1280px](child-best-shots-2025-1280.webp) |
| 研究室（コメント無効） | [390px](child-research-390.webp) / [1280px](child-research-1280.webp) |
| 特徴から探す（承認済み公開版） | [390px](child-features-390.webp) / [1280px](child-features-1280.webp) |

全幅の生データは [browser-results.json](../browser-results.json)。全160描画の原寸画像はPR最終HEADの「Read-only Hatena release preparation」Actions artifactに30日保存します。ここに選んだ22画像はGitに保存します。

rootは上にポータルを追加し、下の7つの通常記事やsidebarを残します。900pxで子も900pxになるため、2列/1列の境界をずらしません。Headerの傘の演出と子のBest Shot/サムネイルCSSを再利用しています。

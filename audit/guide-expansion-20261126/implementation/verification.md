# 資産と表示の検証

本番公開後の基準は `bd1b1eef5c9da0e30c9e5d02742782cb82949d1b`。Draftはこの公開ポータルを読み取り、通常生成と同じ `project_guide_expansion` を適用して比較する。

- 解説の候補20件のID・和名の重複と出典参照を検証。旧マスター・出典・分類・既存リンク34件を保全。
- 既存85種の表示内容・警告・既存出典、写真935枚のID・原記事・分類・撮影日を比較。追加20種の46枚では解説接続IDだけを追加する。
- Chromiumの1440・390・320pxで、公開版は既存85種と整理中20ページ、Draftは解説105種を比較。出典リンク、横はみ出し、文字の重なり、食毒欄・警告を確認し、LightGallery開閉とスクロール位置の復帰を代表ページで検証する。外部写真はテスト用画像に置き換えて比較する。
- 公開日次同期、管理室、特徴検索の承認済み入力、分類台帳、Best Shot、研究室、コメント、LINE、LightGallery実装は読み取り対象として保全する。
- 保護テストの許可差分は、基準mainに対する今回の表示実装6ファイルの正確なGit blobだけに限定。画像生成を保護するユニットテストにも同じ main.py のGit blobを追加した。

代表画面と全ページの比較データは、PRの「Read-only guide detail display audit」で `guide-85-viewport-results` を参照。主要な比較ページはキタマゴタケ、タマゴテングタケモドキ、キホウキタケ。

| 代表画面 | 公開版 | Draft |
| --- | --- | --- |
| キタマゴタケ・390px | [整理中](screens/base-kitamagotake-390.webp) | [図鑑欄・注意](screens/draft-kitamagotake-390.webp) |
| タマゴテングタケモドキ・1440px | [整理中](screens/base-tamagotengutakemodoki-1440.webp) | [図鑑欄・有毒資料](screens/draft-tamagotengutakemodoki-1440.webp) |

代表画像は [初回の表示CI](https://github.com/charchan123/hatena-photo-gallery/actions/runs/45713396784) から取得した。後続コミットはポータルの既存参照フィールドを保護するため、追加データを独立したフィールドへ格納した。生成した図鑑欄のHTMLは代表画像を撮影した版と一致する。

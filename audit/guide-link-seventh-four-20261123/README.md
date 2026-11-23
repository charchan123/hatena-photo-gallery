# 第7組：既存の掲載名4種類と図鑑マスターの安全な接続（公開前レビュー）

**状態：Draft・未マージ・未公開。** 写真を再同定せず、既存の表示名とマスター正式和名が完全一致する写真だけに既存の解説・出典を表示します。

- 基準main：`8de52dfcc1c4d5756ea6e7a87b4fc150df2cdb1f`（PR #176マージ後）
- 変更対象：`data/guide-links.json`（20→24件）と `detail_ui.py`（4種類の元データ照合済み表示文）
- 図鑑マスター141種 Git blob：`2dd35b344c59a7b718c5b86a9b9899b85e8c062d`（変更なし）
- 出典419件 Git blob：`b489a1c9e651ec68fb65478d5d80dcdd86ea3692`（変更なし）
- 解説付き掲載種類：71→75種類の予定

| 掲載名 | マスターID | 参照資料掲載学名 | 食毒区分（不変） | 表示見出し |
|---|---|---|---|---|
| ハラタケ | `haratake` | *Agaricus campestris* | `edibility_reported` | 資料には食用との記載があります |
| ホコリタケ | `hokoritake` | *Lycoperdon perlatum* | `edibility_reported` | 資料には食用との記載があります |
| ムキタケ | `mukitake` | *Panellus serotinus* | `edibility_reported` | 資料には食用との記載があります |
| ルリハツタケ | `rurihatutake` | *Lactarius indigo* | `edibility_reported` | 資料には食用との記載があります |

## 元メモと新表示文

### ハラタケ・ムキタケ・ルリハツタケ

- 元メモ：食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。
- 表示文：石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。

### ホコリタケ

- 元メモ：食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「幼時食」。幼時に限定された食利用の記録であり、時期を限定しない食用判断へ拡張しない。公的資料に食用記述があるという記録であり安全保証ではない。
- 表示文：石川県の資料では、食毒欄に「幼時食」と記載されています。これは若い時期に限った食用の記録であり、成長した個体まで食用と判断できるものではありません。また、採取したキノコの安全性を保証するものでもありません。

全種類の説明文を「です・ます調」に統一します。ただし、食毒の表記は資料の記録であって、安全性・同定の判定ではありません。全種類の「採る・調理する・食べる判断に使用しない」共通警告を保持します。元のメモ・正式和名・マスターIDの完全一致時のみ置換し、変われば適用しません。

## 既登録の出典

- `research-ishikawa-haratake`：石川県「ハラタケ」 https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/haratake.html
- `research-ishikawa-hokoritake`：石川県「ホコリタケ」 https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/hokoritake.html
- `research-ishikawa-mukitake`：石川県「ムキタケ」 https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/mukitake.html
- `research-ishikawa-rurihatutake`：石川県「ルリハツタケ」 https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/rurihatutake.html

ムキタケの掲載学名 *Panellus serotinus* と受容名候補 *Sarcomyxa serotina* の不一致、科等の未確定分類はそのまま維持します。類似種への自動同定や分類の推測はしません。

## 改変範囲と回帰保護

- 既存写真、元記事、写真の同定情報、分類辞書、マスター、出典、Best Shot、研究室、コメント/Cloudflare、LightGallery、公開設定は変更なし
- `tests/test_portal_data.py` に24件の参照整合性、曖昧名拒否、元観察データ不変、ホコリタケ「幼時食」の留保、元メモ変更でのレビュー無効化を追加
- `tests/browser/comments_integration_protection.py` と `tests/browser/ai_artwork_fixture.py` は第7組の厳密な2ファイルGit blobを、新mainの完全一致基準でのみ許可
- CIが全成功し、承認済み本文も人間が確認した後でのみ本番公開判断。勝手にマージしない

**Draft・未マージ・未公開。明示承認まで公開しません。**

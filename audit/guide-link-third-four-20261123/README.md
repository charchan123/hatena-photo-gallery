# 第3組：4種類の既存図鑑情報への接続（公開前レビュー）

**状態：Draft・未マージ・未公開。** 現行の写真と名前が完全一致する場合だけ、既存の図鑑マスターを表示します。写真から新たに種類を推定する作業ではありません。

- 基準main：`7b7f27fd2acc46f92d672320ac680fad4bb237a0`
- 図鑑マスターGit blob：`2dd35b344c59a7b718c5b86a9b9899b85e8c062d` （141種・無変更）
- 出典Git blob：`b489a1c9e651ec68fb65478d5d80dcdd86ea3692` （419件・無変更）
- 表示用4件追加後のguide-links Git blob：`772398ae86b28e8f9b78d0846d7eac06277261f5` （全8件）
- 公開中写真935枚、Best Shot17件、研究室66件、図鑑情報55種。公開後は同じ935枚で解説59種を想定。
- 食毒は元の区分を維持し、食べられるかどうかの判断に使わない共通注意書きも維持します。

| 図鑑の掲載名 | master ID | 既存写真 | 学名（出典報告値） | 食毒ステータス（変更なし） | 元の調査メモ（変更なし） | 新しい表示文（承認待ち） |
|---|---|---:|---|---|---|---|
| カニノツメ | `kaninotume` | 1枚 | *Linderia bicolumnata* | `unknown` | 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。 | 石川県の資料では、食毒欄に「不食」と記載されています。この記載だけで毒性が確認されたとは判断できません。 |
| カワリハツ | `kawarihatu` | 1枚 | *Russula cyanoxantha* | `edibility_reported` | 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。 | 石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。 |
| ガンタケ | `gantake` | 1枚 | *Amanita rubescens* | `poisonous_confirmed` | 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。 厚労科研2021研究分担報告書の表4注2は、以前の「食用にできるが生食は毒」という扱いと区別し、現在は食用にすべきでないとする注意を記載する。加熱による安全性は保証しない。毒成分は追加推定しない。 | 石川県の資料では、食毒欄に「毒」と記載されています。また、2021年の厚生労働科学研究の報告書には、以前は「食用にできるが生食は毒」とされていたものの、現在は食用にすべきでないという注意が記載されています。加熱すれば安全だと判断することはできません。 |
| キツネタケ | `kitunetake` | 2枚 | *Laccaria laccata* | `edibility_reported` | 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。 | 石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。 |

## 参照する出典（マスター登録済み）

### カニノツメ
- `research-ishikawa-kaninotume`：いしかわ きのこ図鑑「カニノツメ」（https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kaninotume.html）

### カワリハツ
- `research-ishikawa-kawarihatu`：いしかわ きのこ図鑑「カワリハツ」（https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kawarihatu.html）

### ガンタケ
- `research-ishikawa-gantake`：いしかわ きのこ図鑑「ガンタケ」（https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/gantake.html）
- `audit-mhlw-grant-2021`：令和3年度 研究分担報告書：植物性自然毒の食中毒の発生動向調査及び「自然毒のリスクプロファイル」更新（https://mhlw-grants.niph.go.jp/system/files/report_pdf/202124033A-buntan6.pdf）

### キツネタケ
- `research-kyoto-fungi-2015`：京都府自然環境目録2015 菌類（公開目録の現行URL）（https://www.pref.kyoto.jp/kankyo/mokuroku/bio/fungi.html）
- `research-ishikawa-kitunetake`：いしかわ きのこ図鑑「キツネタケ」（https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kitunetake.html）

## 安全上の例外と公開条件

- **カニノツメ**：「不食」を「毒」と同一視せず、food status は `unknown` のままです。
- **ガンタケ**：food status は `poisonous_confirmed` のままです。石川県の「毒」、厚生労働科学研究2021年の「食用にすべきでない」とする注意、「加熱すれば安全」ではないことを明示しています。毒成分は推測していません。
- **カワリハツ／キツネタケ**：資料上の「食」と実際に採取した個体の安全性は別である旨を維持します。
- 候補文は和名・mushroom_id・元メモ全文の完全一致時だけ適用し、原文が変われば旧文面に置き換えません。
- 対象の写真5枚と元記事、既存の分類状態・画像URL・研究室・Best Shot は変更しません。
- CI・公開前レビューの後、**ユーザーの明示承認までは公開しません**。

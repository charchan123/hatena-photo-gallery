# 第4組：収集済み図鑑情報4種類の安全な接続（公開前レビュー）

状態：**Draft・未マージ・未公開**。写真からの新規同定、学名や食毒判定の確定ではありません。掲載済みの和名がマスターの和名に完全一致する4ページに、既存の出典付き情報を表示する案です。

- 基準main：`ee64c84509c1115252000a9828fa207c2095cb9b`
- 図鑑マスター141種（無変更）Git blob：`2dd35b344c59a7b718c5b86a9b9899b85e8c062d`
- 出典419件（無変更）Git blob：`b489a1c9e651ec68fb65478d5d80dcdd86ea3692`
- 接続設定（8→12件）Git blob：`21489ddcf589456f3a0b564e9ace78b55488f1d0`
- 公開現状：解説付き59種類、写真935枚（公開後は解説付き63種類の見込み）。対象は既存写真合計6枚。
- 前回までの文体に合わせ、元メモは残して「です・ます調」の表示文だけを追加します。元メモが変わった場合は旧文章を誤適用しません。

| キノコ | master ID | 既存写真 | 学名（出典報告値） | 食毒ステータス（変更なし） | 表示見出し案 |
|---|---|---:|---|---|---|
| キララタケ | `kiraratake` | 1枚 | *Coprinus micaceus* | `edibility_reported` | 資料によって食毒の記載が異なります |
| クチベニタケ | `kutibenitake` | 3枚 | *Calostoma japonicum* | `unknown` | 食毒の区分は確認できていません |
| クリタケ | `kuritake` | 1枚 | *Hypholoma sublateritium* | `edibility_reported` | 資料には食用との記載があります |
| コタマゴテングタケ | `kotamagotengutake` | 1枚 | *Amanita citrina var.citrina* | `poisonous_confirmed` | 公的・専門資料には毒性の記載があります |

## 元メモと読者向け表示文の対照表

| キノコ | 元の調査メモ（不変更） | 新しい表示文 |
|---|---|---|
| キララタケ | 石川県の「食」は食用記録として保持するが、島根県中山間地域研究センター2025年記事はキララタケを「毒」と明示し、資料間競合がある。中国ではCoprinellus micaceus名の消化器症状報告があるが、加熱・飲酒条件と各症例の同定根拠の細部は未確認。旧化学文献は同じクロマトグラフィー挙動の物質という留保を含み、日本産キララタケのコプリン含有や飲酒時のみの毒性は確定しない。edibility_reportedを安全保証や摂食推奨と解釈しない。食用可否の自己判断に使用せず、空の毒成分欄は無毒を意味しない。 | 石川県の資料では「食」と記載されていますが、島根県中山間地域研究センターの2025年の観察会報告では「毒」と記載されています。中国で2021年に発生した中毒についても、Coprinellus micaceusという学名で消化器症状を伴う事例が報告されています。ただし、日本産のキララタケとの対応や、症例の詳しい同定方法、加熱・飲酒との関係は確認できていません。過去の化学研究にはコプリンまたは同じ分析上の挙動を示す物質の記載がありますが、日本産キララタケにコプリンが含まれると確定したものではありません。資料によって評価が異なるため、安全に食べられるとは判断できません。 |
| クチベニタケ | 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。 | 石川県の資料では、食毒欄に「不食」と記載されています。これは「毒」と同じ意味ではなく、この情報だけで毒性が確認されたとは判断できません。 |
| クリタケ | 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。 | 石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。 |
| コタマゴテングタケ | 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。 | 石川県の資料では、食毒欄に「毒」と記載されています。この記載だけで、採取したキノコの種類や安全性を判断することはできません。 |

## 参照する出典（全て既存のソースID）

### キララタケ
- `research-ishikawa-kiraratake`：いしかわ きのこ図鑑「キララタケ」（https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kiraratake.html）
- `final-critical-shimane-2025-kirara`：「大万木山きのこ観察会」を開催しました（https://www1.pref.shimane.lg.jp/life/region/kikan/chusankan/column/20251118.html）
- `final-critical-china-2021`：Mushroom Poisoning Outbreaks — China, 2021（https://pmc.ncbi.nlm.nih.gov/articles/PMC8796718/）
- `final-critical-matthies-laatsch-1992`：Ungewöhnliche Pilzvergiftungen: Coprin, ein Hemmstoff des Alkohol-Abbaus（https://wwwuser.gwdguser.de/~hlaatsc/060_Coprin.pdf）

### クチベニタケ
- `research-ishikawa-kutibenitake`：いしかわ きのこ図鑑「クチベニタケ」（https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kutibenitake.html）

### クリタケ
- `research-ishikawa-kuritake`：いしかわ きのこ図鑑「クリタケ」（https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kuritake.html）

### コタマゴテングタケ
- `research-ishikawa-kotamagotengutake`：いしかわ きのこ図鑑「コタマゴテングタケ」（https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kotamagotengutake.html）

## 特別な安全判断と公開条件

- **キララタケ**：元マスターは `edibility_reported` を保持。ただし石川県「食」と島根県2025年報告「毒」が併存するため、読者の目に入る見出しだけを「資料によって食毒の記載が異なります」に変更します。元の区分を偽って書き換えたり、毒性成分・加熱・飲酒による安全性を断定したりしません。
- 中国CDCの2021年中毒調査は `Coprinellus micaceus` に関する報告ですが、日本産キララタケと同一であるか、症例の採取・検査条件の詳細、コプリンの成分同定までは断定しません。
- **クチベニタケ**：石川県の「不食」は毒性確認と同義ではないため、食毒区分 `unknown` を維持します。
- **クリタケ**：「食」は出典に記された区分であり、採取個体の安全性の判断根拠にしません。
- **コタマゴテングタケ**：石川県の「毒」を保持し、成分や症状を推測で追加しません。
- 食毒の共通警告、写真、出典ID、記事、Best Shot、研究室、コメント/Worker/Cloudflare設定は変更しません。
- すべてのCI成功・原稿レビュー後、**ユーザーの別途承認があるまでマージ・本番公開しません**。

## Webで照合した資料

- 島根県中山間地域研究センター：2025年11月18日「大万木山きのこ観察会」（キララタケを「毒」と記載）：https://www1.pref.shimane.lg.jp/life/region/kikan/chusankan/column/20251118.html
- China CDC Weekly：Mushroom Poisoning Outbreaks — China, 2021（https://weekly.chinacdc.cn/en/article/doi/10.46234/ccdcw2022.010）

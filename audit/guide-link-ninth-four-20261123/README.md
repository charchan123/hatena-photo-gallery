# 第9組：既存掲載4種類の解説・出典接続（公開前レビュー）

**状態：Draft・未マージ・未公開。** 第8組の公開を確認し、既存の掲載和名と141種のマスターを完全一致で照合して追加候補を選定。写真の種同定や学名の再確定は行いません。

- 基準main：`a27c4e9b3f3b11538c93e4162d383e7a902d5b4e`（PR #178マージ済み）
- 公開写真935枚・掲載313項目・解説付き79種類、対象既存写真合計9枚
- 追加対象4種、解説付き79→83種（公開後）、追加リンク28→32件
- マスター141種：Git blob `2dd35b344c59a7b718c5b86a9b9899b85e8c062d`（変更なし）
- 出典419件：Git blob `b489a1c9e651ec68fb65478d5d80dcdd86ea3692`（変更なし）
- 写真ファイル・記事・和名・分類・マスター・元の食毒status・出典・Best Shot17件・研究室66件・Cloudflare/コメント/LightGalleryの既存構成を変更しません

| 掲載名 | 既存写真 | master ID | 出典掲載学名 | status（不変） | 食毒見出し |
|---|---:|---|---|---|---|
| クロハツ | 1枚 | `kurohatu` | *Russula nigricans* | `unknown` | 資料には食用を避けるよう注意があります |
| コツブタケ | 3枚 | `kotubutake` | *Pisolithus arrhizus*（京都府記載） | `unknown` | 食毒の区分は確認できていません |
| チャナメツムタケ | 4枚 | `cyanamemututake` | *Pholiota lubrica* | `edibility_reported` | 資料には食用との記載があります |
| ツチグリ | 1枚 | `tutiguri` | *Astraeus hygrometricus* | `unknown` | 食毒の区分は確認できていません |

## 元の調査メモと表示する説明文

### クロハツ

**原メモ**：
食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「要注意」。条件付き毒性記述／注意記述があるため食用判定へ変換せずunknownとした。 厚労科研2021研究分担報告書の表4注2は、以前の「食用にできるが生食は毒」という扱いと区別し、現在は食用にすべきでないとする注意を記載する。加熱による安全性は保証しない。毒成分は追加推定しない。

**新しい表示文**：
石川県の資料では、食毒欄に「要注意」と記載されています。また、2021年の厚生労働科学研究の報告書には、以前は「食用にできるが生食は毒」とされていたものの、現在は食用にすべきでないと記載されています。加熱すれば安全という意味ではありません。

- status `unknown` は変更しない。一般のunknown見出しを、出典の警戒度に合う「資料には食用を避けるよう注意があります」に置き換える
- ニセクロハツなどの類似種の写真再同定は行わない
- 元の `Russula nigricans` と他の受容名候補の対応が保留であり、分類・学名を推測して改変しない

### コツブタケ

**原メモ**：食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。

**新しい表示文**：石川県の資料では、食毒欄に「不食」と記載されています。これは「毒」と同じ意味ではなく、この記載だけで毒性が確認されたとは判断できません。

- 元資料に掲載の学名表記と京都府資料の学名表記の差、科の保留を維持し、受容名の断定はしない

### チャナメツムタケ

**原メモ**：食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。

**新しい表示文**：石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。

- 「食」との資料記録を、ブログ上の採取個体の同定や摂食可否の許可に拡張しない

### ツチグリ

**原メモ**：食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。

**新しい表示文**：石川県の資料では、食毒欄に「不食」と記載されています。これは「毒」と同じ意味ではなく、この記載だけで毒性が確認されたとは判断できません。

## 保存済み出典

- `research-ishikawa-kurohatu` 石川県・いしかわ きのこ図鑑「クロハツ」：https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kurohatu.html
- `audit-mhlw-grant-2021` 令和3年度 厚生労働科学研究研究分担報告書・表4注2： https://mhlw-grants.niph.go.jp/system/files/report_pdf/202124033A-buntan6.pdf
- `research-ishikawa-kotubutake` 石川県「コツブタケ」：https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/kotubutake.html
- `research-kyoto-fungi-2015` 京都府自然環境目録2015（学名根拠）：https://www.pref.kyoto.jp/kankyo/mokuroku/bio/fungi.html
- `research-ishikawa-cyanamemututake` 石川県「チャナメツムタケ」：https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/cyanamemututake.html
- `research-ishikawa-tutiguri` 石川県「ツチグリ」：https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/tutiguri.html

## 安全ガードとテスト

- `data/guide-links.json`：正確な和名4件の追加のみ
- `detail_ui.py`：和名・ID・元のメモ全文の一致時だけ新しい「です・ます調」の表示文に置換。クロハツはstatus `unknown` の場合だけ注意見出しを上書きし、データ側のstatusは不変
- `tests/test_portal_data.py`：32リンク・出典紐付け・保護される写真と分類・同定不明の拒否・注意説明・元メモが変わった場合の非適用を確認
- `tests/browser/ai_artwork_fixture.py`、`tests/browser/comments_integration_protection.py`：今回の `detail_ui.py` と `data/guide-links.json` のGit blobだけを固定検証（基準mainが完全一致する場合）。既存の画像/Worker/サイト保護は緩めない
- 全種類の共通の「採る・調理する・食べる判断に使用しない」警告を維持。毒性資料や写真の同定に不明点があれば拡大解釈しない

**CI全成功と人間レビューを確認した後も、公開には新たな明示承認が必要です。Draft・未マージ・未公開を維持します。**

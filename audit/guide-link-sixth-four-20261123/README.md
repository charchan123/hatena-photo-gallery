# 第6組：写真付き図鑑4種類への既存解説・出典接続（公開前レビュー）

**状態：Draft・未マージ・未公開。** PR #149 の未反映候補のうち、掲載名が完全一致する4種類のみ追加します。写真の種同定・分類を新たに行いません。

- 基準main: `019b734725471dba35641b188b30eb0d12e384de`（PR #175マージ後）
- 図鑑マスター141種: Git blob `2dd35b344c59a7b718c5b86a9b9899b85e8c062d`（変更なし）
- 出典419件: Git blob `b489a1c9e651ec68fb65478d5d80dcdd86ea3692`（変更なし）
- 明示的な参照名: 16→20件。解説付き種類は67→71種類を予定
- 対象既存写真のファイル、記事、図鑑トップの分類名、撮影情報、Best Shot、研究室、コメント設定を変更しません。

| 掲載名 | 参照マスターID | 元資料掲載の学名 | 食毒ステータス（変更なし） | 食毒見出し |
|---|---|---|---|---|
| ヌメリスギタケ | `numerisugitake` | *Pholiota adiposa* | `edibility_reported` | 資料には食用との記載があります |
| ハタケシメジ | `hatakesimeji` | *Lyophyllum decastes* | `edibility_reported` | 資料には食用との記載があります |
| ハチノスタケ | `hatinosutake` | *Polyporus alveolaris* | `unknown` | 食毒の区分は確認できていません |
| ハツタケ | `hatutake` | *Lactarius hatsudake* | `edibility_reported` | 資料には食用との記載があります |

## 元の食毒メモと表示文

- ヌメリスギタケ、ハタケシメジ、ハツタケ：
  - **元メモ**：食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。
  - **表示文**：石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。
- ハチノスタケ：
  - **元メモ**：食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。
  - **表示文**：石川県の資料では、食毒欄に「不食」と記載されています。これは「毒」と同じ意味ではなく、この記載だけで毒性が確認されたとは判断できません。

表示文は、元マスターのID・和名・元の食毒メモが完全一致した場合だけ適用します。共通の「採る・調理する・食べる判断に使用しない」という注意書きはそのまま維持します。

## 対象の既存出典（2026-11-23 再照合）

- `research-ishikawa-numerisugitake`：石川県「ヌメリスギタケ」 https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/numerisugitake.html （食）
- `research-ishikawa-hatakesimeji`：石川県「ハタケシメジ」 https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/hatakesimeji.html （食）
- `research-ishikawa-hatinosutake`：石川県「ハチノスタケ」 https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/hatinosutake.html （不食）
- `research-ishikawa-hatutake`：石川県「ハツタケ」 https://www.pref.ishikawa.lg.jp/ringyo/kinoko/data/hatutake.html （食）

ハタケシメジのマスター分類 `taxonomy.family=null` は元資料間の整理が保留であり、推測して補いません。ハチノスタケの資料掲載学名 *Polyporus alveolaris* と現行受容名候補 *Neofavolus alveolaris* の関係および属分類保留も現状維持します。「不食」を有毒・無毒いずれの結論にも置き換えません。

## 回帰保護

- `data/guide-links.json`：完全一致の4件追加のみ
- `detail_ui.py`：原資料に一致する場合だけ4種の読みやすい説明へ
- `tests/test_portal_data.py`：20件、完全一致・あいまい名拒否、写真/分類/出典/食毒区分の保全、原メモ更新時の安全側動作を検査
- `tests/browser/comments_integration_protection.py`・`tests/browser/ai_artwork_fixture.py`：第6組の2つのソース変更をGit blob SHAに固定。Worker、API、LightGallery、写真データの旧保護ルールは変更しません。
- 既存の公開数・画像・元記事・Best Shot17・不明キノコ研究室66・出典419・マスター141の保持を公開前CIで確認します。

**CIと人間による文章点検が完了しても、自動でマージ・本番公開しません。公開には別途明示的な承認が必要です。**

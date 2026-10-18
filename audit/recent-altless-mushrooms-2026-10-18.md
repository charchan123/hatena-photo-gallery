# 直近7記事からの図鑑未収録画像監査（2026-10-18）

基準公開 gh-pages f29e3557865bfdfa5964bbabc64c7673bf28520d。記事7件・画像73件、既収録23件、未収録50件（名前taxonomy未照合46、明示的複数種等の境界保留4）。本番公開図鑑893枚。

- 前提：Draft PR #124（ブドウニガイグチ2＋マツタケ2）は未マージ。本PRはそのブランチ上の積み上げであり先に単独マージ不可。
- 新規taxonomy: 外部名称資料が確認できた26種類・既存図鑑または執筆者修正に基づくproject_seed 2種類。名称根拠のみで写真個体の独立同定、食毒・摂食可否は主張しない。
- フジアザミ（植物）は対象外。オオジョウゴタケ？は執筆者の仮同定につき3枚とも保留。
- フモトニガイグチ、アブラシメジモドキは名称根拠の追加精査まで保留（各1枚）。
- アンズアケ(広義)を別種にはしない。執筆者はアンズタケ(広義)に修正済みと説明。古い取得データの互換性のため、別ページを作らない別名扱い。
- 複数種明示見出しの写真は1つのソースURL/写真IDを維持して、それぞれの種の個別HTML上に参照表示する。一般的な曖昧見出しを自動採用しない。
- Phase3C、本番削除・研究/BestShot保護、退役7件の非復活、master141件・sources419件、daily syncを変更しない。

## 追加する名前の名称確認資料

- アカジコウ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- アシナガイグチ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- ウスタケ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- キイロイグチ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- クリフウセンタケ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- シロオニタケ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- タマゴテングタケモドキ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- チチタケ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- テングタケダマシ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- ナカグロモリノカサ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- ニガイグチモドキ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- ベニイグチ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- ベニハナイグチ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- ムラサキヤマドリタケ: https://www.pref.ishikawa.lg.jp/ringyo/kinoko/index50.html
- イボセイヨウショウロ: https://i-zukan.jp/category/syu?category_id=24553
- ウスムラサキシメジ: https://www.city.niigata.lg.jp/iryo/shoku/syokuei/shokucyudokuinfo/kinokoitiran.html
- オオノウタケ: https://i-zukan.jp/category/syu?category_id=18675
- キタマゴタケ: https://www.pref.kyoto.jp/kankyo_red/2026/static/02_plants-fungi/06_fungi.html
- キホウキタケ: https://crd.ndl.go.jp/reference/detail?page=ref_view&id=1000093336
- キンチャワンタケ: https://i-zukan.jp/category/syu?category_id=24440
- サクラシメジモドキ: https://s-kinokonokai.sakura.ne.jp/kinoko/common/sakurasimezimodoki.htm
- ショウゲンジ: https://www.hokeniryo1.metro.tokyo.lg.jp/shokuhin/foods_archives/publications/foodDygiene/pdf/foodDygiene_h03/foodDygiene_h03-03-2.pdf
- マクキヌガサタケ: https://www.rinya.maff.go.jp/hokkaido/square/photo/mushroom.html
- ムレオオフウセンタケ: https://www.hokeniryo1.metro.tokyo.lg.jp/shokuhin/foods_archives/publications/foodDygiene/pdf/foodDygiene_h03/foodDygiene_h03-03-2.pdf
- ヤシャイグチ: https://i-zukan.jp/category/ka?category_id=510&order=0&per=50
- ヤマドリタケ: https://www.pref.kyoto.jp/kankyo_red/2026/static/02_plants-fungi/06_fungi.html

## 未着手・確認予定

- 最新Hatena APIからアンズタケ(広義)の本文修正を取得、公開HTML側の残存旧表記を再確認する。
- CIの独立API PREVIEW/保護写真/Chromium回帰を確認する。PR #124との差分を分離する。

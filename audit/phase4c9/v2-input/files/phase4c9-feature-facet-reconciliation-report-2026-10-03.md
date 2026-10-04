# Phase 4C.9 feature facet provenance reconciliation

監査日：2026-10-03。対象は添付candidateの **383 assignmentのみ**。結論は **Option B（出典ごとに独立した証拠単位）を推奨**。373 assignmentをレビュー候補に残し、10件を保留した。master、sources、入力feature-facets、baseline、reviewed、GitHubは変更していない。食毒・taxonomy・学名の再監査や新規facet付与は行っていない。

この成果は原文を個別照合したassistantによるレビューであり、実在の人間による承認を取得したという意味ではない。厳密に「人手承認済み」と数えられるassignmentは0件。runtime candidateは人間のレビューとv2実装を経て使う候補であり、現行v1への直接置換用／production承認済みデータではない。

## 結果

| 項目 | 件数 |
|---|---:|
| 原文照合したassignment | 383 / 383 |
| 引用されたsourceを確認 | 130 / 130 |
| A VALID_INDEPENDENT_SOURCE_EVIDENCE | 18 |
| B SAFE_SUMMARY_EQUIVALENT | 347 |
| C SOURCE_PROVENANCE_ADJUSTMENT | 8 |
| D INSUFFICIENT_OR_UNSUPPORTED | 10 |
| 削除ではなく保留を推奨 | 10 |
| evidence_text変更推奨 | 3 |
| source_ids変更推奨 | 1 |
| 最終runtime candidate | 373 assignments / 127 entries |
| groups / facets | 4 / 20（定義は不変、全20利用） |
| 元308 mismatchの安全なsummary同等表現 | 281（B 274＋C 7） |

Bには既存のsummary完全一致で変更不要の73件を含む。元の308 evidence mismatchだけでは **A 18 / B 274 / C 7 / D 9**。残り75件はB 73 / C 1 / D 1。元からv1を満たすことと、原文に支持されることは同じではない。

一次分類の優先順位はD、C、B、A。Cは安全なsummary同等表現があるうえでsource集合差が残る7件と、既存の過剰引用1件。evidence/source双方の不一致フラグと副次的なsummary同等表現は全件のJSONに保存した。C以外のsource不一致も消していない。Dには明白な誤りだけでなく、現在のfacetラベルでは表現しきれない限定・部位・比喩を保守的に保留した例を含む。

## 方法と再利用した資料

添付3 JSONを構文解析し、2つの不一致資料と照合した。保存済み `audit-work/web` の本文・取得メタデータを再利用し、130の引用sourceの対象種節を読み、383組のfacet/evidence/source/summaryを個別照合した。多数の資料を再ダウンロードしていない。検索snippet、写真や所属属・科からの形態推定は使っていない。

石川県の種別本文は傘、傘下面、柄、その他を分けた。厚労省は「形と色」と比較表の対象列を区別。森林総研の短い生態欄は実際に記された特徴だけに限定した。ツバアブラシメジは保存済みPDF本文の冊子p.7を利用。ヒロメノトガリアミガサタケは同じDOIの保存済みJ-STAGE全文も参照した。PDF画像化は行っていない。

各判断には原文quote、URL、対象部位・節、抽出本文の行範囲／文字offset、quoteと本文のSHA-256、保存されていた応答のSHA-256を付した。quoteは原文、evidence_textは原文引用または支持される要約として区別する。原文の「菅孔」「紛状」などを引用中で黙って訂正していない。

source_idを有効と認める根拠はHTTP 200ではなく、保存本文の対象種と当該特徴である。既存の学名／和名対応をこの作業で自動変更していない。出典に残る古い名の扱いは本監査の承認対象外。

## 不一致の再現と、追加で見つかったcoverage契約

添付candidateで308 evidence mismatch / 108 mushrooms、16 source-set mismatch / 7 mushroomsを再現。保存されたexpandedでも308 / 16を再現した。従って今回の反映で生じた破損とは扱わない。

実際のbranch `feature_ui.py` を読み取り専用で確認した。blob SHAは `e672989c1a9b1d957c2389b40ccfb55bc4f5bfaf`。ユーザー指定base SHAに対する参照も保持した。CIの392 passed / 1 failedはユーザーからの現況報告であり、この作業でGitHub CIを再実行した値ではない。

v1はさらに「summaryを持つmaster全件とfacet entryのID集合が完全一致」を要求する。現candidateのsummary保有は139件、facet entryは127件で、**12件のcoverage不足も存在**する。最初の例外で停止するため、1つの失敗テストの背後に複数条件の違反がある。今回の範囲外にfacetを追加して埋めない。

v2候補では139件＝127収録＋12明示未収録という閉じた集合を保存した。12件は「形態が存在しない」ではなく「元383 assignmentに含まれず今回追加しない」。summaryを持たない残り2件はこのeligible集合の外である。

## source集合の判断

元の16差異は12件がmaster sourceの部分集合、4件が部分集合でない。source_idsをmaster全体へコピーする修正は行わない。masterの総合説明を支える全出典が、個々のfacetをすべて支えるとは限らない。

ドクツルタケの4件（cap_sticky/gills/stem_solid/stem_scales_pattern）は石川県の該当種本文で明示される。特に「柄：中実」はその引用にある。厚労省sourceへ機械的に置き換えると、原文で確認したprovenanceを失うため、石川県sourceを保持した。

新規に認めた過剰引用はヘビキノコモドキvolva。森林総研ページは傘のイボを記すが、つぼを記さない。`ffpri-hebikinokomodoki`だけをこのassignmentから外し、つぼを明示する`ishikawa-hebikinokomodoki`を保持した。同じ森林総研sourceはcap_scales_wartsでは支持があるため保持する。source台帳自体は変更しない。

## 保留10件

これらの形態が実際に「ない」と判定したわけではない。現facet定義に対する十分な支持がないか、無条件のring表示へ落とす際の不確実性が大きいため、候補から保留した。

| 決定 | 種 | facet | 理由 |
|---|---|---|---|
| FCR-031 | ヤマイグチ | hairy | 「やや綿毛状」は質感の比喩。毛そのものの存在を明示する記載まで確認できず、hairyへの対応を保留。 |
| FCR-049 | ウコンハツ | cap_fibrous_felt | ビロード状のみ。繊維紋・フェルト状と同義の根拠なし |
| FCR-061 | タマゴタケ | cap_striate_grooved | 条線の記載位置が傘縁と明示されない |
| FCR-107 | キアミアシイグチ | cap_fibrous_felt | ビロード状のみ。繊維紋・フェルト状と同義の根拠なし |
| FCR-117 | マツオウジ | ring | つばのないものもある。現行の無条件ringチップは保留 |
| FCR-131 | アワタケ | cap_fibrous_felt | ビロード状のみ。繊維紋・フェルト状と同義の根拠なし |
| FCR-154 | オニイグチ | hairy | 綿毛状鱗片を独立した毛の存在へ拡張しない |
| FCR-157 | オニイグチモドキ | ring | 早落性。現行の無条件ringチップは保留 |
| FCR-292 | ニガクリタケ | ring | 不完全なつば。現行ring意味との対応保留 |
| FCR-321 | ヒトヨタケ | ring | 不完全なつば痕跡。現行ring意味との対応保留 |

ビロード状をフェルト状へ、綿毛状／綿毛状鱗片を毛そのものへ無条件に読み替えない。タマゴタケの引用は「条線有」であり、facetが要求する傘の縁という位置が明示されない。ringについては欠如するものの併記、早落性、不完全、痕跡を単純な有無へ圧縮しない。これは新たな生物学的否定ではなく、公開用の証拠とラベルの適合性を保守的に扱う判断である。

## 限定的な変更3＋1件

| 対象 | field | 旧値 | 候補値 | 理由 |
|---|---|---|---|---|
| ヘビキノコモドキ / volva | source_ids | ['ishikawa-hebikinokomodoki', 'ffpri-hebikinokomodoki'] | ['ishikawa-hebikinokomodoki'] | つぼの明示を確認。袋状・環状・襟状・破片・不完全など、資料の形態限定を保持。単なる基部膨大からは推測しない。 summaryでfacet自体は支持できるが、source単位の集合設計を要調整。masterの全sourceへの水増しはしない。 森林総研はvolvaを記さないため、実際に支持する石川県sourceだけに限定。 |
| タマゴタケモドキ / volva | evidence_text | 柄：繊維状小鱗片有、ツバ有、ツボは袋状 | ツボは袋状 | つぼの明示を確認。袋状・環状・襟状・破片・不完全など、資料の形態限定を保持。単なる基部膨大からは推測しない。 masterのsummaryに当該facetを支持する文字列がないため、独立した出典証拠として保持。 IA-029の未解消ring主張を混在させず、該当部位の原文だけに切り出す。 |
| タマゴタケモドキ / stem_scales_pattern | evidence_text | 柄：繊維状小鱗片有、ツバ有、ツボは袋状 | 繊維状小鱗片有 | 柄の鱗片・模様・ささくれの明示を確認。facet定義に「模様」が含まれるため網目模様も対象。 masterのsummaryに当該facetを支持する文字列がないため、独立した出典証拠として保持。 IA-029の未解消ring主張を混在させず、該当部位の原文だけに切り出す。 |
| ツキヨタケ / stem_solid | evidence_text | 柄：短く中実、隆起状のツバ有 | 柄：短く中実 | 柄の中実の明示を確認。髄状だけからは推定せず、範囲・成長変化は原文に保持。 summaryでfacet自体は支持できるが、source単位の集合設計を要調整。masterの全sourceへの水増しはしない。 つば様隆起帯を真のringと混同させないため中実の原文だけを切り出す。 |

Bの同等表現はOption Aの可否比較用としてJSONに保存した。Option Bの採用案では、281件の原文寄りのevidenceをCIのためだけにsummaryの言い回しへ変更しない。したがって「置換可能281件」と「実際のevidence変更推奨3件」は異なる数である。

## 高リスクの部位・条件確認

- IA-029タマゴタケモドキはcap_sticky/gills/volva/stem_scales_patternの4件だけ。**ringは追加していない**。volvaと柄鱗片の根拠は競合中の「ツバ有」を含む全文から、それぞれ「ツボは袋状」「繊維状小鱗片有」へ切り出した。つばの競合自体の再審査はしていない。
- ツキヨタケstem_solidは「柄：短く中実」だけに絞った。つば様隆起帯からringを作らない。
- poresは「菅孔」という原資料の表記も対象器官の文脈付きで保持。厚労省ドクヤマドリの行見出しが「ひだ」でも、本文が管孔と明示しているためgillsへ読み替えない。
- 中実～中空、中実後中空、中空～髄状等は範囲・成長変化を保持する。両facetがある種は同じ個体で同時に両状態になるという意味ではない。v2のUIではqualifiersの表示が必要。
- volvaには袋状だけでなく環状・襟状・破片・不完全との原記載がある。これらを袋状の完全なつぼと表示しない。
- ベニテングタケのいぼ脱落、シイタケの成長による鱗片消失、ハイイロシメジの「くぼむこともある」、ヤコウタケの傘の被覆層だけのゼラチン質を保持する。本文に存在する条件を削って万能な識別特徴にしない。
- キアミアシイグチの石川県頁は実際には「キアミアミイグチ」と表示する。掲載学名と国内和名対応の既存IA-035資料を参照するが、原文の誤記候補を隠さない。京都府目録はidentity補助資料であり、形態そのものの出典へ水増ししない。
- ヒロメノトガリアミガサタケは原著本文のalveoli記載を根拠に網目を照合。旧和名の概念と現在の学名の対応を今回新規確定したという意味ではない。
- シイタケの2件は厚労省ツキヨタケ頁の「6 間違いやすいキノコ」のシイタケ列にある。ページタイトルだけで別種参照エラーとはしない。逆に主対象ツキヨタケの記載をシイタケへ流用していない。

## Option A / Option B

| 観点 | Option A：v1維持 | Option B：出典単位の証拠 |
|---|---|---|
| summaryの役割 | 引用の格納庫も兼ねる | 読者向け要約 |
| 原文で支持されるA 18件 | summaryへの追加またはfacet削除が必要 | 原文・位置・出典の独立証拠で維持 |
| source集合 | master全体と完全一致 | 当該facetの支持出典集合と一致 |
| 過剰引用 | masterの全sourceコピーでは発生し得る | sourceごとの支持判定を必須化 |
| coverage | summary保有139＝127を要求し失敗 | 127収録＋12理由付き未収録を検証 |
| 実際の原文支持 | v1だけでは保証できない | 固定snapshotと承認済み判定を検証 |
| 移行 | 単純置換で全面解消できない | 明示的version2・新しい検証経路が必要 |

**Option Bを推奨。** summaryの引用一致・source集合一致を削る代わりに、引用snapshotのハッシュと位置、種とfacetへの束縛、各sourceの支持判定、台帳との一致、承認の固定、理由付きcoverageを加える。詳細はvalidator-plan参照。単に非空・参照存在だけを検査する案ではない。

## 検証結果とproduction gate

ローカルで32項目PASS。これは候補と証拠台帳の構造・整合性検証であり、新validatorの実装完了や人間承認を意味しない。現行v1に入力した元candidateはevidence一致で拒否され、新candidateはversion2のため期待どおり拒否される。候補にもv1基準でevidence不一致299件、source集合不一致17件が残る。これを隠してCI通過と報告しない。

| 検査 | 結果 | 詳細 |
|---|---|---|
| JSON構文 | PASS |  |
| input master件数 | PASS |  |
| input source件数 | PASS |  |
| input assignment件数 | PASS |  |
| 383件の決定一対一 | PASS |  |
| candidate version2を明示 | PASS |  |
| 4groups/20facets定義を変更しない | PASS |  |
| master ID重複なし | PASS |  |
| source ID重複なし | PASS |  |
| candidate entry ID重複なし | PASS |  |
| facet assignment重複なし | PASS |  |
| 既存assignment以外の追加なし | PASS |  |
| 全20facet利用 | PASS |  |
| source/master/facet参照切れなし | PASS |  |
| evidenceとsource_ids非空かつsource重複なし | PASS |  |
| 証拠参照の閉包 | PASS |  |
| source集合と支持証拠集合一致 | PASS |  |
| 証拠対象種/facet/支持判定一致 | PASS |  |
| 全証拠quote/offset/本文SHA256/source URL整合 | PASS |  |
| coverage 139対象=127収録+12明示未収録 | PASS |  |
| 373採用+10保留=383 | PASS |  |
| A/B/C/D集計整合 | PASS |  |
| candidateと決定の完全対応 | PASS |  |
| 人間承認の未取得を明示 | PASS |  |
| IA-029 ringなし/既存4facet維持 | PASS |  |
| 添付CSV308件と再現結果対応 | PASS |  |
| 元308evidence/16source不一致再現 | PASS |  |
| 5入力ファイルSHA256不変 | PASS |  |
| 変更はevidence3件/source1件 | PASS |  |
| v1期待どおり拒否:original_input | PASS | mushroom_id dokutsurutake, facet_id cap_sticky: evidence_text is not an exact summary substring |
| v1期待どおり拒否:candidate_v2 | PASS | feature facets version must be 1 |
| 保存済みexpandedでも308/16 | PASS | 308/16 |

production投入は現時点で未承認。人間が少なくとも保留10件、条件・対象種の限定、引用snapshotと表示を確認し、採用する判定台帳のハッシュを固定する。v2validatorと条件表示の変更・テストはこの作業では提案のみ。GitHubへの反映は別工程であり、本作業では書き込みなし。

## 明示未収録12件（追加調査なし）

kiirosuppontake、erimakitutiguri、onifusube、kaninotume、kutibenitake、kotubutake、sankotake、syouro、tutiguri、bunaharitake、hokoritake、yamabusitake。

## 383件の個別判定一覧

以下のIDでdecisions JSONの全文quote・source URL・summary・旧値／候補値・判断理由に一対一で辿れる。表の「保持」は人間承認前の候補としての保持。

| 決定 | mushroom_id | 和名 | facet | 分類 | 処理 | 引用source_id |
|---|---|---|---|---|---|---|
| FCR-001 | kaentake | カエンタケ | rod_cylindrical | B | 保持 | mhlw-kaentake |
| FCR-002 | dokutsurutake | ドクツルタケ | ring | B | 保持 | mhlw-dokutsurutake |
| FCR-003 | dokutsurutake | ドクツルタケ | volva | B | 保持 | mhlw-dokutsurutake |
| FCR-004 | dokutsurutake | ドクツルタケ | cap_sticky | A | 保持 | research-ishikawa-dokuturutake |
| FCR-005 | dokutsurutake | ドクツルタケ | gills | A | 保持 | research-ishikawa-dokuturutake |
| FCR-006 | dokutsurutake | ドクツルタケ | stem_solid | A | 保持 | research-ishikawa-dokuturutake |
| FCR-007 | dokutsurutake | ドクツルタケ | stem_scales_pattern | A | 保持 | research-ishikawa-dokuturutake |
| FCR-008 | akayamadori | アカヤマドリ | cap_sticky | B | 保持 | ishikawa-akayamadori |
| FCR-009 | akayamadori | アカヤマドリ | stem_scales_pattern | B | 保持 | ishikawa-akayamadori |
| FCR-010 | akayamadori | アカヤマドリ | pores | A | 保持 | ishikawa-akayamadori |
| FCR-011 | akayamadori | アカヤマドリ | stem_solid | A | 保持 | ishikawa-akayamadori |
| FCR-012 | hiromenotogariamigasatake | ヒロメノトガリアミガサタケ | head_reticulate | B | 保持 | mycoscience-myc590 |
| FCR-013 | kikurage | キクラゲ | gelatinous | B | 保持 | ishikawa-kikurage |
| FCR-014 | kikurage | キクラゲ | hairy | B | 保持 | ishikawa-kikurage |
| FCR-015 | hebikinokomodoki | ヘビキノコモドキ | cap_scales_warts | B | 保持 | ishikawa-hebikinokomodoki,ffpri-hebikinokomodoki |
| FCR-016 | hebikinokomodoki | ヘビキノコモドキ | volva | C | 保持 | ishikawa-hebikinokomodoki,ffpri-hebikinokomodoki |
| FCR-017 | hebikinokomodoki | ヘビキノコモドキ | gills | A | 保持 | ishikawa-hebikinokomodoki |
| FCR-018 | hebikinokomodoki | ヘビキノコモドキ | stem_solid | A | 保持 | ishikawa-hebikinokomodoki |
| FCR-019 | hanaiguchi | ハナイグチ | cap_sticky | B | 保持 | ishikawa-hanaiguchi |
| FCR-020 | hanaiguchi | ハナイグチ | stem_sticky | B | 保持 | ishikawa-hanaiguchi |
| FCR-021 | hanaiguchi | ハナイグチ | ring | B | 保持 | ishikawa-hanaiguchi |
| FCR-022 | karakasatake | カラカサタケ | cap_scales_warts | B | 保持 | ishikawa-karakasatake |
| FCR-023 | karakasatake | カラカサタケ | stem_hollow | B | 保持 | ishikawa-karakasatake |
| FCR-024 | karakasatake | カラカサタケ | stem_scales_pattern | B | 保持 | ishikawa-karakasatake |
| FCR-025 | karakasatake | カラカサタケ | ring | B | 保持 | ishikawa-karakasatake |
| FCR-026 | karakasatake | カラカサタケ | gills | A | 保持 | ishikawa-karakasatake |
| FCR-027 | yamaiguchi | ヤマイグチ | cap_sticky | B | 保持 | ishikawa-yamaiguchi |
| FCR-028 | yamaiguchi | ヤマイグチ | stem_scales_pattern | B | 保持 | ishikawa-yamaiguchi |
| FCR-029 | yamaiguchi | ヤマイグチ | pores | A | 保持 | ishikawa-yamaiguchi |
| FCR-030 | yamaiguchi | ヤマイグチ | stem_solid | A | 保持 | ishikawa-yamaiguchi |
| FCR-031 | yamaiguchi | ヤマイグチ | hairy | D | 保留 | ishikawa-yamaiguchi |
| FCR-032 | kikubanaiguchi | キクバナイグチ | cap_scales_warts | B | 保持 | ishikawa-kikubanaiguchi,ffpri-kikubanaiguchi |
| FCR-033 | kikubanaiguchi | キクバナイグチ | pores | B | 保持 | ishikawa-kikubanaiguchi,ffpri-kikubanaiguchi |
| FCR-034 | kikubanaiguchi | キクバナイグチ | blue_stain | B | 保持 | ishikawa-kikubanaiguchi,ffpri-kikubanaiguchi |
| FCR-035 | kikubanaiguchi | キクバナイグチ | stem_solid | A | 保持 | ishikawa-kikubanaiguchi |
| FCR-036 | oowaraitake | オオワライタケ | cap_fibrous_felt | B | 保持 | ishikawa-oowaraitake |
| FCR-037 | oowaraitake | オオワライタケ | stem_solid | B | 保持 | ishikawa-oowaraitake |
| FCR-038 | oowaraitake | オオワライタケ | ring | B | 保持 | ishikawa-oowaraitake |
| FCR-039 | oowaraitake | オオワライタケ | gills | A | 保持 | ishikawa-oowaraitake |
| FCR-040 | aorouji | アオロウジ | pores | B | 保持 | ishikawa-aorouji |
| FCR-041 | aorouji | アオロウジ | stem_solid | B | 保持 | ishikawa-aorouji |
| FCR-042 | urabenigasa | ウラベニガサ | cap_scales_warts | B | 保持 | ishikawa-urabenigasa |
| FCR-043 | urabenigasa | ウラベニガサ | gills | B | 保持 | ishikawa-urabenigasa |
| FCR-044 | urabenigasa | ウラベニガサ | stem_solid | B | 保持 | ishikawa-urabenigasa |
| FCR-045 | togariamigasatake | トガリアミガサタケ | head_reticulate | B | 保持 | ishikawa-togariamigasatake |
| FCR-046 | noutake | ノウタケ | granular_powdery | B | 保持 | ishikawa-noutake |
| FCR-047 | ukonhatsu | ウコンハツ | granular_powdery | B | 保持 | ishikawa-ukonhatsu |
| FCR-048 | ukonhatsu | ウコンハツ | gills | B | 保持 | ishikawa-ukonhatsu |
| FCR-049 | ukonhatsu | ウコンハツ | cap_fibrous_felt | D | 保留 | ishikawa-ukonhatsu |
| FCR-050 | enokitake | エノキタケ | cap_sticky | B | 保持 | ishikawa-enokitake |
| FCR-051 | enokitake | エノキタケ | gills | B | 保持 | ishikawa-enokitake |
| FCR-052 | enokitake | エノキタケ | stem_hollow | B | 保持 | ishikawa-enokitake |
| FCR-053 | enokitake | エノキタケ | hairy | B | 保持 | ishikawa-enokitake |
| FCR-054 | kotengutakemodoki | コテングタケモドキ | cap_sticky | B | 保持 | ishikawa-kotengutakemodoki |
| FCR-055 | kotengutakemodoki | コテングタケモドキ | cap_fibrous_felt | B | 保持 | ishikawa-kotengutakemodoki |
| FCR-056 | kotengutakemodoki | コテングタケモドキ | gills | B | 保持 | ishikawa-kotengutakemodoki |
| FCR-057 | kotengutakemodoki | コテングタケモドキ | stem_scales_pattern | B | 保持 | ishikawa-kotengutakemodoki |
| FCR-058 | kotengutakemodoki | コテングタケモドキ | ring | B | 保持 | ishikawa-kotengutakemodoki |
| FCR-059 | kotengutakemodoki | コテングタケモドキ | volva | B | 保持 | ishikawa-kotengutakemodoki |
| FCR-060 | tamagotake | タマゴタケ | cap_sticky | B | 保持 | ishikawa-tamagotake |
| FCR-061 | tamagotake | タマゴタケ | cap_striate_grooved | D | 保留 | ishikawa-tamagotake |
| FCR-062 | tamagotake | タマゴタケ | gills | B | 保持 | ishikawa-tamagotake |
| FCR-063 | tamagotake | タマゴタケ | stem_hollow | B | 保持 | ishikawa-tamagotake |
| FCR-064 | tamagotake | タマゴタケ | stem_scales_pattern | B | 保持 | ishikawa-tamagotake |
| FCR-065 | tamagotake | タマゴタケ | ring | B | 保持 | ishikawa-tamagotake |
| FCR-066 | tamagotake | タマゴタケ | volva | B | 保持 | ishikawa-tamagotake |
| FCR-067 | aragekikurage | アラゲキクラゲ | gelatinous | B | 保持 | ishikawa-aragekikurage |
| FCR-068 | aragekikurage | アラゲキクラゲ | hairy | B | 保持 | ishikawa-aragekikurage |
| FCR-069 | uraguronigaiguchi | ウラグロニガイグチ | cap_sticky | B | 保持 | ishikawa-uraguronigaiguchi |
| FCR-070 | uraguronigaiguchi | ウラグロニガイグチ | pores | B | 保持 | ishikawa-uraguronigaiguchi |
| FCR-071 | uraguronigaiguchi | ウラグロニガイグチ | stem_scales_pattern | B | 保持 | ishikawa-uraguronigaiguchi |
| FCR-072 | uraguronigaiguchi | ウラグロニガイグチ | stem_solid | A | 保持 | ishikawa-uraguronigaiguchi |
| FCR-073 | ookitunetake | オオキツネタケ | cap_depressed | B | 保持 | ishikawa-ookitunetake |
| FCR-074 | ookitunetake | オオキツネタケ | gills | B | 保持 | ishikawa-ookitunetake |
| FCR-075 | ookitunetake | オオキツネタケ | stem_solid | B | 保持 | ishikawa-ookitunetake |
| FCR-076 | seitakaiguchi | セイタカイグチ | cap_fibrous_felt | B | 保持 | ishikawa-seitakaiguchi |
| FCR-077 | seitakaiguchi | セイタカイグチ | pores | B | 保持 | ishikawa-seitakaiguchi |
| FCR-078 | seitakaiguchi | セイタカイグチ | stem_reticulate | B | 保持 | ishikawa-seitakaiguchi |
| FCR-079 | seitakaiguchi | セイタカイグチ | stem_solid | A | 保持 | ishikawa-seitakaiguchi |
| FCR-080 | seitakaiguchi | セイタカイグチ | stem_scales_pattern | B | 保持 | ishikawa-seitakaiguchi |
| FCR-081 | tamachoreitake | タマチョレイタケ | cap_depressed | B | 保持 | research-ishikawa-tamacyoreitake |
| FCR-082 | tamachoreitake | タマチョレイタケ | cap_scales_warts | B | 保持 | research-ishikawa-tamacyoreitake |
| FCR-083 | tamachoreitake | タマチョレイタケ | pores | B | 保持 | research-ishikawa-tamacyoreitake |
| FCR-084 | tamachoreitake | タマチョレイタケ | stem_solid | B | 保持 | research-ishikawa-tamacyoreitake |
| FCR-085 | tsubaaburashimeji | ツバアブラシメジ | cap_sticky | B | 保持 | ishikawa-hakusan-sizen35 |
| FCR-086 | tsubaaburashimeji | ツバアブラシメジ | stem_sticky | B | 保持 | ishikawa-hakusan-sizen35 |
| FCR-087 | miyamatamagotake | ミヤマタマゴタケ | cap_sticky | B | 保持 | research-kyoto-miyamatamagotake |
| FCR-088 | miyamatamagotake | ミヤマタマゴタケ | cap_striate_grooved | B | 保持 | research-kyoto-miyamatamagotake |
| FCR-089 | miyamatamagotake | ミヤマタマゴタケ | ring | B | 保持 | research-kyoto-miyamatamagotake |
| FCR-090 | miyamatamagotake | ミヤマタマゴタケ | volva | B | 保持 | research-kyoto-miyamatamagotake |
| FCR-091 | chichiawatake | チチアワタケ | cap_sticky | B | 保持 | research-ishikawa-titiawatake |
| FCR-092 | chichiawatake | チチアワタケ | pores | B | 保持 | research-ishikawa-titiawatake |
| FCR-093 | chichiawatake | チチアワタケ | stem_solid | B | 保持 | research-ishikawa-titiawatake |
| FCR-094 | hiratake | ヒラタケ | gills | B | 保持 | research-ishikawa-hiratake |
| FCR-095 | ooshirokarakasatake | オオシロカラカサタケ | cap_scales_warts | B | 保持 | research-ishikawa-oosirokarakasatake |
| FCR-096 | ooshirokarakasatake | オオシロカラカサタケ | gills | B | 保持 | research-ishikawa-oosirokarakasatake |
| FCR-097 | ooshirokarakasatake | オオシロカラカサタケ | ring | B | 保持 | research-ishikawa-oosirokarakasatake |
| FCR-098 | ooshirokarakasatake | オオシロカラカサタケ | stem_hollow | B | 保持 | research-ishikawa-oosirokarakasatake |
| FCR-099 | aitake | アイタケ | cap_sticky | B | 保持 | research-ishikawa-aitake |
| FCR-100 | aitake | アイタケ | gills | B | 保持 | research-ishikawa-aitake |
| FCR-101 | aitake | アイタケ | stem_solid | B | 保持 | research-ishikawa-aitake |
| FCR-102 | usuhiratake | ウスヒラタケ | gills | B | 保持 | research-ishikawa-usuhiratake |
| FCR-103 | kinigaiguchi | キニガイグチ | cap_sticky | B | 保持 | research-ishikawa-kinigaiguti |
| FCR-104 | kinigaiguchi | キニガイグチ | pores | B | 保持 | research-ishikawa-kinigaiguti |
| FCR-105 | kinigaiguchi | キニガイグチ | stem_solid | B | 保持 | research-ishikawa-kinigaiguti |
| FCR-106 | kinigaiguchi | キニガイグチ | stem_reticulate | B | 保持 | research-ishikawa-kinigaiguti |
| FCR-107 | kiamiashiiguchi | キアミアシイグチ | cap_fibrous_felt | D | 保留 | research-ishikawa-kiamiasiiguti |
| FCR-108 | kiamiashiiguchi | キアミアシイグチ | pores | B | 保持 | research-ishikawa-kiamiasiiguti |
| FCR-109 | kiamiashiiguchi | キアミアシイグチ | stem_solid | B | 保持 | research-ishikawa-kiamiasiiguti |
| FCR-110 | kiamiashiiguchi | キアミアシイグチ | stem_scales_pattern | B | 保持 | research-ishikawa-kiamiasiiguti |
| FCR-111 | kiamiashiiguchi | キアミアシイグチ | stem_reticulate | B | 保持 | research-ishikawa-kiamiasiiguti |
| FCR-112 | midorinigaiguchi | ミドリニガイグチ | cap_sticky | B | 保持 | research-ishikawa-midorinigaiguti |
| FCR-113 | midorinigaiguchi | ミドリニガイグチ | pores | B | 保持 | research-ishikawa-midorinigaiguti |
| FCR-114 | midorinigaiguchi | ミドリニガイグチ | stem_solid | B | 保持 | research-ishikawa-midorinigaiguti |
| FCR-115 | matsuouji | マツオウジ | cap_scales_warts | B | 保持 | research-ishikawa-matuouji |
| FCR-116 | matsuouji | マツオウジ | gills | B | 保持 | research-ishikawa-matuouji |
| FCR-117 | matsuouji | マツオウジ | ring | D | 保留 | research-ishikawa-matuouji |
| FCR-118 | matsuouji | マツオウジ | stem_solid | B | 保持 | research-ishikawa-matuouji |
| FCR-119 | hoteishimeji | ホテイシメジ | cap_fibrous_felt | B | 保持 | research-ishikawa-hoteisimeji |
| FCR-120 | hoteishimeji | ホテイシメジ | gills | B | 保持 | research-ishikawa-hoteisimeji |
| FCR-121 | hoteishimeji | ホテイシメジ | stem_solid | B | 保持 | research-ishikawa-hoteisimeji |
| FCR-122 | akajikou | アカジコウ | cap_sticky | B | 保持 | research-ishikawa-akajikou |
| FCR-123 | akajikou | アカジコウ | pores | B | 保持 | research-ishikawa-akajikou |
| FCR-124 | akajikou | アカジコウ | stem_reticulate | B | 保持 | research-ishikawa-akajikou |
| FCR-125 | akajikou | アカジコウ | blue_stain | B | 保持 | research-ishikawa-akajikou |
| FCR-126 | akamomitake | アカモミタケ | gills | B | 保持 | research-ishikawa-akamomitake |
| FCR-127 | akamomitake | アカモミタケ | stem_hollow | B | 保持 | research-ishikawa-akamomitake |
| FCR-128 | amitake | アミタケ | cap_sticky | B | 保持 | research-ishikawa-amitake |
| FCR-129 | amitake | アミタケ | pores | B | 保持 | research-ishikawa-amitake |
| FCR-130 | amitake | アミタケ | stem_solid | B | 保持 | research-ishikawa-amitake |
| FCR-131 | awatake | アワタケ | cap_fibrous_felt | D | 保留 | research-ishikawa-awatake |
| FCR-132 | awatake | アワタケ | pores | B | 保持 | research-ishikawa-awatake |
| FCR-133 | awatake | アワタケ | stem_solid | B | 保持 | research-ishikawa-awatake |
| FCR-134 | awatake | アワタケ | blue_stain | B | 保持 | research-ishikawa-awatake |
| FCR-135 | anzutake | アンズタケ | stem_solid | B | 保持 | research-ishikawa-anzutake |
| FCR-136 | inusenbontake | イヌセンボンタケ | gills | B | 保持 | research-ishikawa-inusenbontake |
| FCR-137 | inusenbontake | イヌセンボンタケ | hairy | B | 保持 | research-ishikawa-inusenbontake |
| FCR-138 | irogawari | イロガワリ | cap_sticky | B | 保持 | research-ishikawa-irogawari |
| FCR-139 | irogawari | イロガワリ | pores | B | 保持 | research-ishikawa-irogawari |
| FCR-140 | irogawari | イロガワリ | stem_solid | B | 保持 | research-ishikawa-irogawari |
| FCR-141 | irogawari | イロガワリ | hairy | B | 保持 | research-ishikawa-irogawari |
| FCR-142 | irogawari | イロガワリ | blue_stain | A | 保持 | research-ishikawa-irogawari |
| FCR-143 | usutake | ウスタケ | cap_depressed | B | 保持 | research-ishikawa-usutake |
| FCR-144 | urabenihoteisimeji | ウラベニホテイシメジ | cap_fibrous_felt | B | 保持 | research-ishikawa-urabenihoteisimeji |
| FCR-145 | urabenihoteisimeji | ウラベニホテイシメジ | gills | B | 保持 | research-ishikawa-urabenihoteisimeji |
| FCR-146 | urabenihoteisimeji | ウラベニホテイシメジ | stem_solid | B | 保持 | research-ishikawa-urabenihoteisimeji |
| FCR-147 | ooicyoutake | オオイチョウタケ | gills | B | 保持 | research-ishikawa-ooicyoutake |
| FCR-148 | ooicyoutake | オオイチョウタケ | stem_solid | B | 保持 | research-ishikawa-ooicyoutake |
| FCR-149 | oniiguti | オニイグチ | cap_scales_warts | B | 保持 | research-ishikawa-oniiguti |
| FCR-150 | oniiguti | オニイグチ | pores | B | 保持 | research-ishikawa-oniiguti |
| FCR-151 | oniiguti | オニイグチ | stem_solid | B | 保持 | research-ishikawa-oniiguti |
| FCR-152 | oniiguti | オニイグチ | stem_scales_pattern | B | 保持 | research-ishikawa-oniiguti |
| FCR-153 | oniiguti | オニイグチ | stem_reticulate | B | 保持 | research-ishikawa-oniiguti |
| FCR-154 | oniiguti | オニイグチ | hairy | D | 保留 | research-ishikawa-oniiguti |
| FCR-155 | oniigutimodoki | オニイグチモドキ | cap_scales_warts | B | 保持 | research-ishikawa-oniigutimodoki |
| FCR-156 | oniigutimodoki | オニイグチモドキ | pores | B | 保持 | research-ishikawa-oniigutimodoki |
| FCR-157 | oniigutimodoki | オニイグチモドキ | ring | D | 保留 | research-ishikawa-oniigutimodoki |
| FCR-158 | oniigutimodoki | オニイグチモドキ | stem_solid | B | 保持 | research-ishikawa-oniigutimodoki |
| FCR-159 | oniigutimodoki | オニイグチモドキ | stem_reticulate | B | 保持 | research-ishikawa-oniigutimodoki |
| FCR-160 | kaigaratake | カイガラタケ | hairy | B | 保持 | research-ishikawa-kaigaratake |
| FCR-161 | kakisimeji | カキシメジ | cap_sticky | B | 保持 | research-ishikawa-kakisimeji |
| FCR-162 | kakisimeji | カキシメジ | gills | B | 保持 | research-ishikawa-kakisimeji |
| FCR-163 | kakisimeji | カキシメジ | stem_hollow | B | 保持 | research-ishikawa-kakisimeji |
| FCR-164 | kabairoturutake | カバイロツルタケ | gills | B | 保持 | research-ishikawa-kabairoturutake |
| FCR-165 | kabairoturutake | カバイロツルタケ | volva | B | 保持 | research-ishikawa-kabairoturutake |
| FCR-166 | kabairoturutake | カバイロツルタケ | stem_hollow | B | 保持 | research-ishikawa-kabairoturutake |
| FCR-167 | kawaratake | カワラタケ | hairy | C | 保持 | research-ishikawa-kawaratake |
| FCR-168 | kawarihatu | カワリハツ | cap_sticky | B | 保持 | research-ishikawa-kawarihatu |
| FCR-169 | kawarihatu | カワリハツ | gills | B | 保持 | research-ishikawa-kawarihatu |
| FCR-170 | kanzoutake | カンゾウタケ | stem_solid | B | 保持 | research-ishikawa-kanzoutake |
| FCR-171 | gantake | ガンタケ | cap_scales_warts | B | 保持 | research-ishikawa-gantake |
| FCR-172 | gantake | ガンタケ | gills | B | 保持 | research-ishikawa-gantake |
| FCR-173 | gantake | ガンタケ | ring | B | 保持 | research-ishikawa-gantake |
| FCR-174 | gantake | ガンタケ | volva | B | 保持 | research-ishikawa-gantake |
| FCR-175 | gantake | ガンタケ | stem_hollow | B | 保持 | research-ishikawa-gantake |
| FCR-176 | kitunetake | キツネタケ | cap_scales_warts | B | 保持 | research-ishikawa-kitunetake |
| FCR-177 | kitunetake | キツネタケ | gills | B | 保持 | research-ishikawa-kitunetake |
| FCR-178 | kitunetake | キツネタケ | stem_solid | B | 保持 | research-ishikawa-kitunetake |
| FCR-179 | kiraratake | キララタケ | gills | B | 保持 | research-ishikawa-kiraratake |
| FCR-180 | kiraratake | キララタケ | stem_hollow | B | 保持 | research-ishikawa-kiraratake |
| FCR-181 | kusaurabenitake | クサウラベニタケ | gills | B | 保持 | research-ishikawa-kusaurabenitake |
| FCR-182 | kusaurabenitake | クサウラベニタケ | stem_hollow | B | 保持 | research-ishikawa-kusaurabenitake |
| FCR-183 | kuritake | クリタケ | gills | B | 保持 | research-ishikawa-kuritake |
| FCR-184 | kuritake | クリタケ | stem_solid | B | 保持 | research-ishikawa-kuritake |
| FCR-185 | kurohatu | クロハツ | gills | B | 保持 | research-ishikawa-kurohatu |
| FCR-186 | kurohatu | クロハツ | stem_solid | B | 保持 | research-ishikawa-kurohatu |
| FCR-187 | kurohatumodoki | クロハツモドキ | gills | B | 保持 | research-ishikawa-kurohatumodoki |
| FCR-188 | kurohatumodoki | クロハツモドキ | stem_solid | B | 保持 | research-ishikawa-kurohatumodoki |
| FCR-189 | kurorappatake | クロラッパタケ | cap_scales_warts | B | 保持 | research-ishikawa-kurorappatake |
| FCR-190 | kurorappatake | クロラッパタケ | stem_hollow | B | 保持 | research-ishikawa-kurorappatake |
| FCR-191 | koutake | コウタケ | cap_scales_warts | B | 保持 | research-ishikawa-koutake |
| FCR-192 | koutake | コウタケ | cap_depressed | B | 保持 | research-ishikawa-koutake |
| FCR-193 | koutake | コウタケ | stem_hollow | B | 保持 | research-ishikawa-koutake |
| FCR-194 | koganetake | コガネタケ | gills | B | 保持 | research-ishikawa-koganetake |
| FCR-195 | koganetake | コガネタケ | ring | B | 保持 | research-ishikawa-koganetake |
| FCR-196 | koganetake | コガネタケ | stem_solid | B | 保持 | research-ishikawa-koganetake |
| FCR-197 | koganenikawatake | コガネニカワタケ | gelatinous | B | 保持 | research-ishikawa-koganenikawatake |
| FCR-198 | kotamagotengutake | コタマゴテングタケ | cap_sticky | B | 保持 | research-ishikawa-kotamagotengutake |
| FCR-199 | kotamagotengutake | コタマゴテングタケ | gills | B | 保持 | research-ishikawa-kotamagotengutake |
| FCR-200 | kotamagotengutake | コタマゴテングタケ | ring | B | 保持 | research-ishikawa-kotamagotengutake |
| FCR-201 | kotamagotengutake | コタマゴテングタケ | volva | B | 保持 | research-ishikawa-kotamagotengutake |
| FCR-202 | kotamagotengutake | コタマゴテングタケ | stem_hollow | B | 保持 | research-ishikawa-kotamagotengutake |
| FCR-203 | kofukisarunokosikake | コフキサルノコシカケ | pores | B | 保持 | research-ishikawa-kofukisarunokosikake |
| FCR-204 | sakurasimeji | サクラシメジ | cap_sticky | B | 保持 | research-ishikawa-sakurasimeji |
| FCR-205 | sakurasimeji | サクラシメジ | gills | B | 保持 | research-ishikawa-sakurasimeji |
| FCR-206 | sakurasimeji | サクラシメジ | stem_solid | B | 保持 | research-ishikawa-sakurasimeji |
| FCR-207 | sakuratake | サクラタケ | gills | B | 保持 | research-ishikawa-sakuratake |
| FCR-208 | sakuratake | サクラタケ | stem_hollow | B | 保持 | research-ishikawa-sakuratake |
| FCR-209 | sakuratake | サクラタケ | hairy | B | 保持 | research-ishikawa-sakuratake |
| FCR-210 | saketubatake | サケツバタケ | cap_sticky | B | 保持 | research-ishikawa-saketubatake |
| FCR-211 | saketubatake | サケツバタケ | cap_scales_warts | B | 保持 | research-ishikawa-saketubatake |
| FCR-212 | saketubatake | サケツバタケ | gills | B | 保持 | research-ishikawa-saketubatake |
| FCR-213 | saketubatake | サケツバタケ | ring | B | 保持 | research-ishikawa-saketubatake |
| FCR-214 | saketubatake | サケツバタケ | stem_hollow | B | 保持 | research-ishikawa-saketubatake |
| FCR-215 | saketubatake | サケツバタケ | stem_solid | B | 保持 | research-ishikawa-saketubatake |
| FCR-216 | sasakurehitoyotake | ササクレヒトヨタケ | cap_scales_warts | B | 保持 | research-ishikawa-sasakurehitoyotake |
| FCR-217 | sasakurehitoyotake | ササクレヒトヨタケ | gills | B | 保持 | research-ishikawa-sasakurehitoyotake |
| FCR-218 | sasakurehitoyotake | ササクレヒトヨタケ | ring | B | 保持 | research-ishikawa-sasakurehitoyotake |
| FCR-219 | sasakurehitoyotake | ササクレヒトヨタケ | stem_hollow | B | 保持 | research-ishikawa-sasakurehitoyotake |
| FCR-220 | simofurisimeji | シモフリシメジ | cap_sticky | B | 保持 | research-ishikawa-simofurisimeji |
| FCR-221 | simofurisimeji | シモフリシメジ | cap_fibrous_felt | B | 保持 | research-ishikawa-simofurisimeji |
| FCR-222 | simofurisimeji | シモフリシメジ | gills | B | 保持 | research-ishikawa-simofurisimeji |
| FCR-223 | simofurisimeji | シモフリシメジ | stem_hollow | B | 保持 | research-ishikawa-simofurisimeji |
| FCR-224 | simofurisimeji | シモフリシメジ | stem_solid | B | 保持 | research-ishikawa-simofurisimeji |
| FCR-225 | syougenji | ショウゲンジ | gills | B | 保持 | research-ishikawa-syougenji |
| FCR-226 | syougenji | ショウゲンジ | ring | B | 保持 | research-ishikawa-syougenji |
| FCR-227 | syougenji | ショウゲンジ | volva | B | 保持 | research-ishikawa-syougenji |
| FCR-228 | syougenji | ショウゲンジ | stem_solid | B | 保持 | research-ishikawa-syougenji |
| FCR-229 | siroonitake | シロオニタケ | cap_scales_warts | B | 保持 | research-ishikawa-siroonitake |
| FCR-230 | siroonitake | シロオニタケ | gills | B | 保持 | research-ishikawa-siroonitake |
| FCR-231 | siroonitake | シロオニタケ | ring | B | 保持 | research-ishikawa-siroonitake |
| FCR-232 | siroonitake | シロオニタケ | stem_solid | B | 保持 | research-ishikawa-siroonitake |
| FCR-233 | sirokanosita | シロカノシタ | stem_solid | B | 保持 | research-ishikawa-sirokanosita |
| FCR-234 | suehirotake | スエヒロタケ | gills | B | 保持 | research-ishikawa-suehirotake |
| FCR-235 | suehirotake | スエヒロタケ | hairy | B | 保持 | research-ishikawa-suehirotake |
| FCR-236 | sugiedatake | スギエダタケ | gills | B | 保持 | research-ishikawa-sugiedatake |
| FCR-237 | sugiedatake | スギエダタケ | stem_hollow | B | 保持 | research-ishikawa-sugiedatake |
| FCR-238 | sugiedatake | スギエダタケ | hairy | B | 保持 | research-ishikawa-sugiedatake |
| FCR-239 | sugitake | スギタケ | cap_scales_warts | B | 保持 | research-ishikawa-sugitake |
| FCR-240 | sugitake | スギタケ | gills | B | 保持 | research-ishikawa-sugitake |
| FCR-241 | sugitake | スギタケ | ring | B | 保持 | research-ishikawa-sugitake |
| FCR-242 | sugitake | スギタケ | stem_solid | B | 保持 | research-ishikawa-sugitake |
| FCR-243 | sugihiratake | スギヒラタケ | gills | B | 保持 | research-ishikawa-sugihiratake |
| FCR-244 | sugihiratake | スギヒラタケ | hairy | B | 保持 | research-ishikawa-sugihiratake |
| FCR-245 | tamagotakemodoki | タマゴタケモドキ | cap_sticky | C | 保持 | research-ishikawa-tamagotakemodoki |
| FCR-246 | tamagotakemodoki | タマゴタケモドキ | gills | C | 保持 | research-ishikawa-tamagotakemodoki |
| FCR-247 | tamagotakemodoki | タマゴタケモドキ | volva | A | 保持 | research-ishikawa-tamagotakemodoki |
| FCR-248 | tamagotakemodoki | タマゴタケモドキ | stem_scales_pattern | A | 保持 | research-ishikawa-tamagotakemodoki |
| FCR-249 | tititake | チチタケ | granular_powdery | B | 保持 | research-ishikawa-tititake |
| FCR-250 | tititake | チチタケ | gills | B | 保持 | research-ishikawa-tititake |
| FCR-251 | tititake | チチタケ | stem_hollow | B | 保持 | research-ishikawa-tititake |
| FCR-252 | cyanamemututake | チャナメツムタケ | cap_sticky | B | 保持 | research-ishikawa-cyanamemututake |
| FCR-253 | cyanamemututake | チャナメツムタケ | cap_scales_warts | B | 保持 | research-ishikawa-cyanamemututake |
| FCR-254 | cyanamemututake | チャナメツムタケ | gills | B | 保持 | research-ishikawa-cyanamemututake |
| FCR-255 | cyanamemututake | チャナメツムタケ | stem_solid | B | 保持 | research-ishikawa-cyanamemututake |
| FCR-256 | cyanamemututake | チャナメツムタケ | stem_scales_pattern | B | 保持 | research-ishikawa-cyanamemututake |
| FCR-257 | tuetake | ツエタケ | cap_sticky | B | 保持 | research-ishikawa-tuetake |
| FCR-258 | tuetake | ツエタケ | gills | B | 保持 | research-ishikawa-tuetake |
| FCR-259 | tuetake | ツエタケ | stem_hollow | B | 保持 | research-ishikawa-tuetake |
| FCR-260 | tukiyotake | ツキヨタケ | cap_scales_warts | C | 保持 | research-ishikawa-tukiyotake |
| FCR-261 | tukiyotake | ツキヨタケ | gills | C | 保持 | research-ishikawa-tukiyotake |
| FCR-262 | tukiyotake | ツキヨタケ | stem_solid | C | 保持 | research-ishikawa-tukiyotake |
| FCR-263 | turiganetake | ツリガネタケ | pores | B | 保持 | research-ishikawa-turiganetake |
| FCR-264 | turutake | ツルタケ | cap_sticky | B | 保持 | research-ishikawa-turutake |
| FCR-265 | turutake | ツルタケ | gills | B | 保持 | research-ishikawa-turutake |
| FCR-266 | turutake | ツルタケ | volva | B | 保持 | research-ishikawa-turutake |
| FCR-267 | turutake | ツルタケ | stem_hollow | B | 保持 | research-ishikawa-turutake |
| FCR-268 | tengutake | テングタケ | cap_scales_warts | B | 保持 | research-ishikawa-tengutake |
| FCR-269 | tengutake | テングタケ | gills | B | 保持 | research-ishikawa-tengutake |
| FCR-270 | tengutake | テングタケ | ring | B | 保持 | research-ishikawa-tengutake |
| FCR-271 | tengutake | テングタケ | volva | B | 保持 | research-ishikawa-tengutake |
| FCR-272 | tengutake | テングタケ | stem_hollow | B | 保持 | research-ishikawa-tengutake |
| FCR-273 | tokiirohiratake | トキイロヒラタケ | gills | B | 保持 | research-ishikawa-tokiirohiratake |
| FCR-274 | dokukarakasatake | ドクカラカサタケ | cap_scales_warts | B | 保持 | research-ishikawa-dokukarakasatake |
| FCR-275 | dokukarakasatake | ドクカラカサタケ | gills | B | 保持 | research-ishikawa-dokukarakasatake |
| FCR-276 | dokukarakasatake | ドクカラカサタケ | ring | B | 保持 | research-ishikawa-dokukarakasatake |
| FCR-277 | dokukarakasatake | ドクカラカサタケ | stem_hollow | B | 保持 | research-ishikawa-dokukarakasatake |
| FCR-278 | dokubenitake | ドクベニタケ | cap_sticky | B | 保持 | research-ishikawa-dokubenitake |
| FCR-279 | dokubenitake | ドクベニタケ | gills | B | 保持 | research-ishikawa-dokubenitake |
| FCR-280 | nameko | ナメコ | cap_sticky | B | 保持 | research-ishikawa-nameko |
| FCR-281 | nameko | ナメコ | gills | B | 保持 | research-ishikawa-nameko |
| FCR-282 | nameko | ナメコ | ring | B | 保持 | research-ishikawa-nameko |
| FCR-283 | nameko | ナメコ | stem_solid | B | 保持 | research-ishikawa-nameko |
| FCR-284 | nameko | ナメコ | stem_sticky | B | 保持 | research-ishikawa-nameko |
| FCR-285 | naratake | ナラタケ | cap_scales_warts | B | 保持 | research-ishikawa-naratake |
| FCR-286 | naratake | ナラタケ | gills | B | 保持 | research-ishikawa-naratake |
| FCR-287 | naratake | ナラタケ | ring | B | 保持 | research-ishikawa-naratake |
| FCR-288 | naratakemodoki | ナラタケモドキ | cap_scales_warts | B | 保持 | research-ishikawa-naratakemodoki |
| FCR-289 | naratakemodoki | ナラタケモドキ | gills | B | 保持 | research-ishikawa-naratakemodoki |
| FCR-290 | naratakemodoki | ナラタケモドキ | stem_solid | B | 保持 | research-ishikawa-naratakemodoki |
| FCR-291 | nigakuritake | ニガクリタケ | gills | B | 保持 | research-ishikawa-nigakuritake |
| FCR-292 | nigakuritake | ニガクリタケ | ring | D | 保留 | research-ishikawa-nigakuritake |
| FCR-293 | nisekurohatu | ニセクロハツ | cap_depressed | B | 保持 | research-ishikawa-nisekurohatu |
| FCR-294 | nisekurohatu | ニセクロハツ | gills | B | 保持 | research-ishikawa-nisekurohatu |
| FCR-295 | nisekurohatu | ニセクロハツ | stem_solid | B | 保持 | research-ishikawa-nisekurohatu |
| FCR-296 | numeriiguti | ヌメリイグチ | cap_sticky | B | 保持 | research-ishikawa-numeriiguti |
| FCR-297 | numeriiguti | ヌメリイグチ | pores | B | 保持 | research-ishikawa-numeriiguti |
| FCR-298 | numeriiguti | ヌメリイグチ | ring | B | 保持 | research-ishikawa-numeriiguti |
| FCR-299 | numerisugitake | ヌメリスギタケ | cap_sticky | B | 保持 | research-ishikawa-numerisugitake |
| FCR-300 | numerisugitake | ヌメリスギタケ | cap_scales_warts | B | 保持 | research-ishikawa-numerisugitake |
| FCR-301 | numerisugitake | ヌメリスギタケ | gills | B | 保持 | research-ishikawa-numerisugitake |
| FCR-302 | numerisugitake | ヌメリスギタケ | ring | B | 保持 | research-ishikawa-numerisugitake |
| FCR-303 | numerisugitake | ヌメリスギタケ | stem_hollow | B | 保持 | research-ishikawa-numerisugitake |
| FCR-304 | numerisugitake | ヌメリスギタケ | stem_sticky | B | 保持 | research-ishikawa-numerisugitake |
| FCR-305 | hatakesimeji | ハタケシメジ | gills | B | 保持 | research-ishikawa-hatakesimeji |
| FCR-306 | hatakesimeji | ハタケシメジ | stem_solid | B | 保持 | research-ishikawa-hatakesimeji |
| FCR-307 | hatinosutake | ハチノスタケ | cap_scales_warts | B | 保持 | research-ishikawa-hatinosutake |
| FCR-308 | hatinosutake | ハチノスタケ | pores | B | 保持 | research-ishikawa-hatinosutake |
| FCR-309 | hatutake | ハツタケ | cap_depressed | B | 保持 | research-ishikawa-hatutake |
| FCR-310 | hatutake | ハツタケ | gills | B | 保持 | research-ishikawa-hatutake |
| FCR-311 | hatutake | ハツタケ | stem_hollow | B | 保持 | research-ishikawa-hatutake |
| FCR-312 | haratake | ハラタケ | gills | B | 保持 | research-ishikawa-haratake |
| FCR-313 | haratake | ハラタケ | ring | B | 保持 | research-ishikawa-haratake |
| FCR-314 | haratake | ハラタケ | stem_hollow | B | 保持 | research-ishikawa-haratake |
| FCR-315 | haratake | ハラタケ | stem_solid | B | 保持 | research-ishikawa-haratake |
| FCR-316 | hidahatake | ヒダハタケ | cap_sticky | B | 保持 | research-ishikawa-hidahatake |
| FCR-317 | hidahatake | ヒダハタケ | gills | B | 保持 | research-ishikawa-hidahatake |
| FCR-318 | hidahatake | ヒダハタケ | stem_solid | B | 保持 | research-ishikawa-hidahatake |
| FCR-319 | hitoyotake | ヒトヨタケ | cap_scales_warts | B | 保持 | research-ishikawa-hitoyotake |
| FCR-320 | hitoyotake | ヒトヨタケ | gills | B | 保持 | research-ishikawa-hitoyotake |
| FCR-321 | hitoyotake | ヒトヨタケ | ring | D | 保留 | research-ishikawa-hitoyotake |
| FCR-322 | hitoyotake | ヒトヨタケ | stem_hollow | B | 保持 | research-ishikawa-hitoyotake |
| FCR-323 | bunasimeji | ブナシメジ | gills | B | 保持 | research-ishikawa-bunasimeji |
| FCR-324 | bunasimeji | ブナシメジ | stem_solid | B | 保持 | research-ishikawa-bunasimeji |
| FCR-325 | honsimeji | ホンシメジ | gills | B | 保持 | research-ishikawa-honsimeji |
| FCR-326 | honsimeji | ホンシメジ | stem_solid | B | 保持 | research-ishikawa-honsimeji |
| FCR-327 | maitake | マイタケ | pores | B | 保持 | research-ishikawa-maitake |
| FCR-328 | maitake | マイタケ | stem_solid | B | 保持 | research-ishikawa-maitake |
| FCR-329 | matutake | マツタケ | cap_scales_warts | B | 保持 | research-ishikawa-matutake |
| FCR-330 | matutake | マツタケ | gills | B | 保持 | research-ishikawa-matutake |
| FCR-331 | matutake | マツタケ | ring | B | 保持 | research-ishikawa-matutake |
| FCR-332 | matutake | マツタケ | stem_solid | B | 保持 | research-ishikawa-matutake |
| FCR-333 | mannentake | マンネンタケ | pores | B | 保持 | research-ishikawa-mannentake |
| FCR-334 | mannentake | マンネンタケ | stem_solid | B | 保持 | research-ishikawa-mannentake |
| FCR-335 | mukitake | ムキタケ | gills | B | 保持 | research-ishikawa-mukitake |
| FCR-336 | mukitake | ムキタケ | stem_solid | B | 保持 | research-ishikawa-mukitake |
| FCR-337 | mukitake | ムキタケ | hairy | B | 保持 | research-ishikawa-mukitake |
| FCR-338 | murasakisimeji | ムラサキシメジ | gills | B | 保持 | research-ishikawa-murasakisimeji |
| FCR-339 | murasakisimeji | ムラサキシメジ | stem_solid | B | 保持 | research-ishikawa-murasakisimeji |
| FCR-340 | murasakifuusentake | ムラサキフウセンタケ | gills | B | 保持 | research-ishikawa-murasakifuusentake |
| FCR-341 | murasakifuusentake | ムラサキフウセンタケ | stem_solid | B | 保持 | research-ishikawa-murasakifuusentake |
| FCR-342 | murasakifuusentake | ムラサキフウセンタケ | hairy | B | 保持 | research-ishikawa-murasakifuusentake |
| FCR-343 | yakoutake | ヤコウタケ | cap_sticky | B | 保持 | research-ishikawa-yakoutake |
| FCR-344 | yakoutake | ヤコウタケ | gills | B | 保持 | research-ishikawa-yakoutake |
| FCR-345 | yakoutake | ヤコウタケ | stem_hollow | B | 保持 | research-ishikawa-yakoutake |
| FCR-346 | yakoutake | ヤコウタケ | gelatinous | B | 保持 | research-ishikawa-yakoutake |
| FCR-347 | yamadoritakemodoki | ヤマドリタケモドキ | cap_sticky | B | 保持 | research-ishikawa-yamadoritakemodoki |
| FCR-348 | yamadoritakemodoki | ヤマドリタケモドキ | pores | B | 保持 | research-ishikawa-yamadoritakemodoki |
| FCR-349 | yamadoritakemodoki | ヤマドリタケモドキ | stem_solid | B | 保持 | research-ishikawa-yamadoritakemodoki |
| FCR-350 | yamadoritakemodoki | ヤマドリタケモドキ | stem_scales_pattern | B | 保持 | research-ishikawa-yamadoritakemodoki |
| FCR-351 | yamadoritakemodoki | ヤマドリタケモドキ | stem_reticulate | B | 保持 | research-ishikawa-yamadoritakemodoki |
| FCR-352 | rurihatutake | ルリハツタケ | cap_sticky | B | 保持 | research-ishikawa-rurihatutake |
| FCR-353 | rurihatutake | ルリハツタケ | gills | B | 保持 | research-ishikawa-rurihatutake |
| FCR-354 | rurihatutake | ルリハツタケ | stem_hollow | B | 保持 | research-ishikawa-rurihatutake |
| FCR-355 | rurihatutake | ルリハツタケ | stem_solid | B | 保持 | research-ishikawa-rurihatutake |
| FCR-356 | shirotamagotengutake | シロタマゴテングタケ | gills | B | 保持 | research-mhlw-0000142708 |
| FCR-357 | shirotamagotengutake | シロタマゴテングタケ | ring | B | 保持 | research-mhlw-0000142708 |
| FCR-358 | shirotamagotengutake | シロタマゴテングタケ | volva | B | 保持 | research-mhlw-0000142708 |
| FCR-359 | benitengutake | ベニテングタケ | cap_scales_warts | B | 保持 | research-mhlw-0000142728 |
| FCR-360 | benitengutake | ベニテングタケ | gills | B | 保持 | research-mhlw-0000142728 |
| FCR-361 | benitengutake | ベニテングタケ | ring | B | 保持 | research-mhlw-0000142728 |
| FCR-362 | benitengutake | ベニテングタケ | stem_scales_pattern | B | 保持 | research-mhlw-0000142728 |
| FCR-363 | dokusasako | ドクササコ | gills | B | 保持 | research-mhlw-0000142713 |
| FCR-364 | dokusasako | ドクササコ | cap_depressed | B | 保持 | research-mhlw-0000142713 |
| FCR-365 | dokusasako | ドクササコ | stem_hollow | B | 保持 | research-mhlw-0000142713 |
| FCR-366 | dokusasako | ドクササコ | stem_solid | B | 保持 | research-mhlw-0000142713 |
| FCR-367 | dokuyamadori | ドクヤマドリ | pores | B | 保持 | research-mhlw-0000143400 |
| FCR-368 | dokuyamadori | ドクヤマドリ | blue_stain | B | 保持 | research-mhlw-0000143400 |
| FCR-369 | nezumishimeji | ネズミシメジ | gills | B | 保持 | research-mhlw-0000143409 |
| FCR-370 | nezumishimeji | ネズミシメジ | stem_scales_pattern | B | 保持 | research-mhlw-0000143409 |
| FCR-371 | haiiroshimeji | ハイイロシメジ | gills | B | 保持 | research-mhlw-0000143411 |
| FCR-372 | haiiroshimeji | ハイイロシメジ | cap_depressed | B | 保持 | research-mhlw-0000143411 |
| FCR-373 | hikageshibiretake | ヒカゲシビレタケ | cap_sticky | B | 保持 | research-mhlw-0000143413 |
| FCR-374 | hikageshibiretake | ヒカゲシビレタケ | gills | B | 保持 | research-mhlw-0000143413 |
| FCR-375 | hikageshibiretake | ヒカゲシビレタケ | stem_hollow | B | 保持 | research-mhlw-0000143413 |
| FCR-376 | hikageshibiretake | ヒカゲシビレタケ | blue_stain | B | 保持 | research-mhlw-0000143413 |
| FCR-377 | amigasatake | アミガサタケ | head_reticulate | B | 保持 | research-fukui-amigasatake |
| FCR-378 | yanagimatsutake | ヤナギマツタケ | ring | C | 保持 | research-chiba-yanagimatsutake |
| FCR-379 | shiitake | シイタケ | cap_scales_warts | B | 保持 | research-mhlw-0000142114 |
| FCR-380 | shiitake | シイタケ | gills | B | 保持 | research-mhlw-0000142114 |
| FCR-381 | kinugasatake | キヌガサタケ | head_reticulate | B | 保持 | research-ishikawa-kinugasatake |
| FCR-382 | suppontake | スッポンタケ | head_reticulate | B | 保持 | research-ishikawa-suppontake |
| FCR-383 | sanagitake | サナギタケ | granular_powdery | B | 保持 | research-ishikawa-sanagitake |

## 入力ファイルの不変性

- `upload/feature-facets-final-candidate-2026-10-03(1).json`：`57d1ba6b700e1dbff6d3980a55d9bc8718ab8508006c747c0d1c72800d7fb5f4`
- `upload/phase4c9-feature-facet-contract-summary-2026-10-03(1).md`：`178a13ec34438cb43002a6d7b2fa4858dffa4cc90d634c0339f88c3d559cecae`
- `upload/sources-final-candidate-2026-10-03(1).json`：`d5213f1cf0881af1c60ea949c0321ae0eb854daa3f300135dae9e9f9ad2fdb66`
- `upload/phase4c9-feature-facet-contract-mismatches-2026-10-03(1).csv`：`b915dc229e07ffb08bc1215c51477f856a0ccc0b309b71f988423312d0c1861d`
- `upload/mushroom-master-final-candidate-2026-10-03(1).json`：`2ce8cfc61726ef04bb6f4bba26c42511e2c0bf1d4017b9e87e0a359d61decca4`

入力5ファイルのSHA-256が作業開始時と一致。原データ・baseline・reviewedに書き込む操作は行っていない。GitHub操作はfeature_ui.pyの読取りだけ。

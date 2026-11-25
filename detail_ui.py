"""Evidence-backed subject detail view models and HTML rendering."""

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re


FOOD_SAFETY_LABELS = {
    "poisonous_confirmed": "公的・専門資料には毒性の記載があります",
    "edibility_reported": "資料には食用との記載があります",
    "unknown": "食毒の区分は確認できていません",
}

GENERIC_FOOD_NOTE = (
    "食用可否の自己判断には使用しない。"
    "毒性の記録がないことは安全を意味しない。"
)

FOOD_NOTE_REPLACEMENTS = (
    ("source report", "出典資料の記載"),
    ("food safety", "食毒情報"),
    ("edibility status", "食用可否の区分"),
    ("schema", "データ構造"),
    ("project", "本サイト"),
    ("source", "出典資料"),
    ("edibility", "食用可否"),
    ("master", "図鑑データ"),
)

# This source note occurs on many species. The approved extended wording is
# specific to the reviewed Yamadoritakemodoki detail page, not a global rewrite.
YAMADORITAKEMODOKI_SOURCE_NOTE = (
    "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 "
    "石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。"
)
YAMADORITAKEMODOKI_DISPLAY_NOTE = (
    "石川県の資料では、食毒欄に「食」と記載されています。"
    "これは公的資料に食用との記載があることを示すもので、"
    "実際に採ったキノコの安全性を保証するものではありません。"
    "毒性についての記載がなくても安全とは限らないため、"
    "食べられるかどうかを自分で判断するためには使わないでください。"
)

# Exact source-note match: never infer an edible mushroom from a similar name.
SHIITAKE_SOURCE_NOTE = (
    "食用可否の自己判断には使用しない。"
    "毒性の記録がないことは安全を意味しない。 "
    "農林水産省が食用きのこと明記した利用記録。"
    "野生個体の判定には使用しない。"
)
SHIITAKE_DISPLAY_NOTE = (
    "農林水産省の資料では、シイタケを食用のキノコとして紹介しています。"
    "ただし、この情報だけで野生のキノコの種類や安全性を判断することはできません。"
)


FOOD_NOTE_SENTENCES = {
    "石川県の公的図鑑が「食」と記載しているというsource report。projectによる安全判定ではない。": (
        "石川県の公的図鑑では「食」と記載されています。"
        "これは出典資料の記載を示すもので、本サイトが食用可否を判定したものではありません。"
    ),
}


# Explicitly reviewed reader-facing sentences for the 51 linked mushroom pages.
# Each entry pins the exact source note and canonical name. When source data changes,
# the old prose must not be silently applied to different scientific evidence.
FOOD_NOTE_REVIEWED = {
    "kaentake": ("カエンタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", None),
    "dokutsurutake": ("ドクツルタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", None),
    "chichiawatake": ("チチアワタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「要注意」。", "石川県の資料では、食毒欄に「要注意」と記載されています。"),
    "hiratake": ("ヒラタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "yanagimatsutake": ("ヤナギマツタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 森林総合研究所がヤナギマツタケの食用利用を明記。食用記述の記録であり同定・安全の保証ではない。", "森林総合研究所の資料には、ヤナギマツタケが食用として利用されているとの記載があります。ただし、この記載は、採取したキノコの種類や安全性を保証するものではありません。"),
    "chaamigasatake": ("チャアミガサタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", None),
    "ooshirokarakasatake": ("オオシロカラカサタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。", "石川県の資料では、食毒欄に「毒」と記載されています。"),
    "aitake": ("アイタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "matsuouji": ("マツオウジ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "usuhiratake": ("ウスヒラタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "kiirosuppontake": ("キイロスッポンタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", None),
    "akayamadori": ("アカヤマドリ", "石川県の公的図鑑が「食」と記載しているというsource report。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の公的図鑑では、食毒欄に「食」と記載されています。これは資料上の区分であり、実際に採取したキノコの安全性を保証するものではありません。"),
    "hiromenotogariamigasatake": ("ヒロメノトガリアミガサタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", None),
    "amigasatake": ("アミガサタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。福井市自然史博物館は食用利用と生食中毒を併記。今回単純な食用・毒の区分へ一般化せずunknownを保持。", "福井市自然史博物館の資料には、食用として利用されていることと、生食による中毒の両方が記載されています。そのため、食用・毒のどちらか一方には分類していません。"),
    "kikurage": ("キクラゲ", "石川県資料がキクラゲを「食」と記載。これはsource reportであり安全保証ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、キクラゲの食毒欄に「食」と記載されています。ただし、資料上の記載だけで採取したキノコの安全性は判断できません。"),
    "hebikinokomodoki": ("ヘビキノコモドキ", "石川県林業試験場の公的図鑑が「毒」と明示。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県林業試験場の公的図鑑では、食毒欄に「毒」と記載されています。"),
    "hanaiguchi": ("ハナイグチ", "石川県の公的図鑑が「食」と記載。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "karakasatake": ("カラカサタケ", "石川県の公的図鑑が「食」と記載。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 島根県の公的一覧には「カラカサタケ（注意）」と掲載される。注意理由は当該一覧だけでは未確認であり、毒性・毒成分・発症条件を推測しない。資料上の食用記録は安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。一方、島根県の公的一覧には「カラカサタケ（注意）」と掲載されています。注意が必要な詳しい理由は確認できていないため、毒性や発症条件を推測していません。食用との記載があっても、安全性を保証するものではありません。"),
    "yamaiguchi": ("ヤマイグチ", "石川県の公的図鑑が「食」と記載。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "kikubanaiguchi": ("キクバナイグチ", "石川県の公的図鑑が「食」と記載。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "kurokawa": ("クロカワ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", None),
    "oowaraitake": ("オオワライタケ", "石川県の公的図鑑が「毒」と明示している。毒成分名は今回sourceに無いため追加しない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の公的図鑑では、食毒欄に「毒」と記載されています。毒成分名については、今回参考にした資料からは確認できていません。"),
    "aorouji": ("アオロウジ", "石川県の公的図鑑が「食」と記載。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "urabenigasa": ("ウラベニガサ", "石川県の公的図鑑が「食」と記載。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "togariamigasatake": ("トガリアミガサタケ", "石川県の公的図鑑が「食」と記載しているというsource report。安全保証ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 島根県はトガリアミガサタケの加熱不足による中毒を注意喚起している。資料上の食用記録とこの条件付き毒性を併記し、加熱すれば安全という保証にはしない。", "石川県の資料では、食毒欄に「食」と記載されています。一方、島根県の資料では、加熱不足による中毒に注意を呼びかけています。食用との記載があっても安全性を保証するものではなく、加熱すれば安全とも判断できません。"),
    "noutake": ("ノウタケ", "石川県資料の記載は「幼時食」。若い時期についてのsource reportであり、projectによる安全判定ではない。「食」一般へ意味を拡張しない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「幼時食」と記載されています。これは若い時期についての利用記録であり、成長したものを含めて食べられるという意味ではありません。"),
    "ukonhatsu": ("ウコンハツ", "sourceの食毒欄は「不明」。毒性情報がないことや不明であることは安全を意味しない。 石川県の食毒欄は「不明」。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「不明」と記載されています。毒性について記載がないことは、安全性が確認されたという意味ではありません。"),
    "enokitake": ("エノキタケ", "石川県の公的図鑑が「食」と記載。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "kinigaiguchi": ("キニガイグチ", "今回指定した一次・公的/大学sourceでは、food safetyをmasterへ登録するための情報を使用しない。安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「食」と記載されています。ただし、今回参照した一次資料・公的資料・大学資料の情報からは、食用可否を確定する根拠を追加していません。資料上の記載だけで安全とは判断できません。"),
    "kotengutakemodoki": ("コテングタケモドキ", "石川県の公的図鑑が「毒」と明示。毒成分名は今回sourceにないため追加しない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の公的図鑑では、食毒欄に「毒」と記載されています。毒成分名については、今回参考にした資料からは確認できていません。"),
    "tamagotake": ("タマゴタケ", "石川県の公的図鑑が「食」と記載。projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "aragekikurage": ("アラゲキクラゲ", "公的資料が「食」と記載したsource reportであり、projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "参考にした公的資料では、食用のキノコとして記載されています。ただし、実際に採取したキノコの安全性を保証するものではありません。"),
    "uraguronigaiguchi": ("ウラグロニガイグチ", "石川県に「食」、関東森林管理局2020年資料に「食用」の記録があるため、edibility_reportedは資料掲載評価として保持する。現在の摂食安全性は未確定。島根県の毒・注意対象ギャラリーにも掲載されるが個別の区分理由は未確認。林野庁資料の仮称類似種と、Sutorius eximius種複合体・日本産和名との対応は未解決。北米の同学名下には加熱後の中毒報告があるが、日本産への同一性を確定していない。食用可否の自己判断に使用せず、加熱による安全も保証しない。空の毒成分欄は無毒を意味しない。", "石川県の資料では「食」、関東森林管理局の2020年の資料では「食用」と記載されています。一方、島根県の毒・注意対象の写真一覧にも掲載されていますが、その詳しい理由は確認できていません。また、林野庁資料にある仮称の類似種や、Sutorius eximius種複合体と日本産の和名との対応も確定していません。北米では同じ学名のもとで加熱後の中毒が報告されていますが、日本産と同じ種であるかは確認できていません。食用との記載があっても安全とは判断できず、加熱すれば安全ともいえません。毒成分欄が空欄でも、無毒という意味ではありません。"),
    "ookitunetake": ("オオキツネタケ", "公的資料が「食」と記載したsource reportであり、projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "参考にした公的資料では、食用のキノコとして記載されています。ただし、実際に採取したキノコの安全性を保証するものではありません。"),
    "kiamiashiiguchi": ("キアミアシイグチ", "食用可否を今回確定していない。情報がないことは安全を意味しない。 石川県の食毒欄は「不食」。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "食用かどうかは、今回確認した資料では確定していません。石川県の資料では、食毒欄に「不食」と記載されています。毒性が確認されたという意味に置き換えず、資料の記載をそのまま紹介しています。"),
    "seitakaiguchi": ("セイタカイグチ", "公的資料が「食」と記載したsource reportであり、projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "参考にした公的資料では、食用のキノコとして記載されています。ただし、実際に採取したキノコの安全性を保証するものではありません。"),
    "tamachoreitake": ("タマチョレイタケ", "公的資料が「食」と記載したsource reportであり、projectによる安全判定ではない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "参考にした公的資料では、食用のキノコとして記載されています。ただし、実際に採取したキノコの安全性を保証するものではありません。"),
    "tsubaaburashimeji": ("ツバアブラシメジ", "資料には地域での食利用記載があるが、高山帯個体との同一性にはDNA解析が必要と資料自身が述べるため、projectとしてedibilityを一般化しない。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "参考にした資料には、地域で食用として利用されているとの記載があります。ただし、高山帯の個体と同じ種かどうかについては、資料でもDNA解析が必要とされています。そのため、食用との記載を本種全体に当てはめてはいません。"),
    "hoteishimeji": ("ホテイシメジ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。石川県の食毒欄は「要注意」。厚労科研2021研究分担報告書の表4注1は、食べる前後の飲酒で悪酔いのような中毒を起こすと注意している。unknownは無毒・安全を意味しない。飲酒しなければ安全とも判断しない。", "石川県の資料では、食毒欄に「要注意」と記載されています。2021年の厚生労働科学研究の報告書には、食べる前後に飲酒すると、悪酔いに似た中毒を起こすと記載されています。ただし、お酒を飲まなければ安全という意味ではありません。"),
    "midorinigaiguchi": ("ミドリニガイグチ", "食用可否を今回確定していない。情報がないことは安全を意味しない。 石川県の食毒欄は「不明」。 食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。", "食用かどうかは、今回確認した資料では確定していません。石川県の資料でも、食毒欄は「不明」と記載されています。"),
    "miyamatamagotake": ("ミヤマタマゴタケ", "食毒は未確認。unknownおよび空のtoxinsは無毒・安全を意味しない。食用可否の自己判断には使用しない。", "食毒については確認できていません。毒成分の記載がないことも、安全性を示すものではありません。"),
    "akajikou": ("アカジコウ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "usutake": ("ウスタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。", "石川県の資料では、食毒欄に「毒」と記載されています。"),
    "syougenji": ("ショウゲンジ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "siroonitake": ("シロオニタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。", "石川県の資料では、食毒欄に「毒」と記載されています。"),
    "tititake": ("チチタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "matutake": ("マツタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "yamadoritakemodoki": ("ヤマドリタケモドキ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは公的資料に食用との記載があることを示すもので、実際に採ったキノコの安全性を保証するものではありません。毒性についての記載がなくても安全とは限らないため、食べられるかどうかを自分で判断するためには使わないでください。"),
    "benitengutake": ("ベニテングタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 厚生労働省が中毒症状・毒性を記載した記録であり、採取個体の同定資料ではない。 厚生労働省は中毒症状または事例を記載。", "厚生労働省の資料には、このキノコの毒性や中毒症状・事例についての記載があります。ただし、この情報だけで、採取したキノコの種類を判断することはできません。"),
    "dokuyamadori": ("ドクヤマドリ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 厚生労働省が中毒症状・毒性を記載した記録であり、採取個体の同定資料ではない。 厚生労働省は中毒症状または事例を記載。", "厚生労働省の資料には、このキノコの毒性や中毒症状・事例についての記載があります。ただし、この情報だけで、採取したキノコの種類を判断することはできません。"),
    "shiitake": ("シイタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 農林水産省が食用きのこと明記した利用記録。野生個体の判定には使用しない。", "農林水産省の資料では、シイタケを食用のキノコとして紹介しています。ただし、この情報だけで野生のキノコの種類や安全性を判断することはできません。"),
}


# Four additional, already-named gallery subjects from the reviewed #149
# candidate set. Never show these polished words unless source note and name
# still match exactly. Human-reviewed master data and food status stay intact.
NEXT_FOUR_SOURCE_NOTE = (
    "食用可否の自己判断には使用しない。"
    "毒性の記録がないことは安全を意味しない。 "
    "石川県の食毒欄は「食」。"
    "公的資料に食用記述があるという記録であり安全保証ではない。"
)
NEXT_FOUR_DISPLAY_NOTE = (
    "石川県の資料では、食毒欄に「食」と記載されています。"
    "これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"
)
NEXT_FOUR_FOOD_NOTE_REVIEWED = {
    "akamomitake": ("アカモミタケ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
    "amitake": ("アミタケ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
    "urabenihoteisimeji": ("ウラベニホテイシメジ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
    "oniigutimodoki": ("オニイグチモドキ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
}


# Draft-only display candidates for the third group of four existing pages.
# Always match mushroom ID, canonical Japanese name, and exact source note.
# The source master, food status, warnings and citations remain untouched.
THIRD_FOUR_FOOD_NOTE_CANDIDATES = {
    "kaninotume": ("カニノツメ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。", "石川県の資料では、食毒欄に「不食」と記載されています。この記載だけで毒性が確認されたとは判断できません。"),
    "kawarihatu": ("カワリハツ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "gantake": ("ガンタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。 厚労科研2021研究分担報告書の表4注2は、以前の「食用にできるが生食は毒」という扱いと区別し、現在は食用にすべきでないとする注意を記載する。加熱による安全性は保証しない。毒成分は追加推定しない。", "石川県の資料では、食毒欄に「毒」と記載されています。また、2021年の厚生労働科学研究の報告書には、以前は「食用にできるが生食は毒」とされていたものの、現在は食用にすべきでないという注意が記載されています。加熱すれば安全だと判断することはできません。"),
    "kitunetake": ("キツネタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
}


# Fourth group: evidence-exact, source-pinned reader prose; retain the master unchanged.
# Kiraratake has conflicting public source assessments, so its visible label
# must not imply that the 'edibility_reported' master status proves edibility.
FOURTH_FOUR_FOOD_NOTE_REVIEWED = {
    "kiraratake": ("キララタケ", "石川県の「食」は食用記録として保持するが、島根県中山間地域研究センター2025年記事はキララタケを「毒」と明示し、資料間競合がある。中国ではCoprinellus micaceus名の消化器症状報告があるが、加熱・飲酒条件と各症例の同定根拠の細部は未確認。旧化学文献は同じクロマトグラフィー挙動の物質という留保を含み、日本産キララタケのコプリン含有や飲酒時のみの毒性は確定しない。edibility_reportedを安全保証や摂食推奨と解釈しない。食用可否の自己判断に使用せず、空の毒成分欄は無毒を意味しない。", "石川県の資料では「食」と記載されていますが、島根県中山間地域研究センターの2025年の観察会報告では「毒」と記載されています。中国で2021年に発生した中毒についても、Coprinellus micaceusという学名で消化器症状を伴う事例が報告されています。ただし、日本産のキララタケとの対応や、症例の詳しい同定方法、加熱・飲酒との関係は確認できていません。過去の化学研究にはコプリンまたは同じ分析上の挙動を示す物質の記載がありますが、日本産キララタケにコプリンが含まれると確定したものではありません。資料によって評価が異なるため、安全に食べられるとは判断できません。"),
    "kutibenitake": ("クチベニタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。", "石川県の資料では、食毒欄に「不食」と記載されています。これは「毒」と同じ意味ではなく、この情報だけで毒性が確認されたとは判断できません。"),
    "kuritake": ("クリタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
    "kotamagotengutake": ("コタマゴテングタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。", "石川県の資料では、食毒欄に「毒」と記載されています。この記載だけで、採取したキノコの種類や安全性を判断することはできません。"),
}
KIRARATAKE_CONFLICT_LABEL = "資料によって食毒の記載が異なります"


# Fifth group: pin mushroom ID, source canonical name and exact original notes.
# Never change source master, underlying food status, source IDs or safety warning.
FIFTH_FOUR_FOOD_NOTE_REVIEWED = {
    "turutake": ("ツルタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの種類や安全性を保証するものではありません。"),
    "tengutake": ("テングタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。 厚生労働省は中毒症状または事例を記載。", "石川県の資料では、食毒欄に「毒」と記載されています。厚生労働省の資料にも、嘔吐や下痢などの消化器症状のほか、神経系の症状を伴う中毒事例が記載されています。"),
    "nigakuritake": ("ニガクリタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。 厚生労働省は中毒症状または事例を記載。 厚生労働省掲載のファシキュロール類等は報告成分として扱う。同資料は重篤・致死的中毒の毒性本体が明確でないことも記載しており、列挙成分が死亡原因と確定したという意味にしない。", "石川県の資料では、食毒欄に「毒」と記載されています。厚生労働省の資料には、嘔吐、下痢、腹痛などの症状や死亡例を含む重篤な中毒事例が記載されています。ファシキュロール類などの含有成分も報告されていますが、致死的な中毒を起こす原因物質が確定したという意味ではありません。"),
    "numeriiguti": ("ヌメリイグチ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。これは資料上の区分であり、採取したキノコの安全性を保証するものではありません。"),
}

# Sixth group: keep original source notes and food-safety status unchanged.
# The reviewed display prose is applied only on exact ID, Japanese name and source note.
SIXTH_FOUR_FOOD_NOTE_REVIEWED = {
    "numerisugitake": ("ヌメリスギタケ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
    "hatakesimeji": ("ハタケシメジ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
    "hatinosutake": ("ハチノスタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。", "石川県の資料では、食毒欄に「不食」と記載されています。これは「毒」と同じ意味ではなく、この記載だけで毒性が確認されたとは判断できません。"),
    "hatutake": ("ハツタケ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
}

# Seventh group: source-backed, human-reviewable notes; do not alter master data.
# Hokoritake's source explicitly says 幼時食: do not broaden this to all ages.
SEVENTH_FOUR_FOOD_NOTE_REVIEWED = {
    "haratake": ("ハラタケ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
    "hokoritake": ("ホコリタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「幼時食」。幼時に限定された食利用の記録であり、時期を限定しない食用判断へ拡張しない。公的資料に食用記述があるという記録であり安全保証ではない。", "石川県の資料では、食毒欄に「幼時食」と記載されています。これは若い時期に限った食用の記録であり、成長した個体まで食用と判断できるものではありません。また、採取したキノコの安全性を保証するものでもありません。"),
    "mukitake": ("ムキタケ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
    "rurihatutake": ("ルリハツタケ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
}

# Eighth group: preserve source exactness, including caveats about a caution
# listing and a raw-consumption warning. No species is re-identified here.
EIGHTH_ANZUTAKE_WARNING_LABEL = "資料に食用記載と注意情報があります"
EIGHTH_FOUR_FOOD_NOTE_REVIEWED = {
    "anzutake": ("アンズタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。 島根県の公的一覧には「アンズタケ（注意）」と掲載される。注意理由は当該一覧だけでは未確認であり、毒性・毒成分・発症条件を推測しない。資料上の食用記録は安全保証ではない。", "石川県の資料では、食毒欄に「食」と記載されています。一方、島根県の資料では「アンズタケ（注意）」として掲載されています。この一覧だけでは注意が必要な理由までは確認できないため、毒性や発症条件を決めつけることはできません。資料の食用記載は、採取したキノコの安全性を保証するものではありません。"),
    "kakisimeji": ("カキシメジ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。 厚生労働省は中毒症状または事例を記載。", "石川県の資料では、食毒欄に「毒」と記載されています。厚生労働省の資料には、嘔吐や下痢などの中毒症状・事例が記載されています。ただし、これらの資料だけで写真に写る個体の種を特定できるわけではありません。"),
    "kabairoturutake": ("カバイロツルタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。条件付き毒性記述／注意記述があるため食用判定へ変換せずunknownとした。", "石川県の資料では、食毒欄に「食」と記載されています。一方、森林総合研究所の資料には「生食すると毒だといわれる」と記載されています。食用という記載だけで安全とは判断できず、加熱すれば安全という意味でもありません。"),
    "kusaurabenitake": ("クサウラベニタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「毒」。 厚生労働省は中毒症状または事例を記載。", "石川県の資料では、食毒欄に「毒」と記載されています。厚生労働省の資料には、嘔吐や下痢などの中毒症状・事例が記載されています。ただし、これらの資料だけで写真に写る個体の種を特定できるわけではありません。"),
}

# Ninth group: source-exact food notes.  Do not change the master, taxonomy
# or the original food_safety status.  Kurohatu's '要注意' and 2021 caution
# must be visible even though its stored status remains 'unknown'.
NINTH_KUROHATU_WARNING_LABEL = "資料には食用を避けるよう注意があります"
NINTH_FOUR_FOOD_NOTE_REVIEWED = {
    "kurohatu": ("クロハツ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「要注意」。条件付き毒性記述／注意記述があるため食用判定へ変換せずunknownとした。 厚労科研2021研究分担報告書の表4注2は、以前の「食用にできるが生食は毒」という扱いと区別し、現在は食用にすべきでないとする注意を記載する。加熱による安全性は保証しない。毒成分は追加推定しない。", "石川県の資料では、食毒欄に「要注意」と記載されています。また、2021年の厚生労働科学研究の報告書には、以前は「食用にできるが生食は毒」とされていたものの、現在は食用にすべきでないと記載されています。加熱すれば安全という意味ではありません。"),
    "kotubutake": ("コツブタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。", "石川県の資料では、食毒欄に「不食」と記載されています。これは「毒」と同じ意味ではなく、この記載だけで毒性が確認されたとは判断できません。"),
    "cyanamemututake": ("チャナメツムタケ", NEXT_FOUR_SOURCE_NOTE, NEXT_FOUR_DISPLAY_NOTE),
    "tutiguri": ("ツチグリ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「不食」。", "石川県の資料では、食毒欄に「不食」と記載されています。これは「毒」と同じ意味ではなく、この記載だけで毒性が確認されたとは判断できません。"),
}

# Tenth (final exact-name) group: conservative warnings for two new links.
# Keep the source master unchanged and apply only when ID/name/full note match.
TENTH_NARATAKE_CAUTION_LABEL = "資料に食用記載と注意情報があります"
TENTH_MANNENTAKE_USE_LABEL = "資料には薬用・鑑賞との記載があります"
TENTH_TWO_FOOD_NOTE_REVIEWED = {
    "naratake": ("ナラタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「食」。公的資料に食用記述があるという記録であり安全保証ではない。 茨城県はナラタケ類の摂食後事例と、ナラタケ・ナラタケモドキの多量摂取による消化不良への注意を記載する。原因種が確定した毒性試験と同一視せず、食用記録に注意を併記する。", "石川県の資料では、食毒欄に「食」と記載されています。一方、茨城県の資料では、ナラタケやナラタケモドキについて、食べ過ぎると消化不良を起こしやすいと注意しています。食用との記載があっても、採取したキノコの種類や安全性を判断することはできません。"),
    "mannentake": ("マンネンタケ", "食用可否の自己判断には使用しない。毒性の記録がないことは安全を意味しない。 石川県の食毒欄は「薬用、鑑賞」。", "石川県の資料では、食毒欄に「薬用、鑑賞」と記載されています。これは資料に記された利用区分であり、薬としての効果や、採取したキノコの安全性を示すものではありません。"),
}


def reader_facing_food_note(note):
    """Show source-specific facts; the detail panel renders the safety warning separately."""
    note = _present(note)
    if note is None:
        return None
    if note in FOOD_NOTE_SENTENCES:
        return FOOD_NOTE_SENTENCES[note]
    # These two stock cautions are already displayed in the full warning below.
    # Strip only these exact sentences, keeping all species-specific caveats.
    for stock_sentence in (
        "食用可否の自己判断には使用しない。",
        "毒性の記録がないことは安全を意味しない。",
    ):
        note = note.replace(stock_sentence, "")
    note = " ".join(note.split())
    if not note:
        return None
    for internal, reader_facing in FOOD_NOTE_REPLACEMENTS:
        note = note.replace(internal, reader_facing)
    return note


def _present(value):
    return value if isinstance(value, str) and value.strip() else None


def _source_ids(field):
    if not isinstance(field, dict):
        return []
    values = field.get("source_ids")
    return [value for value in values if isinstance(value, str)] if isinstance(values, list) else []


def _identity(article):
    for key in ("article_id", "article_path", "url"):
        value = article.get(key)
        if value is not None and str(value).strip():
            return key, str(value)
    return None


def _published_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).timestamp()
    except (ValueError, OverflowError):
        return None


def _articles_for(gallery_name, observations):
    articles = {}
    for observation in observations:
        if observation.get("gallery_name") != gallery_name:
            continue
        article = observation.get("article")
        if not isinstance(article, dict):
            continue
        identity = _identity(article)
        if identity is None or identity in articles:
            continue
        articles[identity] = {
            "title": article.get("title"), "url": article.get("url"),
            "published": article.get("published"), "_identity": identity,
        }

    def key(article):
        timestamp = _published_timestamp(article.get("published"))
        return ((0, -timestamp) if timestamp is not None else (1, 0), article["_identity"])

    result = sorted(articles.values(), key=key)
    for article in result:
        article.pop("_identity")
    return result


TAXONOMY_DISPLAY_PATH = Path(__file__).resolve().parent / "data" / "taxonomy-display-ja.json"
JAPANESE_TEXT = re.compile(r"[ぁ-んァ-ヺ一-龯]")
DISPLAY_GUIDE_ROWS = (
    ("特徴", "features"), ("生育環境", "habitat"), ("資料に記載された発生時期", "season"),
)


def _load_taxonomy_display(path):
    if path is None:
        return {}, {}
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec["version"] == 1 and all(isinstance(spec[key], dict) for key in ("entries", "sources")):
            return spec["entries"], spec["sources"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {}, {}


def _taxonomy_display_fields(master, entry, sources):
    taxonomy = master.get("taxonomy") or {}
    identity = {
        "name": master.get("canonical_name_ja"),
        "scientific": (master.get("scientific_name") or {}).get("value"),
        **{rank: (taxonomy.get(rank) or {}).get("value") for rank in ("family", "genus")},
    }
    if not isinstance(entry, dict) or entry.get("expected") != identity:
        return {}
    fields = entry.get("fields")
    if not isinstance(fields, dict):
        return {}
    usable = {}
    for rank in ("family", "genus", "ecology", "name_reference", "food_reference",
                 *(key for _, key in DISPLAY_GUIDE_ROWS)):
        item = fields.get(rank)
        if not isinstance(item, dict):
            continue
        value = _present(item.get("value"))
        linked = item.get("sources")
        if (value and JAPANESE_TEXT.search(value) and isinstance(linked, list) and linked
                and all(isinstance(ref, str) and isinstance(sources.get(ref), dict)
                        and str(sources[ref].get("url", "")).startswith("https://") for ref in linked)):
            usable[rank] = item
    return usable


def _knowledge(master, source_map, *, display_entry=None, display_sources=None):
    rows = []
    used_ids = []

    def add(label, value, field, *, note=None):
        value = _present(value)
        if value is None:
            return
        rows.append({"label": label, "value": value, "note": note})
        used_ids.extend(_source_ids(field))

    scientific = master.get("scientific_name") or {}
    add("学名", scientific.get("value"), scientific,
        note="出典資料に記載された学名" if scientific.get("name_status") == "source_reported" else None)
    taxonomy = master.get("taxonomy") or {}
    family, genus = taxonomy.get("family") or {}, taxonomy.get("genus") or {}
    display_sources = display_sources or {}
    display_fields = _taxonomy_display_fields(master, display_entry, display_sources)
    display_refs = []

    def add_display(label, choice, original):
        note = " ".join(text for text in (choice.get("latin"), choice.get("note"))
                        if isinstance(text, str) and text.strip())
        add(label, choice["value"], original, note=note or None)
        display_refs.extend(choice["sources"])

    if "name_reference" in display_fields:
        add_display("学名の資料比較", display_fields["name_reference"], {})
    for label, rank, original in (("科名", "family", family), ("属名", "genus", genus),
                                   ("生態", "ecology", {})):
        chosen = display_fields.get(rank)
        raw = _present(original.get("value"))
        if chosen:
            add_display(label, chosen, original)
        elif rank == "ecology":
            add(label, "未確認", original)
        elif raw and JAPANESE_TEXT.search(raw):
            add(label, raw, original, note="出典資料の表記")
        else:
            add(label, "確認中", original, note=f"資料に記載された名称：{raw}" if raw else None)
    for label, key in DISPLAY_GUIDE_ROWS:
        field = master.get(key) or {}
        summary = field.get("summary")
        if _present(summary) is None and key in display_fields:
            add_display(label, display_fields[key], field)
        else:
            add(label, summary, field)
    food = master.get("food_safety") or {}
    status = food.get("status")
    if status in FOOD_SAFETY_LABELS:
        add("食毒情報", FOOD_SAFETY_LABELS[status], food)
        if (master.get("mushroom_id") == "kiraratake"
                and master.get("canonical_name_ja") == "キララタケ"
                and status == "edibility_reported"):
            # Keep the original status and source record, but avoid a misleading
            # food-friendly headline when public sources conflict.
            rows[-1]["value"] = KIRARATAKE_CONFLICT_LABEL
        name_and_note = (master.get("canonical_name_ja"), food.get("notes"))
        approved_note = {
            ("ヤマドリタケモドキ", YAMADORITAKEMODOKI_SOURCE_NOTE): YAMADORITAKEMODOKI_DISPLAY_NOTE,
            ("シイタケ", SHIITAKE_SOURCE_NOTE): SHIITAKE_DISPLAY_NOTE,
        }.get(name_and_note)
        reviewed = (FOOD_NOTE_REVIEWED.get(master.get("mushroom_id"))
                    or NEXT_FOUR_FOOD_NOTE_REVIEWED.get(master.get("mushroom_id"))
                    or THIRD_FOUR_FOOD_NOTE_CANDIDATES.get(master.get("mushroom_id"))
                    or FOURTH_FOUR_FOOD_NOTE_REVIEWED.get(master.get("mushroom_id"))
                    or FIFTH_FOUR_FOOD_NOTE_REVIEWED.get(master.get("mushroom_id"))
                    or SIXTH_FOUR_FOOD_NOTE_REVIEWED.get(master.get("mushroom_id"))
                    or SEVENTH_FOUR_FOOD_NOTE_REVIEWED.get(master.get("mushroom_id"))
                    or EIGHTH_FOUR_FOOD_NOTE_REVIEWED.get(master.get("mushroom_id"))
                    or NINTH_FOUR_FOOD_NOTE_REVIEWED.get(master.get("mushroom_id"))
                    or TENTH_TWO_FOOD_NOTE_REVIEWED.get(master.get("mushroom_id")))
        if (master.get("mushroom_id") == "anzutake" and
                master.get("canonical_name_ja") == "アンズタケ" and
                status == "edibility_reported" and reviewed is not None and
                reviewed[:2] == (master.get("canonical_name_ja"), food.get("notes"))):
            # The source retains '食', but another public source says '注意'.
            rows[-1]["value"] = EIGHTH_ANZUTAKE_WARNING_LABEL
        if (master.get("mushroom_id") == "kurohatu" and
                master.get("canonical_name_ja") == "クロハツ" and
                status == "unknown" and reviewed is not None and
                reviewed[:2] == (master.get("canonical_name_ja"), food.get("notes"))):
            # Explicit caution is more informative than a generic unknown
            # status; never recategorize the underlying master record.
            rows[-1]["value"] = NINTH_KUROHATU_WARNING_LABEL
        if (reviewed is not None and
                reviewed[:2] == (master.get("canonical_name_ja"), food.get("notes"))):
            if (master.get("mushroom_id") == "naratake"
                    and status == "edibility_reported"):
                rows[-1]["value"] = TENTH_NARATAKE_CAUTION_LABEL
            elif (master.get("mushroom_id") == "mannentake"
                    and status == "unknown"):
                rows[-1]["value"] = TENTH_MANNENTAKE_USE_LABEL
        if (reviewed is not None and
                reviewed[:2] == (master.get("canonical_name_ja"), food.get("notes"))):
            # None means this source contained only the repeated generic warning.
            notes = reviewed[2]
        else:
            # Unreviewed or changed source notes retain their old safe renderer.
            notes = approved_note if approved_note is not None else reader_facing_food_note(food.get("notes"))
        if notes:
            rows[-1]["note"] = notes
        food_reference = display_fields.get("food_reference")
        if (food_reference and food_reference.get("expected_status") == status
                and "expected_notes" in food_reference and food_reference["expected_notes"] == food.get("notes")):
            add_display("食毒資料の補足", food_reference, {})
    toxin_names = []
    for toxin in master.get("toxins") or []:
        if not isinstance(toxin, dict) or not _present(toxin.get("name")):
            continue
        toxin_names.append(toxin["name"])
        used_ids.extend(_source_ids(toxin))
    if toxin_names:
        rows.append({"label": "資料に記載された成分", "value": "、".join(toxin_names), "note": None})

    sources = []
    for source_id in dict.fromkeys(used_ids):
        source = source_map.get(source_id)
        if isinstance(source, dict):
            sources.append({key: source.get(key) for key in ("source_id", "organization", "title", "url")})
    existing_urls = {source["url"] for source in sources}
    for key in dict.fromkeys(display_refs):
        source = display_sources[key]
        if source["url"] not in existing_urls:
            sources.append({**source, "source_id": f"taxonomy-display-{key}"})
            existing_urls.add(source["url"])
    return {"rows": rows, "sources": sources}


def build_detail_views(portal_data, *, taxonomy_display_path=TAXONOMY_DISPLAY_PATH):
    """Build detail models using only explicit links in portal schema v1."""
    if not isinstance(portal_data, dict) or portal_data.get("version") != 1:
        raise ValueError("detail UI requires portal-data schema version 1")
    reference = portal_data.get("reference_data") or {}
    master_root = reference.get("mushroom_master") or {}
    source_root = reference.get("sources") or {}
    masters = {row.get("mushroom_id"): row for row in master_root.get("entries", [])
               if isinstance(row, dict) and _present(row.get("mushroom_id"))}
    source_map = {row.get("source_id"): row for row in source_root.get("sources", [])
                  if isinstance(row, dict) and _present(row.get("source_id"))}
    display_entries, display_sources = _load_taxonomy_display(taxonomy_display_path)
    observations = portal_data.get("observations") or []
    views = {}
    for subject in portal_data.get("subjects") or []:
        if not isinstance(subject, dict) or not _present(subject.get("gallery_name")):
            continue
        name = subject["gallery_name"]
        master = masters.get(subject.get("mushroom_master_id"))
        classification_counts = subject.get("classification_counts")
        taxonomy = subject.get("taxonomy")
        review_pending = isinstance(classification_counts, dict) and any(
            classification_counts.get(key, 0) >= 1
            for key in ("confirmed_mushroom_identity_uncertain", "manual_review_name_conflict", "legacy_review")
            if isinstance(classification_counts.get(key, 0), (int, float))
        )
        taxonomy_pending = (
            isinstance(taxonomy, dict)
            and taxonomy.get("subject_type") == "mushroom"
            and subject.get("mushroom_master_id") is None
        )
        views[name] = {
            "gallery_name": name,
            # Presentation metadata from the same explicit ID join as food labels.
            "food_safety_status": (master.get("food_safety") or {}).get("status") if master else None,
            "knowledge": _knowledge(
                master, source_map, display_entry=display_entries.get(master.get("mushroom_id")),
                display_sources=display_sources,
            ) if master is not None else None,
            "knowledge_pending": master is None and (review_pending or taxonomy_pending),
            "articles": _articles_for(name, observations),
        }
    return views


def _format_published(value):
    timestamp = _published_timestamp(value)
    if timestamp is None:
        return "記事公開日：不明"
    date = datetime.fromtimestamp(timestamp, timezone.utc)
    return f"記事公開日：{date.year}年{date.month}月{date.day}日"


def _render_article(article):
    date = html.escape(_format_published(article.get("published")))
    title = html.escape(str(article.get("title") or "無題"))
    url = _present(article.get("url"))
    title_html = f'<a href="{html.escape(url, quote=True)}" target="_top">{title}</a>' if url else title
    return (f'<li class="subject-record-item"><time class="subject-record-date">{date}</time>'
            f'<div class="subject-record-title">{title_html}</div></li>')


def render_detail_sections(view):
    """Render optional knowledge and reverse-link sections for one subject."""
    if not isinstance(view, dict):
        return ""
    parts = []
    knowledge = view.get("knowledge")
    if isinstance(knowledge, dict):
        rows = []
        for row in knowledge.get("rows", []):
            label = html.escape(str(row["label"])); value = html.escape(str(row["value"]))
            note = row.get("note")
            note_html = f'<div class="knowledge-note">{html.escape(str(note))}</div>' if note else ""
            rows.append(f'<div class="knowledge-row"><dt class="knowledge-label">{label}</dt>'
                        f'<dd class="knowledge-value">{value}{note_html}</dd></div>')
        sources = []
        for source in knowledge.get("sources", []):
            organization = html.escape(str(source.get("organization") or ""))
            title = html.escape(str(source.get("title") or "出典"))
            text = f"{organization}：{title}" if organization else title
            url = _present(source.get("url"))
            sources.append(f'<li><a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{text}</a></li>'
                           if url else f"<li>{text}</li>")
        source_html = (f'<details class="knowledge-sources"><summary>出典を見る（{len(sources)}件）</summary>'
                       f'<ul>{"".join(sources)}</ul></details>') if sources else ""
        parts.append('<section class="knowledge-panel"><h2 class="knowledge-title">図鑑情報</h2>'
                     f'<dl class="knowledge-facts">{"".join(rows)}</dl>'
                     '<p class="knowledge-warning">食べられるかどうかについては、参考にした資料の情報を掲載しています。'
                     'このページの情報を、キノコを採ったり、調理したり、食べたりする判断には使わないでください。'
                     '毒性についての記載がなくても、安全とは限りません。</p>'
                     f'{source_html}</section>')
    elif view.get("knowledge_pending") is True:
        parts.append('<section class="knowledge-pending"><h2>図鑑情報は現在整理中です</h2>'
                     '<p>キノコの図鑑や研究資料などを参考に、情報を調べています。確認できた内容から順次追加していきます。</p></section>')
    articles = view.get("articles") or []
    if articles:
        items = [_render_article(article) for article in articles]
        visible = "".join(items[:5])
        older = items[5:]
        more = (f'<details class="subject-record-more"><summary>過去の観察記録をさらに見る（{len(older)}件）</summary>'
                f'<ul class="subject-record-list">{"".join(older)}</ul></details>') if older else ""
        parts.append('<section class="subject-records"><h2>📔 このキノコが登場した観察記録</h2>'
                     f'<ul class="subject-record-list">{visible}</ul>{more}</section>')
    return "".join(parts)


def poison_spore_attribute(view):
    """Opt in only for the existing, explicitly linked poisonous status."""
    if (view or {}).get("food_safety_status") == "poisonous_confirmed":
        return ' data-food-safety="poisonous_confirmed"'
    return ""

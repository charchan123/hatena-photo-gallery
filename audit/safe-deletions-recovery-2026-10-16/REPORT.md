# 安全な写真削除の復旧実装・検証

Draft PR: https://github.com/charchan123/hatena-photo-gallery/pull/114

PR #113保存headを継承し、旧Workの未保存実装を救出して不足を修正した。
**実装のレビュー用PRであり、本番再開・実データ承認・公開の記録ではない。**

## 恒久運用の構成

- strict API全ページ取得、旧公開commitとsealの照合、Atom ID/厳密URLhash/ordinalで対象を識別する。
- 同じsnapshot/fingerprint/参照集合で別Actions runの完全取得2回、6〜72時間の間隔を要求。同じrunの再試行は独立確認と数えない。取得異常/再登場/文脈変化で再確認する。
- 通常削除だけを自動対象とし、全DOM画像の3%かつ20枚以下、記事5%かつ2件以下に限定（小規模fixture下限1）。URL置換/共有/順序・ラベル変更/下書き化は人間の通常削除承認でも解除しない。
- Best Shot/年間Best、全open PRの未公開Best Shot、研究/同定、名前変更/手動採用receipt、curatedなID/URL参照を保護する。参照取得不能は停止する。
- 判定前に専用Git branch `sync-deletion-audit` へappend-only eventを非force保存し、remote headの一致を確認する。競合/保存失敗は公開を止める。
- guardが承認した厳密な対象だけを旧比較集合から除外し、既存ID/分類/研究/選定validatorを通す。全ページを一時出力で検証し、失敗時は前の出力を維持する。
- receiptとhistory anchorをsnapshotへ保持。元の自動追加receiptも退役ledgerに保持し、再出現や履歴改変を止める。旧7枚退役manifest/receiptは維持する。
- 管理室に写真単位の保留、代替案、明示承認、研究写真だけの削除承認、ケースのアーカイブ/退役を実装。ID再入力・理由・最新照合・差分プレビュー・隔離実生成を経る。正の承認はmainへレビュー済みmanifestが入った後だけ有効。実対象のmanifestは今回作っていない。
- 公開停止中も日次buildは再巡回する。さらに独立read-only監査を毎日01:30 UTC（10:30 JST、GitHub遅延あり）に追加し、履歴保存・生成初期化の失敗からも独立して取得を試みる。監査は運用上の確認回数を増やさず、hash履歴を書かず、公開しない。
- 監査artifactと件数のみのActions summaryを毎回保存する。定期監査で保留/異常があればActionsを失敗にして既存のActions通知設定へつなぐ。メール等の実到達はアカウント設定依存で未確認。

## 今回追加で修正した欠損

1. アーカイブ承認がマージ済み・公開待ちの状態でも元の同定履歴を参照保護へ戻して再レビュー可能にした。
2. その判断を保留へ差し替えた場合、同定registryを復元し、旧承認/ケース/履歴capsuleを削除せずsupersedesで保持する。
3. 同じ画像URLの全出現が複数記事から同時に消えた場合も、共有URLとして自動削除を拒否する。
4. 出力中の削除記事リンクとJSONエスケープされた退役画像URLも検出して停止する。
5. Chromium回帰を独立したread-only CIへ追加した。

## 最新APIと未承認対象

[認証付き読取り監査 38913573487](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38913573487)
で12ページ/112 entry/下書き1/公開111記事/全DOM980画像を取得。
旧公開は110記事/図鑑906写真。削除1記事/16画像、追加2記事/20画像、図鑑893候補（新規3・その他17）。
保存CSVと16枚すべての観察ID/Atom記事hash/画像URLhashが一致した。詳細は `live-check-38913573487.json`。

| 対象 | 状態 |
|---|---|
| 通常写真14枚 | 独立した運用確認が不足。削除済み・人間承認済みとは扱わない |
| カワリハツ？ `research-940496f1ccdb136f` | 1/1枚欠落。ケース消滅を自動承認しない |
| Lanmaoa？ `research-f9cb62e956fa8604` | 1/6枚欠落。残5枚と同定履歴を継続して保護 |

実adapterは `DELETION_CONFIRMATION_OR_APPROVAL_PENDING` で停止。
公開/出力置換/確認履歴書込みなしをActionsで検証した。
後続の同じ実装head `7f174c52...` の[読取り監査 38914042493](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38914042493)も成功。
読み取り専用PR監査を独立2回の運用証拠に流用していない。

## 検証の区別

- 実ジェネレーター + strict Atom fixture: 初回の安全停止→7時間後の別runで通常写真1枚退役と新規1枚追加→翌日同じreceipt/IDを保持、を検証した。旧7枚のvalidatorも通す。
- bare Git fixture: append-only保存、巻戻し/改変検出、競合時の非force push失敗と履歴残存を検証した。
- Chromium: 削除承認29項目、Best Shot92項目。PC/キーボード/IME相当/タッチ相当。日本語フォントを用意して画面も確認。
- 既存全JavaScript試験/構文、Python compile、production validatorと保護値を検証。141種/419出典/373特徴/overlay0。mainのdata、旧7枚manifest、既存移行/同定validatorのバイト一致。
- 最新API: GitHub Secretsを既存Actions内で使用するGETのみ。ローカルへ秘密を持ち出していない。
- 本番の監査履歴branch作成・独立確認2回・実写真の削除適用・Safari/Firefox/実機タッチ・通知の実到達は未実施。

最終Python件数/CI結果は `VALIDATION.json` に記録する。

## 公開前に必要な人間の判断

mainへ直接pushせず、このDraftで停止する。
#113と#114を両方マージする必要はなく、#114が#113の保存headを含む後継である。
#111/#112は独立したDraftのまま維持し、無断変更していない。
後継のレビュー後も、運用履歴の独立取得2回と保護研究写真2件の明示判断が揃うまで公開は止まる。
一括承認や安全ゲートの解除によって再開しない。

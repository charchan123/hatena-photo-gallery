# 記事・写真の同期管理（Phase 2）

PR #106の仕様修正：**通常の自動同期はPhase 1と同じ条件で進みます。**
管理室の「確認済み」はローカルの確認履歴であり、公開許可ではありません。

初版で追加した人間承認必須ゲートは撤去しました。`sync-reviews/approvals.json` と
追加写真の承認PR経路も削除しています。承認済み7枚のretirementは別の固定台帳で、変更していません。

## 日次運用

|ケース|公開候補と停止条件|
|---|---|
|既存記事の更新|従来のAPI・全ページ・Phase 3C・ID/名前/URL・参照検証を通れば承認なしで反映|
|高信頼の新規写真|`SAFE_NEW`、`accepted_subject`、confidence=`high`と従来の照合条件を満たせば、1枚でも複数でも自動追加|
|未分類・曖昧な新規写真|勝手な名前を付けず自動採用しない。従来Phase 3Cが生成対象外とする写真はinventoryに残す。新規gallery候補が分類ゲートに抵触する場合はfail-closed|
|既存写真の削除・名前・URL変更|従来どおりBLOCKED。確認済み・保留などの操作でも解除しない|

追加の隔離機能は実装していません。単にportalから除いても別のHTMLに残る可能性があり、
production entries・全出力・重複対応・既存参照との整合性を独立して証明する必要があるためです。
Phase 1の除外判定を新設の隔離や「キノコ以外」への推測変更で置き換えていません。

## 管理画面

- 127.0.0.1専用、Origin・CSRF・任意path/URL入力の拒否を維持。
- 最新Actionsと最後の正常公開を別表示。UNKNOWN・未取得・0件を区別。
- 552件の過去の保留を新規問題552件とは表示しません。
- 名前・記事・日付・分類状態検索、カテゴリfilter、30件paging、写真・記事プレビューを維持。
- 状態：自動追加済み／確認待ち（新規・以前から）／要対応／保留／確認済み。
- **自動追加候補には承認ボタンを要求しません。** 公開済みと候補を区別します。
- 「確認済み」「現状維持」「保留」「判断取消」はローカル監査だけ。
  確認済みでも既存写真変更の要対応は未解決として残ります。保留でも高信頼写真の自動追加を止めません。
- 名前修正提案は人間の入力として保留保存。未分類の強制採用、既存写真の削除・URL置換の適用は未対応。
  これらは個別移行が必要です。権限のない承認PRボタンは置きません。
- 既存のBest Shot、研究室、更新告知、情報拡充とそのPR経路は変更しません。

## 自動追加の読み取り証跡

- 通常の`reconcile_ids`とretirement検証に成功した新しいIDだけを記録。
- `article-sync-status.json`に直近の自動追加写真数・正常生成日時を追加。
- `article-sync-snapshot.json`のoptional `automatic_additions`へ履歴を保持。
- 各履歴は公開済みobservation ID、記事ID hash、URL hash、article内重複番号、
  追加時の分類status/reason、日時。生の画像URL、記事本文、認証情報は記録しません。
- 追加ゼロの日にも過去の履歴を維持。管理室で件数・日時・追加時の根拠を表示。
- 旧906枚を「今回の自動追加」と推測して登録しません。旧snapshotに履歴がなければ未記録です。
- receiptはIDとURL hash、重複番号、日時、schemaを検証。これは承認データではなく、
  削除・名前変更・URL置換などを許可しません。履歴破損はsnapshot破損としてfail-closed。
- 公開candidate生成後でもdeployされるまでは管理室の「自動追加済み」に表示しません。
  管理室は単一の公開gh-pages commitのsnapshotだけを比較元にします。

## ローカル操作・鮮度

- ローカル状態はignored `admin/local-state/sync/review.json`。atomic replaceとsymlink拒否を維持。
- candidate IDはAtom記事ID hash＋画像URL hash＋記事内重複番号。
  `article_N.html`や全DOM位置を識別に使いません。
- snapshot、inventory、分類根拠fingerprintが変わった過去の判断は失効します。
- 旧仕様の「採用」記録には公開権限がありません。新しい採用操作は拒否します。
- API取得失敗でも最後の公開成功状態を表示。失敗したliveレビューは無効化。
- 実生成プレビューは認証済みGET、鮮度再検査、同じ`article_sync.run()`と全保護ゲートを利用。
  管理室から公開・deploy・mergeは行いません。

## Windows使用手順

1. Git、Python 3.10以降、Node.jsを準備し、`python -m pip install -r requirements-dev.txt`。
2. 作業checkoutを更新し、`git fetch origin main gh-pages`。
3. `admin\start_admin.bat`または`python -m admin.server`。
4. `http://127.0.0.1:8765/`の「記事・写真の同期管理」。公開状態の閲覧と確認履歴にははてなAPIキー不要。
5. 未公開の同期候補も確認する場合だけ、サーバーを起動するローカル環境へ
   `HATENA_USER`、`HATENA_BLOG_ID`、`HATENA_API_KEY`を安全に設定して再起動。
   キーをブラウザー、レビューコメント、Git、ログへ入力/保存しません。
6. 最新Actionsの取得はGitHub CLIの`gh auth login`が必要。
   取得できないときは未取得と表示し、通常の毎日同期に影響しません。

## 検証

- `tests/test_sync_automatic_updates.py`はHTTP/EXIF transport以外を実関数で実行。
  記事更新、1枚追加、2枚追加、次回のID維持、承認ファイル不要、HTML/JSON生成を確認。
- 同じ実生成で曖昧な新規gallery候補、既存URL・名前変更・削除はBLOCKED、旧出力byte保持。
- 追加の確認・保留・取消は生成結果に適用されず、安全ゲートを変更しません。
- 退役復活拒否、全旧ID・名前・URL、Best Shot・研究室参照、全既存回帰を検証。
- 詳細結果は `docs/sync-review/test-validation.json`、
  `public-protection.json`、`browser-validation.json`、実API検証記録を参照。

管理室自体の例外移行適用は引き続きPARTIALです。今回は通常の自動更新を維持する仕様修正であり、
未分類の手動分類・既存写真変更の移行機能を完成したとは扱いません。
Hatena記事操作、main push、merge、deploy、workflow_dispatch、サイト公開は行いません。

## 実APIの読み取り専用事前検証

[Actions 38203721560](https://github.com/charchan123/hatena-photo-gallery/actions/runs/38203721560)
で同じproduction wrapperを2回実行し、ともにSUCCESS。
12ページ・公開110記事・976画像occurrences・906 gallery、下書き2記事除外。
旧906枚のID/名前/URL、Best Shot3件、研究室67ケースを保持。
retired7枚の出力検査PASS、Phase 3C PASS、322 HTML生成。2回目は新記事・新画像0。
実APIに新規写真はなかったため、1枚/複数枚追加はfixture実生成の証拠です。

PR106・同一repo pull_request限定、contents:read、Hatena GETのみ。
生成はRUNNER_TEMP、非公開本文・認証値・画像URLのログ/成果物出力なし。
一時workflowは検証後に削除し、最終PR差分に残しません。
実APIを取得したgeneratorのコードは最終修正と同一です。


## Phase 2c：図鑑未収録写真の個別採用

単一の公開DOM画像に限定した人間分類・採用・翌日の継続と専用Draft PRの手順は [ARTICLE_PHOTO_SYNC_MANUAL_ADOPTION.md](ARTICLE_PHOTO_SYNC_MANUAL_ADOPTION.md) を参照してください。通常の高信頼新規写真は承認不要のままです。既存の名前修正とは別の移行・台帳を使用します。

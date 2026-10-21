# Cloudflare隔離検証：着手前監査（2026-10-22 JST）

## 結論

**準備資料を作成。実環境構築・テストは未実施で、ログイン承認待ち。** 本番Pagesと公開コメント設定を変更せず、安全停止している。完了したのは現在状態の読み取り・導入調査・設定の不整合検出・後続設計・ローカル回帰だけ。

## 独立取得した基準

- main：`090eac16c25129695452a10a076532c752d8bd27`（PR #135マージ）
- main tree：`f86c9cacd26b3779045b771c454c1c480f03a15a`（#135最終実装と同じ）
- gh-pages：`35f2c8589553555890a82220e0c73304b017fd35`
- 公開写真933、Best Shot17、NEW!14、研究66、退役7。registry SHA：`240e897c1edfddcef4d658f774885373be254c704c7f03b7535ac4f606bb10c5`。
- 公開manifestの66 active IDとコードの対応表を照合し、一致。確認待ち0。
- [baseline.json](baseline.json)に公開portalのSHA-256、全data/sync-migrations、コード・管理室・生成workflowなど24保護ファイルのSHA-256と状態を記録した。新規資料以外は最新mainと同一。

CloudflareはWorkのクラウドブラウザで `https://dash.cloudflare.com/login` が表示された。未ログインなのでアカウント内の契約・既存リソースは不明。アカウントが存在しないとは推測しない。初回ブラウザ接続に時間がかかったが、サイトからbot blockが出たとは判断していない。認証情報を入力・取得・保存していない。

## 停止理由と具体的な修正案

1. 依頼第2節により、Cloudflareへのログインを含む外部操作は事前説明と明示承認が必要。ログイン、D1/Worker/Turnstile/Access作成、secret登録、remote migration、deployを実行していない。
2. 公開JSのcredentials=omitはAccess Cookieを送らない。検証UI/APIを同一originに置き、検証専用ビルドのみsame-originにする必要がある。
3. Workerのmanifest取得先は本番Pagesへ固定され、別staging URLは拒否される。完全隔離には凍結manifestの取得方針をstaging専用entryへ限定して用意し、本番制限を維持する必要がある。
4. localhost管理室の接続は管理Bearerのみ。Access service tokenは検証用のサーバー側transportにだけ追加し、Windows管理室を公開しない。

詳細・承認対象・無料プラン・認証・終了手順は[隔離構築計画](../../docs/research-comments-staging-plan.md)。コード修正は別Draft PRで行い、今回の資料PRに安全ゲートの緩和を含めない。

## 実施した検証

| 検証 | 今回の結果 | 環境 |
|---|---|---|
| 公開設定 | enabled=false、API/site key空、承認null | gh-pages読み取り |
| 66ケース | registry/公開manifest/生成モデル一致 | 読取専用ローカル |
| migration3本 | 適用成功、66 cases、FK違反0、registry SHA一致 | メモリ内SQLite |
| 既存研究コメントPython | 9 PASS | Work内隔離Python |
| 既存Worker/API/復元 | 13 PASS | 合成本文・一時SQLite・通信モック |
| 実Workers/D1/Turnstile | **全てNOT RUN** | 未作成・未接続 |
| Android実機の検証画面 | **NOT RUN** | 検証URL未作成 |

[17項目の試験表](test-matrix.json)は全項目NOT_RUN_AWAITING_APPROVAL。ローカル合格やPR #135の過去CIを実Cloudflareの合格として計上しない。基盤障害と、検証entryでの制御故障・通信モックも区別する。

今回の差分はdocs2本とaudit3ファイルのみ。アプリ・SQL・workflow・公開設定・実データの変更はない。最終コミット、Draft PR URL、最終HEADに紐づく各CIのURLと結果はDraft PR本文で追跡する。

## 後続要件A〜C

[正式な要件候補](../../docs/research-comments-roadmap.md)に、LINE/Web Push比較と推奨、スマホ管理者認証・深いリンク・セッション・誤送信防止、予約語（公開/管理人/ふすべまる）と匿名名前所有権、調査時系列と根拠・既存Git同定台帳との整合を整理した。優先順位、DB候補、費用・運用・紛失/似た文字/端末移行の制約も記載。全て今回未実装。

## 終了時点の状態・残る承認

- Cloudflare作成リソース0、secret登録0、remote migration0、Worker deploy0、契約/課金変更0。
- 本番Pages、公開コメント受付、写真・同定・通知・既存下書きは変更していない。
- stagingはまだ存在を確認できておらず、こちらから作成していない。staging flagsを切り替えた実績もない。「閉鎖確認済みの実stagingがある」とは報告しない。
- 最初に必要なのはCloudflareログインと既存アカウント/Free/リソース読み取りの承認。その後、具体的アカウントと専用リソース名・権限を確認して構築承認を求める。
- Zero Trust Free初期設定でも支払情報が必要となる場合があり、その段階は別判断。支払情報・規約同意・有料変更を自動で進めない。
- Androidで承認・secure sign-in・実Turnstile/画面確認が可能。WorkがAPI/DB/ブラウザとlocalhost管理室を検証する。実Windowsの既存下書きバックアップ・安全更新・端末固有確認は後日別作業。

Draft・未マージで保存し、外部環境の変更承認前に停止する。

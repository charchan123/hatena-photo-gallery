# 研究室コメントのLINE通知

Draftの追加機能。既定はLINE_ENABLED=false、月間上限0通。PR #137のコメント公開と独立して導入する。外部アカウント作成、外部接続、鍵登録、D1へのSQL適用、課金、公開設定変更は個別承認後に実施する。

## 確定投稿と再送

comments/line/0001_outbox.sqlを承認されたDBに適用すると、新規の一般公開コメントをコメントと同じトランザクションでoutboxに記録する。公式返信、再送receipt、過去の投稿を新しく通知しない。投稿直後のwaitUntilと5分ごとのscheduled処理が送信し、LINEの失敗は投稿結果へ伝播しない。無効設定・未導入DBでは送信を停止する。

comment_idを最初の送信からX-Line-Retry-Keyに使い、宛先hash・本文を固定する。leaseで同時送信を防ぎ、月間枠をD1 batchで一度だけ予約する。200と受理済みIDを伴う409を記録し、結果が不明な要求は同じ本文・宛先・キーで再試行する。23時間経過、月境界、宛先変更では自動再送を停止する。停止行の手動再投入には受理状況の確認が必要となる。API受理後でもブロックなどにより端末へ届かない場合がある。[LINE公式の再試行仕様](https://developers.line.biz/en/docs/messaging-api/retrying-api-request/)

送信時に公開状態を再確認する。非表示は保留し、本人削除は待機本文を消す。LINEが既に受理した通知を後から取り消すことはできない。outboxはIDと状態を保存し、初回送信の本文は成功・恒久停止・本人削除時に消す。本文・宛先・認証情報をconsoleへ出さない。

## メッセージと管理室

対象ケース名、投稿者、120文字までの概要、恒久ケースのコメント欄へのHTTPSリンクを1メッセージで送る。リンク先の該当欄を開く。PC管理室では同じケースIDを検索する。

現在の管理室はPCのlocalhostで動作する。スマホから開ける管理URLを提供するには、別途認証付きHTTPS管理画面の設計と承認が必要となる。この実装の通知は、PCのローカル管理室で操作する旨を記載する。

## 費用と設定

LINE公式アカウントのコミュニケーションプランは月額0円・200通までで、追加送信に対応しない。本実装はLINE_MONTHLY_LIMITを1〜200通に制限し、LINEの残量APIとアプリ内の原子的な予約数の両方を確認する。他の配信も同じアカウント枠を使うため、その利用量も含めて停止する。結果不明の通知も枠を消費したものとして予約を保持する。上限変更・有料プランへの変更は別承認とする。[LINE公式料金](https://www.lycbiz.com/jp/service/line-official-account/plan/)

承認後に設定する項目は次のとおり。

- Worker secretにLINE_CHANNEL_ACCESS_TOKENとLINE_RECIPIENT_IDを保存する。Git、管理室ブラウザ、チャット、ログへ書かない。
- LINE_START_ATは接続承認時のISO 8601時刻にする。その時刻以前の投稿へ遡って通知しない。
- LINE_MONTHLY_LIMITを承認された上限に設定し、受信試験後にLINE_ENABLED=trueにする。コメント側の公開・受付承認とREAD/WRITEも必要となる。
- 追加SQLは通常の初期migration群と分けている。既存DB・installation ID・バックアップを確認後に適用する。初回seedの再適用を避ける。
- コメントのJSONバックアップは通知ledgerを含まない。DB全体の復旧時はLINEを停止し、outbox・line_budgetを保全して月内予約を照合する。復旧済みDBの過去投稿を再投入しない。

## スマホなしで進める範囲

キュー、二重通知防止、通信失敗、月間上限、リンク表示、同時実行は合成DBと偽LINE応答で検証する。

本人操作が必要な最終工程は、承認後のLINE公式アカウントの友だち追加、送信先の確認、テスト通知1件の受信確認となる。受信先はLINE表示名や検索用IDから推測せず、署名検証されたWebhookなどで本人のuserIdを取得する。公開Webhookを追加する場合はその外部接続を承認後に実装する。Webhookを使わず、本人が当該providerの開発者として自身のuserIdを安全に取得できる場合もある。[userIdの公式取得方法](https://developers.line.biz/en/docs/messaging-api/getting-user-ids/)

## 切り戻し

LINE_ENABLED=falseで送信を停止する。コメントの投稿・閲覧は独立して継続できる。不要なLINE資格情報の失効は承認後に実施する。未送信・結果不明のledgerを保持して二重送信を防ぐ。

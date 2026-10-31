# 通常記事・読者機能・集客の保護範囲

2026-10-24 JST。CSS/フッター候補だけで「読者通知が届いた」「SEO順位不変」とは報告しません。

| 項目 | 保護方法・今回確認できること | 残る実確認 |
|---|---|---|
| 読者登録・購読リスト | はてなブログ自体・ブログID・読者リンク・サイドバーを保持 | ログイン利用者の表示。登録/解除操作はしない |
| 通常記事の更新通知 | 投稿API/日時/公開範囲/記事URLを変更しない | 次の正規の記事公開後の購読リスト/メール。テスト投稿しない |
| RSS・Atom | 公開/feedと/rssをGET、現行XMLと宣言URLを記録。記事の配信ははてなを維持 | 公開後のHTTP/内容と次の正規記事の追加 |
| ブロググループ | 参加設定・公開範囲・通常投稿は変更しない | 実際の参加状態と次の記事掲載。固定ページ更新を新着投稿の代用にしない |
| はてなスター | native container/記事permalinkを保持。GitHub Pagesの公式連携JS無変更 | 認証済み表示・件数。実追加/削除は禁止 |
| ブックマーク | nativeリンク/元記事URLを保持 | 表示と既存件数。送信しない |
| 既存コメント | 記事を削除/再投稿せず、DOM・コメントUIを保持 | 認証済みUI、既存の全履歴。投稿しない |
| 記事・カテゴリーURL | hrefを同一DOMの前後で照合、root以外を起動対象外 | 公開後のリンク巡回 |
| 検索エンジン | native記事一覧・見出し・リンクとcanonicalを保持。JS無効でも旧記事表示 | 順位やiframeのindex帰属は保証不可。Search Consoleで後日監視 |
| トップmeta | rootのtitle/canonical/OGPを変更しない。/new-topも現行の自己canonicalを保持 | 公開直後のソース、SNSプレビューcache。重複ページの順位影響は未確定 |
| 最新・過去記事 | 既存一覧/ページャ/探索日記を維持、root上に/archiveへの常設リンク | 戻る/進む、ページ送り、実Android |
| 検索・月別アーカイブ | sidebar/form/action/リンクを保持。rootでもsidebarを隠さない | 読取検索と月別一覧の実遷移 |

公式根拠：
- https://help.hatenablog.com/entry/reading/subscribe ：読者/購読リスト/1日1回メール。過去・未来日時など通知条件もある。
- https://help.hatenablog.com/entry/pages ：固定ページはトップや通常新着一覧・RSS/Atomで配信されない。
- https://help.hatenablog.com/entry/blog-group ：参加ブログの最新更新の掲載。複数グループの制限や公開条件は現在の参加設定も確認する。
- https://help.hatenablog.com/entry/config/detail ：ブログ情報/検索/フィード等の設定。
- https://help.hatenablog.com/entry/design/design-css ：広告やシステム部品の非表示に関する注意。

はてな記事本文、ID/URL、配信設定、コメント・スター・ブックマークの保存先は変更しません。外部部品を除外したローカル再現の成功と、認証済み本番サービスの完全な動作試験は別です。

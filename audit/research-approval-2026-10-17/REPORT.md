# 研究写真2件の個別承認提案

承認根拠：PR #116 comment 6228088094（2026-10-17）。
カワリハツは archive_research、Lanmaoa は approve_research_photo。対象IDを既存の管理室メソッドへ個別に再入力する。
通常14枚の承認manifestは作らない。公開スイッチfalse、main/gh-pages/監査履歴へ書き込まない。

本番観測38922030976と38990433068、10時間7分53.019397秒差、同baseline/protection/16 fingerprints、履歴4イベントを再検証済み。

現在は正式管理室処理と隔離生成を、GET認証環境を持つ一時CIで実行する準備段階。CIが検証して出力した2個のmanifestのみを次のコミットで保存する。無検証のmanifest直書きはしない。
実承認対象・差分・検証結果は完了後に追記する。マージ・公開は行わない。

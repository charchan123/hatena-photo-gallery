# 🍄 Hatena Blog Photo Gallery

はてなブログの各カテゴリごとの画像を自動収集し、GitHub Pages上にギャラリーページを生成します。

- Python + GitHub Actions で毎晩自動更新
- カテゴリ名ごとに画像をタイル表示
- 完全無料運用

## ローカル管理画面（ブログ管理者専用）

Windowsでは `admin/start_admin.bat` をダブルクリックすると、標準ライブラリだけで
`http://127.0.0.1:8765/` に「きのこブログ管理室」が起動します。公開サイトには生成・配布
されません。PR作成には別途 `gh auth login` が必要です。変更はメモリ上の「変更予定」として
保持され、検証後に一時git worktreeからbranch・commit・push・PRを作成します。

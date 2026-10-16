"""Counts-only daily monitoring, independent of publication and audit writes."""
import json
import os
from pathlib import Path


def summarize(directory='cache'):
    try:
        report=json.loads((Path(directory)/'deletion-live-audit.json').read_text())
        preview=json.loads((Path(directory)/'deletion-preview.json').read_text())
        counts=report['counts']
        assert report['read_only'] is True and report['publication']=='NOT_ATTEMPTED'
        removed=counts['deleted_images'];protected=counts['protected_deletion_candidates']
        assert type(removed) is int and type(protected) is int and 0<=protected<=removed
        state=preview['result'];assert state in {'BLOCKED','PREVIEW'}
        waiting=state=='BLOCKED'
        text=('写真削除監査：承認・公開は実行していません。\n\n'
              f'削除検出 {removed}件 / 重要参照あり {protected}件 / '
              +('公開候補は安全停止中。管理室で確認してください。' if waiting else '隔離検証完了。公開判断は別途必要です。')+'\n')
        return text,waiting
    except (OSError,ValueError,KeyError,TypeError,AssertionError):
        return '写真削除監査：取得・検証資料が不足しています。公開許可はありません。Actionsを確認してください。\n',True


def main():
    text,pending=summarize()
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as stream:stream.write(text)
    # Scheduled monitor failures use the repository's existing Actions
    # notification settings. No mail/Slack credentials or raw source content.
    return 1 if pending and os.environ.get('DELETION_MONITOR_EVENT')=='schedule' else 0


if __name__=='__main__':raise SystemExit(main())

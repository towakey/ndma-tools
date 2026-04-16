@echo off
cd /d "%~dp0"
python sync_latest_data.py
if %errorlevel% neq 0 (
    echo エラーが発生しました。ログを確認してください。
    pause
) else (
    echo 同期が正常に完了しました。
)
pause

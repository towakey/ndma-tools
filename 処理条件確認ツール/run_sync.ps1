# 同期スクリプト (PowerShell)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

try {
    python sync_latest_data.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "エラーが発生しました。ログを確認してください。" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "同期が正常に完了しました。" -ForegroundColor Green
    }
} catch {
    Write-Host "例外が発生しました: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

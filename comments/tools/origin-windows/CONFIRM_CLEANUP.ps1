param([Parameter(Mandatory=$true)][string]$RunDirectory,
      [Parameter(Mandatory=$true)][string]$ApprovalFile,
      [Parameter(Mandatory=$true)][string]$ApprovalSHA256,
      [string]$ClosureProofFile)
$ErrorActionPreference = 'Stop'
try {
    if ((Get-FileHash -LiteralPath $ApprovalFile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovalSHA256) { throw 'APPROVAL_BYTES_CHANGED' }
    $kinokoReportFile = Join-Path $RunDirectory 'diagnostic-report.json'
    if (-not (Test-Path -LiteralPath $kinokoReportFile)) { $kinokoReportFile = Join-Path $RunDirectory 'read-only-report.json' }
    $kinokoReport = Get-Content -LiteralPath $kinokoReportFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $kinokoApproval = Get-Content -LiteralPath $ApprovalFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($kinokoReport.authorization_id -ne $kinokoApproval.authorization_id) { throw 'AUTHORIZATION_MISMATCH' }
    $kinokoClosureKind = 'main-report'
    if ($kinokoReport.urls_closed -ne $true) {
        if (-not $ClosureProofFile) { throw 'CLOSURE_NOT_CONFIRMED_CHECK_DASHBOARD' }
        $kinokoProofPath = [IO.Path]::GetFullPath($ClosureProofFile)
        if ([IO.Path]::GetDirectoryName($kinokoProofPath) -ne [IO.Path]::GetFullPath($RunDirectory) -or [IO.Path]::GetFileName($kinokoProofPath) -cnotmatch '^(watchdog-report|close-only-\d+)\.json$') { throw 'CLOSURE_PROOF_PATH_INVALID' }
        $kinokoProof = Get-Content -LiteralPath $kinokoProofPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($kinokoProof.authorization_id -ne $kinokoApproval.authorization_id -or -not (($kinokoProof.result -eq 'WATCHDOG_CLOSED' -and $kinokoProof.closure_verified -eq $true) -or ($kinokoProof.result -eq 'CLOSE_ONLY_CLOSED' -and $kinokoProof.urls_closed -eq $true))) { throw 'CLOSURE_PROOF_INVALID' }
        $kinokoClosureKind = 'independent-close-report'
    }
    if ($kinokoApproval.api_token_name -cnotmatch '^kinoko-comments-origin-diag-build-\d{8}$') { throw 'TOKEN_NAME_INVALID' }
    Write-Host ('削除対象APIトークン名: ' + $kinokoApproval.api_token_name)
    Write-Host 'Cloudflare公式管理画面で対象トークンを削除し、一覧から消えたことを確認してください。'
    $kinokoAnswer = Read-Host '削除確認後だけ DELETED_IN_DASHBOARD と入力（秘密値は入力しない）'
    if ($kinokoAnswer -cne 'DELETED_IN_DASHBOARD') { throw 'DELETION_NOT_CONFIRMED' }
    $kinokoReceipt = @{ schema=1; authorization_id=$kinokoApproval.authorization_id; urls_closed_report=$true; closure_evidence=$kinokoClosureKind; post_checks_unchanged_report=($kinokoReport.post_checks_unchanged -eq $true); token_revocation='operator-dashboard-confirmation'; api_revocation_independently_verified=$false; confirmed_at_utc=[DateTimeOffset]::UtcNow.ToString('o') } | ConvertTo-Json
    $kinokoPath = Join-Path $RunDirectory 'cleanup-receipt.json'
    $kinokoStream = [IO.File]::Open($kinokoPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $kinokoBytes = [Text.Encoding]::UTF8.GetBytes($kinokoReceipt); $kinokoStream.Write($kinokoBytes,0,$kinokoBytes.Length) } finally { $kinokoStream.Dispose() }
    Write-Host 'CLEANUP_RECEIPT_SAVED evidence=operator-dashboard-confirmation no_network=true'
} catch {
    Write-Host 'CLEANUP_CONFIRMATION_STOP token_deletion_not_confirmed=true'
    throw 'CLEANUP_CONFIRMATION_STOP'
} finally {
    Remove-Item Env:CLOUDFLARE_API_TOKEN, Env:CLOUDFLARE_ACCOUNT_ID, Env:KINOKO_RETEST_OWNER_EMAIL, Env:KINOKO_ACCESS_CLIENT_ID, Env:KINOKO_ACCESS_CLIENT_SECRET, Env:KINOKO_STAGING_ADMIN_TOKEN -ErrorAction SilentlyContinue
    try { Set-Clipboard -Value ' ' } catch { }
    Write-Host ('LOCAL_CREDENTIALS_CLEARED=' + (-not ($env:CLOUDFLARE_API_TOKEN -or $env:KINOKO_RETEST_OWNER_EMAIL -or $env:KINOKO_ACCESS_CLIENT_ID -or $env:KINOKO_ACCESS_CLIENT_SECRET)))
    Remove-Variable kinokoReport, kinokoReportFile, kinokoApproval, kinokoClosureKind, kinokoProofPath, kinokoProof, kinokoAnswer, kinokoReceipt, kinokoPath, kinokoStream, kinokoBytes -ErrorAction SilentlyContinue
}

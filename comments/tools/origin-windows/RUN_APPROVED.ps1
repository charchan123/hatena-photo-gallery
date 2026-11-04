param(
    [Parameter(Mandatory=$true)][string]$ApprovalFile,
    [Parameter(Mandatory=$true)][string]$ApprovalSHA256,
    [Parameter(Mandatory=$true)][string]$ManifestSHA256,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [ValidateSet('ReadOnly','Diagnose','CloseOnly')][string]$Phase = 'ReadOnly'
)
$ErrorActionPreference = 'Stop'
$kinokoToken = $null
$kinokoOwner = $null
$kinokoPointer = [IntPtr]::Zero
$kinokoClipboardCleared = $false
try {
    if ($env:NODE_OPTIONS) { throw 'NODE_OPTIONS_FORBIDDEN' }
    if ($env:KINOKO_ACCESS_CLIENT_ID -or $env:KINOKO_ACCESS_CLIENT_SECRET -or $env:KINOKO_STAGING_ADMIN_TOKEN) { throw 'SERVICE_OR_ADMIN_CREDENTIALS_FORBIDDEN' }
    if ($ApprovalSHA256 -cnotmatch '^[a-f0-9]{64}$' -or $ManifestSHA256 -cnotmatch '^[a-f0-9]{64}$') { throw 'PUBLIC_SHA_REQUIRED' }
    & (Join-Path $PSScriptRoot 'VERIFY_OFFLINE.ps1') -ManifestSHA256 $ManifestSHA256
    $kinokoApproval = Get-Content -LiteralPath $ApprovalFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($kinokoApproval.approved -ne $true -or $kinokoApproval.authorization_id -cnotmatch '^[a-f0-9]{16,32}$') { Write-Host 'OFFLINE_APPROVAL_REJECTED no_input=true no_network=true'; throw 'APPROVAL_NOT_GRANTED' }
    $kinokoRun = Join-Path $env:LOCALAPPDATA ('KinokoCommentsStaging\origin-diag-' + $kinokoApproval.authorization_id)
    $kinokoMode = @{ ReadOnly='read-only'; Diagnose='diagnose'; CloseOnly='close-only' }[$Phase]
    $kinokoRunner = Join-Path $PSScriptRoot 'runner.mjs'
    # This validation has no network and runs before any secret prompt.
    # CloseOnly validates the same fixed lease/schema with cleanup mode instead.
    $kinokoValidateMode = if ($Phase -eq 'CloseOnly') { 'validate-close-only' } else { 'validate' }
    & node $kinokoRunner $ApprovalFile $ApprovalSHA256 $ManifestSHA256 $kinokoRun $EvidenceDirectory $kinokoValidateMode 'root-only' 'no-service-auth'
    if ($LASTEXITCODE -ne 0) { throw 'OFFLINE_VALIDATION_STOP' }
    $env:CLOUDFLARE_ACCOUNT_ID = '8b3955654c3eeda9f2679f594202a758'
    $kinokoToken = Read-Host '今回承認された新APIトークン（伏字入力・保存しません）' -AsSecureString
    $kinokoPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($kinokoToken)
    try { $env:CLOUDFLARE_API_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($kinokoPointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($kinokoPointer); $kinokoPointer = [IntPtr]::Zero }
    if ($Phase -ne 'CloseOnly') {
        $kinokoOwner = Read-Host '本人限定Allowに登録したメール（伏字入力・保存しません）' -AsSecureString
        $kinokoPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($kinokoOwner)
        try { $env:KINOKO_RETEST_OWNER_EMAIL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($kinokoPointer) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($kinokoPointer); $kinokoPointer = [IntPtr]::Zero }
    }
    & node $kinokoRunner $ApprovalFile $ApprovalSHA256 $ManifestSHA256 $kinokoRun $EvidenceDirectory $kinokoMode 'root-only' 'no-service-auth'
    if ($LASTEXITCODE -ne 0) { throw 'ORIGIN_STOP_NO_RETRY' }
    Write-Host 'PHASE_FINISHED Do_not_start_CPU_OPTIONS_or_comments Delete_API_token_in_dashboard_at_work_end'
} catch {
    # Never echo native exception messages, input values or environment variables.
    Write-Host 'ORIGIN_ENTRY_STOP Check_sanitized_report Do_not_retry_or_reopen_URL'
    throw 'ORIGIN_ENTRY_STOP_NO_RETRY'
} finally {
    if ($kinokoPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($kinokoPointer) }
    if ($null -ne $kinokoToken) { $kinokoToken.Dispose() }
    if ($null -ne $kinokoOwner) { $kinokoOwner.Dispose() }
    Remove-Item Env:CLOUDFLARE_API_TOKEN, Env:CLOUDFLARE_ACCOUNT_ID, Env:KINOKO_RETEST_OWNER_EMAIL, Env:KINOKO_ACCESS_CLIENT_ID, Env:KINOKO_ACCESS_CLIENT_SECRET, Env:KINOKO_STAGING_ADMIN_TOKEN -ErrorAction SilentlyContinue
    try { Set-Clipboard -Value ' '; $kinokoClipboardCleared = $true } catch { }
    $kinokoCleared = -not ($env:CLOUDFLARE_API_TOKEN -or $env:KINOKO_RETEST_OWNER_EMAIL -or $env:KINOKO_ACCESS_CLIENT_ID -or $env:KINOKO_ACCESS_CLIENT_SECRET -or $env:KINOKO_STAGING_ADMIN_TOKEN)
    Write-Host ('LOCAL_CREDENTIALS_CLEARED=' + $kinokoCleared + ' clipboard_overwritten=' + $kinokoClipboardCleared)
    Remove-Variable kinokoToken, kinokoOwner, kinokoPointer, kinokoApproval, kinokoRun, kinokoMode, kinokoRunner, kinokoValidateMode, kinokoCleared, kinokoClipboardCleared -ErrorAction SilentlyContinue
}

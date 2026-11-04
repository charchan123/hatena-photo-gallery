param([Parameter(Mandatory=$true)][string]$PackageDirectory)
$ErrorActionPreference = 'Stop'
$scripts = Join-Path $PackageDirectory 'comments/tools/origin-windows'
$manifest = (Get-FileHash -LiteralPath (Join-Path $PackageDirectory 'package-manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
foreach ($file in @('RUN_APPROVED.ps1','CONFIRM_CLEANUP.ps1','VERIFY_OFFLINE.ps1')) {
    $parseTokens = $null; $parseErrors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile((Join-Path $scripts $file),[ref]$parseTokens,[ref]$parseErrors)
    if ($parseErrors.Count -ne 0) { throw 'PS_SYNTAX_FAILED' }
}
& (Join-Path $scripts 'VERIFY_OFFLINE.ps1') -ManifestSHA256 $manifest
$supportFile = Join-Path $PackageDirectory 'comments/tools/access-readiness.mjs'
$supportOriginal = [IO.File]::ReadAllBytes($supportFile)
try {
    [IO.File]::AppendAllText($supportFile,"`n// synthetic corruption`n")
    $tamperRejected = $false
    try { $null = & (Join-Path $scripts 'VERIFY_OFFLINE.ps1') -ManifestSHA256 $manifest 6>&1 } catch { $tamperRejected = $true }
    if (-not $tamperRejected) { throw 'PS_HASH_GATE_FAILED' }
} finally { [IO.File]::WriteAllBytes($supportFile,$supportOriginal) }
$temp = Join-Path ([IO.Path]::GetTempPath()) ('origin-ps-offline-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $temp
$global:OriginTestPrompts = 0
function global:Read-Host {
    param([string]$Prompt,[switch]$AsSecureString)
    $global:OriginTestPrompts++
    if ($global:OriginTestPromptMode -eq 'cleanup') { return 'DELETED_IN_DASHBOARD' }
    if (-not $AsSecureString) { throw 'EXPECTED_SECURE_INPUT' }
    return ConvertTo-SecureString -String 'synthetic-powershell-input' -AsPlainText -Force
}
try {
    $template = Join-Path $scripts 'approval.template.json'
    $templateSHA = (Get-FileHash -LiteralPath $template -Algorithm SHA256).Hash.ToLowerInvariant()
    $env:CLOUDFLARE_API_TOKEN = 'synthetic-previous-input'
    $rejected = $false
    $lines = @()
    try { $lines = & (Join-Path $scripts 'RUN_APPROVED.ps1') -ApprovalFile $template -ApprovalSHA256 $templateSHA -ManifestSHA256 $manifest -EvidenceDirectory $temp 6>&1 }
    catch { $rejected = $true }
    if (-not $rejected -or $global:OriginTestPrompts -ne 0 -or $env:CLOUDFLARE_API_TOKEN) { throw 'UNAPPROVED_ENTRY_DID_NOT_STOP_AND_CLEAR' }
    # Test only: replace the Node command so this PowerShell wrapper test never
    # invokes a live phase. The real Node phases are covered by fetch-shim tests.
    $approval = Get-Content -LiteralPath $template -Raw | ConvertFrom-Json
    $approval.approved = $true; $approval.authorization_id = '0123456789abcdef'
    $approval.api_token_name = 'kinoko-comments-origin-diag-build-20990101'
    $approvalPath = Join-Path $temp 'synthetic-approval.json'
    $approval | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $approvalPath -Encoding UTF8
    $approvalSHA = (Get-FileHash -LiteralPath $approvalPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $global:OriginTestNodeCalls = 0; $global:OriginTestFailNode = $false
    function global:node {
        $global:OriginTestNodeCalls++
        if ($args[6] -like 'validate*') {
            if ($env:CLOUDFLARE_API_TOKEN) { throw 'SECRET_PRESENT_BEFORE_OFFLINE_VALIDATION' }
            $global:LASTEXITCODE = 0; return
        }
        if (-not $env:CLOUDFLARE_API_TOKEN -or -not $env:KINOKO_RETEST_OWNER_EMAIL) { throw 'SECURE_INPUT_NOT_PASSED_TO_CHILD' }
        $global:LASTEXITCODE = if ($global:OriginTestFailNode) { 1 } else { 0 }
    }
    if (-not $env:LOCALAPPDATA) { $env:LOCALAPPDATA = $temp }
    foreach ($fail in @($false,$true)) {
        $global:OriginTestFailNode = $fail; $global:OriginTestPromptMode = 'secure'
        $threw = $false
        try { $null = & (Join-Path $scripts 'RUN_APPROVED.ps1') -ApprovalFile $approvalPath -ApprovalSHA256 $approvalSHA -ManifestSHA256 $manifest -EvidenceDirectory $temp 6>&1 }
        catch { $threw = $true }
        if ($threw -ne $fail -or $env:CLOUDFLARE_API_TOKEN -or $env:KINOKO_RETEST_OWNER_EMAIL) { throw 'PS_FINALLY_CLEANUP_FAILED' }
    }
    if ($global:OriginTestNodeCalls -ne 4 -or $global:OriginTestPrompts -ne 4) { throw 'WRAPPER_PHASE_ORDER_FAILED' }
    $report = @{ urls_closed=$true; post_checks_unchanged=$true; authorization_id=$approval.authorization_id }
    $report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temp 'diagnostic-report.json') -Encoding UTF8
    $global:OriginTestPromptMode = 'cleanup'
    $null = & (Join-Path $scripts 'CONFIRM_CLEANUP.ps1') -RunDirectory $temp -ApprovalFile $approvalPath -ApprovalSHA256 $approvalSHA 6>&1
    $receipt = Get-Content -LiteralPath (Join-Path $temp 'cleanup-receipt.json') -Raw | ConvertFrom-Json
    if ($receipt.api_revocation_independently_verified -ne $false -or $receipt.token_revocation -ne 'operator-dashboard-confirmation') { throw 'DELETION_PROOF_OVERCLAIMED' }
    $previous = (Get-FileHash -LiteralPath (Join-Path $temp 'cleanup-receipt.json')).Hash
    $duplicateRejected = $false
    try { $null = & (Join-Path $scripts 'CONFIRM_CLEANUP.ps1') -RunDirectory $temp -ApprovalFile $approvalPath -ApprovalSHA256 $approvalSHA 6>&1 } catch { $duplicateRejected=$true }
    if (-not $duplicateRejected -or (Get-FileHash -LiteralPath (Join-Path $temp 'cleanup-receipt.json')).Hash -ne $previous) { throw 'CLEANUP_RECEIPT_OVERWRITTEN' }
    Write-Host 'POWERSHELL_OFFLINE_OK parsed=3 unapproved_no_input=true secure_cleanup_success_and_failure=true deletion_evidence=operator-only network=mocked'
    # The expected native failure above set LASTEXITCODE=1. Only after every
    # assertion passed, report this test process's success to the CI pwsh shell.
    $global:LASTEXITCODE = 0
} finally {
    Remove-Item Function:global:Read-Host, Function:global:node -ErrorAction SilentlyContinue
    Remove-Item Env:CLOUDFLARE_API_TOKEN, Env:KINOKO_RETEST_OWNER_EMAIL -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}

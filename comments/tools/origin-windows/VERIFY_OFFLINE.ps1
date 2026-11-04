param([Parameter(Mandatory=$true)][string]$ManifestSHA256)
$ErrorActionPreference = 'Stop'
if ($env:NODE_OPTIONS) { throw 'NODE_OPTIONS_FORBIDDEN' }
if ($ManifestSHA256 -cnotmatch '^[a-f0-9]{64}$') { throw 'MANIFEST_SHA_REQUIRED' }
$kinokoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$kinokoManifestFile = Join-Path $kinokoRoot 'package-manifest.json'
if ((Get-FileHash -LiteralPath $kinokoManifestFile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ManifestSHA256) { throw 'PACKAGE_MANIFEST_CHANGED' }
$kinokoManifest = Get-Content -LiteralPath $kinokoManifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
$kinokoExpected = @(
 'comments/tools/origin-windows/runner.mjs','comments/tools/origin-windows/preflight.mjs',
 'comments/tools/origin-windows/code-receipt.mjs','comments/tools/origin-windows/expected-seed.json',
 'comments/tools/origin-windows/approval.template.json','comments/tools/origin-windows/RUN_APPROVED.ps1',
 'comments/tools/origin-windows/CONFIRM_CLEANUP.ps1','comments/tools/origin-windows/VERIFY_OFFLINE.ps1',
 'comments/tools/origin-windows/README.md','comments/tools/access-origin-diagnostic.mjs',
 'comments/tools/access-readiness.mjs','comments/staging/access-snapshot.mjs'
)
$kinokoNames = @($kinokoManifest.files.PSObject.Properties.Name)
$kinokoDifference = Compare-Object -CaseSensitive ($kinokoExpected | Sort-Object) ($kinokoNames | Sort-Object)
if ($kinokoManifest.protocol -cne 'origin-windows-v1' -or $kinokoManifest.source_head -cnotmatch '^[a-f0-9]{40}$' -or $kinokoDifference) { throw 'PACKAGE_FILE_SET_CHANGED' }
foreach ($kinokoName in $kinokoExpected) {
    $kinokoFile = Join-Path $kinokoRoot $kinokoName
    $kinokoItem = Get-Item -LiteralPath $kinokoFile
    if ($kinokoItem.PSIsContainer -or ($kinokoItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'PACKAGE_FILE_INVALID' }
    if ((Get-FileHash -LiteralPath $kinokoFile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $kinokoManifest.files.$kinokoName) { throw 'PACKAGE_BYTES_CHANGED' }
}
Write-Host ('PACKAGE_OK source_head=' + $kinokoManifest.source_head + ' no_network=true verified_before_node_import=true')

param(
    [Parameter(Mandatory = $true)][string]$Config,
    [string]$RetryWi = '',
    [string]$PublishWi = '',
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$installDirectory = $PSScriptRoot
$manifestPath = Join-Path $installDirectory 'install-manifest.json'
$dispatcherVersion = $null
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    foreach ($entry in $manifest.files.PSObject.Properties) {
        $file = Join-Path $installDirectory $entry.Name
        if (-not (Test-Path -LiteralPath $file)) { throw "Missing installed file: $($entry.Name)" }
        if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.Value) {
            throw "Installed dispatcher changed: $($entry.Name). Run setup.ps1 again."
        }
    }
    $dispatcherVersion = $manifest.version
} else {
    if (-not (Test-Path -LiteralPath (Join-Path $installDirectory '.git'))) {
        throw 'Dispatcher is neither a verified installation nor a Git checkout.'
    }
    & git -C $installDirectory diff --quiet -- bridge.py invoke-dispatch.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Dispatcher checkout has local changes in executable files.' }
    $dispatcherVersion = (& git -C $installDirectory rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $dispatcherVersion) { throw 'Cannot determine dispatcher Git version.' }
}
if (-not (Test-Path -LiteralPath $Config)) { throw "Missing config: $Config" }
if ($RetryWi -and $RetryWi -notmatch '^WI-\d+$') { throw 'RetryWi must look like WI-012.' }
if ($PublishWi -and $PublishWi -notmatch '^WI-\d+$') { throw 'PublishWi must look like WI-012.' }
if ($RetryWi -and $PublishWi) { throw 'Choose RetryWi or PublishWi, never both.' }
$settings = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
if ($ValidateOnly) {
    & $settings.codex --version
    if ($LASTEXITCODE -ne 0) { throw 'Codex version check failed.' }
    Write-Output "Dispatcher validated: $dispatcherVersion"
    exit 0
}
$arguments = @((Join-Path $installDirectory 'bridge.py'), '--config', $Config)
if ($RetryWi) { $arguments += @('--retry-wi', $RetryWi) }
if ($PublishWi) { $arguments += @('--publish-wi', $PublishWi) }
& $settings.python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Dispatch stopped. Claims and local recovery files were preserved.' }

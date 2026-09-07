param(
    [Parameter(Mandatory = $true)][string]$Config,
    [string]$RetryWi = '',
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$installDirectory = $PSScriptRoot
$manifestPath = Join-Path $installDirectory 'install-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Missing install manifest; run setup.ps1 again.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files.PSObject.Properties) {
    $file = Join-Path $installDirectory $entry.Name
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing installed file: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.Value) {
        throw "Installed dispatcher changed: $($entry.Name). Run setup.ps1 again."
    }
}
if (-not (Test-Path -LiteralPath $Config)) { throw "Missing config: $Config" }
if ($RetryWi -and $RetryWi -notmatch '^WI-\d+$') { throw 'RetryWi must look like WI-012.' }
$settings = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
if ($ValidateOnly) {
    & $settings.codex --version
    if ($LASTEXITCODE -ne 0) { throw 'Codex version check failed.' }
    Write-Output "Dispatcher installation validated: $($manifest.version)"
    exit 0
}
$arguments = @((Join-Path $installDirectory 'bridge.py'), '--config', $Config)
if ($RetryWi) { $arguments += @('--retry-wi', $RetryWi) }
& $settings.python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Dispatch stopped. Claims and local recovery files were preserved.' }

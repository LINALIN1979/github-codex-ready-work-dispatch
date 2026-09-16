param(
    [Parameter(Mandatory = $true)][string]$Config,
    [string]$RetryWi = '',
    [string]$PublishWi = '',
    [string]$CoordinationCommand = '',
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$installDirectory = $PSScriptRoot
$manifestPath = Join-Path $installDirectory 'install-manifest.json'
$dispatcherVersion = $null
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if (-not $manifest.version -or $manifest.version -notmatch '^[0-9a-f]{40}$' -or
        -not $manifest.source_provenance -or
        $manifest.source_provenance.git_revision -ne $manifest.version) {
        throw 'Installed dispatcher provenance manifest is missing or invalid. Run setup.ps1 again.'
    }
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
if ($CoordinationCommand -and $CoordinationCommand -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') { throw 'Invalid CoordinationCommand.' }
if (@($RetryWi, $PublishWi, $CoordinationCommand).Where({ $_ }).Count -gt 1) {
    throw 'Choose RetryWi, PublishWi or CoordinationCommand, never more than one.'
}
$settings = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json

function Resolve-CodexDesktopExecutable {
    param([object]$Settings, [string]$ConfigPath)

    $desktopRoot = [IO.Path]::GetFullPath(
        (Join-Path $env:LOCALAPPDATA 'OpenAI\\Codex\\bin')).TrimEnd('\\')
    $configured = [string]$Settings.codex
    $configuredPath = if ($configured) {
        [IO.Path]::GetFullPath($configured)
    } else {
        ''
    }
    # Only managed Codex Desktop paths are auto-refreshed. A host that deliberately
    # configured a different executable retains its explicit fail-closed behavior.
    if (-not $configuredPath.StartsWith($desktopRoot + '\\', [StringComparison]::OrdinalIgnoreCase)) {
        if (-not $configuredPath -or -not (Test-Path -LiteralPath $configuredPath -PathType Leaf)) {
            throw 'Configured Codex executable is missing.'
        }
        return $configuredPath
    }

    $candidate = Get-ChildItem -LiteralPath $desktopRoot -Directory -ErrorAction SilentlyContinue |
        ForEach-Object {
            $path = Join-Path $_.FullName 'codex.exe'
            if (Test-Path -LiteralPath $path -PathType Leaf) { Get-Item -LiteralPath $path }
        } |
        Sort-Object LastWriteTime -Descending |
        ForEach-Object {
            $version = (& $_.FullName --version 2>$null).Trim()
            if ($LASTEXITCODE -eq 0 -and $version) {
                [pscustomobject]@{ Path = $_.FullName; Version = $version }
            }
        } |
        Select-Object -First 1

    if (-not $candidate) {
        throw 'No runnable Codex Desktop executable was found.'
    }
    if ($Settings.codex -ne $candidate.Path -or $Settings.codex_version -ne $candidate.Version) {
        $Settings.codex = $candidate.Path
        $Settings.codex_version = $candidate.Version
        $Settings | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ConfigPath -Encoding utf8
    }
    return $candidate.Path
}

$resolvedCodex = Resolve-CodexDesktopExecutable $settings $Config
$coordinationEnabled = [bool]$settings.coordination_ref
if ($coordinationEnabled) {
    $hasExplicitPrincipals = $null -ne $settings.trusted_coordination_principals
    $hasLegacyTrust = $settings.trusted_coordination_actors -and $settings.trusted_coordination_roles
    if ($settings.coordination_ref -notmatch '^refs/heads/codex/[A-Za-z0-9._/-]+$' -or
        $settings.coordination_ref -eq 'refs/heads/codex/dispatch-state' -or
        (-not $hasExplicitPrincipals -and -not $hasLegacyTrust) -or
        ($hasExplicitPrincipals -and -not $settings.trusted_coordination_principals) -or
        -not $settings.coordination_authority_ref) {
        throw 'Coordination configuration is incomplete or unsafe.'
    }
} elseif ($CoordinationCommand) {
    throw 'Coordination commands are disabled in this host config.'
}
if ($ValidateOnly) {
    & $resolvedCodex --version
    if ($LASTEXITCODE -ne 0) { throw 'Codex version check failed.' }
    Write-Output "Dispatcher validated: $dispatcherVersion"
    exit 0
}
$arguments = @((Join-Path $installDirectory 'bridge.py'), '--config', $Config)
if ($RetryWi) { $arguments += @('--retry-wi', $RetryWi) }
if ($PublishWi) { $arguments += @('--publish-wi', $PublishWi) }
if ($CoordinationCommand) { $arguments += @('--coordination-command', $CoordinationCommand) }
& $settings.python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Dispatch stopped. Claims and local recovery files were preserved.' }

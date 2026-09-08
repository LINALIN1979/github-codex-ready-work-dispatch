param(
    [Parameter(Mandatory = $true)][string]$HostRepo,
    [Parameter(Mandatory = $true)][string]$RunnerLabel,
    [string]$BaseBranch = 'main',
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'github-codex-ready-work-dispatch'),
    [string]$Codex = '',
    [string]$Python = '',
    [string]$WorkItemsPath = 'docs/work-items',
    [string]$WorkflowPath = '.github/workflows/codex-ready-dispatch.yml',
    [string]$ExpectedRunnerUser = '',
    [string[]]$AdditionalTriggerPath = @(),
    [string]$DataRoot = '',
    [string]$HostLockRoot = '',
    [string]$CoordinationRef = '',
    [string[]]$TrustedCoordinatorActor = @(),
    [string[]]$TrustedCoordinatorRole = @(),
    [string]$CoordinationAuthorityRef = ''
)
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
$provenancePaths = @('setup.ps1', 'bridge.py', 'invoke-dispatch.ps1', 'templates/ready-dispatch.yml.template')
$sourceRoot = (& git -C $source rev-parse --show-toplevel 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or -not $sourceRoot) { throw 'Dispatcher source must be a Git working tree.' }
$sourceRoot = (Resolve-Path -LiteralPath $sourceRoot).Path
$sourcePath = (Resolve-Path -LiteralPath $source).Path
if ($sourceRoot -ne $sourcePath) { throw 'Dispatcher setup must run from the repository root.' }
$version = (& git -C $source rev-parse --verify HEAD 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^[0-9a-f]{40}$') { throw 'Cannot determine reviewed dispatcher Git version.' }
$sourceStatus = @(& git -C $source status --porcelain=v1 --untracked-files=all -- $provenancePaths)
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify dispatcher source status.' }
if ($sourceStatus.Count -gt 0 -and $sourceStatus[0]) {
    throw ('Dispatcher source has local changes in material files: ' + ($sourceStatus -join '; '))
}
$sourceHashes = [ordered]@{}
foreach ($path in $provenancePaths) {
    $tracked = (& git -C $source ls-files --error-unmatch -- $path 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $tracked -ne $path) { throw "Material source is not tracked: $path" }
    $fullPath = Join-Path $source $path
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) { throw "Missing material source: $path" }
    $sourceHashes[$path] = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash
}
$hostPath = (Resolve-Path -LiteralPath $HostRepo).Path
if (-not (Test-Path -LiteralPath (Join-Path $hostPath '.git'))) { throw 'HostRepo must be a Git working tree root.' }
$remote = (& git -C $hostPath remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Host repo needs an origin remote.' }
if ($remote -match 'github\.com[:/](?<repo>[^/]+/[^/.]+)(?:\.git)?$') { $repository = $Matches.repo } else { throw 'Origin must be a GitHub repository URL.' }
$repositorySlug = $repository -replace '/', '-'
$installDirectory = Join-Path $InstallRoot $repositorySlug
$dataDirectory = if ($DataRoot) { $DataRoot } else { Join-Path $installDirectory 'data' }
$lockDirectory = if ($HostLockRoot) { $HostLockRoot } else { Join-Path $InstallRoot 'host-lock' }
New-Item -ItemType Directory -Force -Path $installDirectory, $dataDirectory | Out-Null
Copy-Item -LiteralPath (Join-Path $source 'bridge.py') -Destination $installDirectory -Force
Copy-Item -LiteralPath (Join-Path $source 'invoke-dispatch.ps1') -Destination $installDirectory -Force
$files = @{}
foreach ($name in @('bridge.py', 'invoke-dispatch.ps1')) {
    $files[$name] = (Get-FileHash -LiteralPath (Join-Path $installDirectory $name) -Algorithm SHA256).Hash
}
$manifest = [ordered]@{
    version = $version
    source_provenance = [ordered]@{ git_revision = $version; files = $sourceHashes }
    files = $files
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $installDirectory 'install-manifest.json') -Encoding utf8
if (-not $Codex) {
    $codexCommand = Get-Command codex.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $codexCommand) {
        $desktopCandidates = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin\*\codex.exe') -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
        $codexCommand = $desktopCandidates | Select-Object -First 1
    }
    if (-not $codexCommand) { throw 'Codex executable was not found. Pass -Codex with its full .exe path.' }
    $Codex = if ($codexCommand.Source) { $codexCommand.Source } else { $codexCommand.FullName }
}
if ([System.IO.Path]::GetExtension($Codex) -ne '.exe') { throw 'Codex must point to codex.exe, not a PowerShell or cmd shim.' }
if (-not $Python) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pythonCommand) { throw 'Python was not found. Pass -Python with its full .exe path.' }
    $Python = $pythonCommand.Source
}
$codexVersion = (& $Codex --version).Trim()
if ($LASTEXITCode -ne 0) { throw 'Codex version check failed.' }
$pythonVersion = (& $Python --version).Trim()
if ($LASTEXITCode -ne 0) { throw 'Python version check failed.' }
if ($CoordinationRef) {
    if ($CoordinationRef -notmatch '^refs/heads/codex/[A-Za-z0-9._/-]+$' -or $CoordinationRef -eq 'refs/heads/codex/dispatch-state') {
        throw 'CoordinationRef must be a dedicated refs/heads/codex/* branch.'
    }
    if (-not $TrustedCoordinatorActor -or -not $TrustedCoordinatorRole -or -not $CoordinationAuthorityRef) {
        throw 'CoordinationRef requires trusted actors, trusted roles and CoordinationAuthorityRef.'
    }
} elseif ($TrustedCoordinatorActor -or $TrustedCoordinatorRole -or $CoordinationAuthorityRef) {
    throw 'Coordination trust settings require CoordinationRef.'
}
$config = [ordered]@{
    repository = $repository
    remote = $remote
    root = $dataDirectory
    host_lock_root = $lockDirectory
    base_branch = $BaseBranch
    work_items_path = $WorkItemsPath
    codex = (Resolve-Path -LiteralPath $Codex).Path
    codex_version = $codexVersion
    python = (Resolve-Path -LiteralPath $Python).Path
    coordination_ref = $CoordinationRef
    trusted_coordination_actors = @($TrustedCoordinatorActor)
    trusted_coordination_roles = @($TrustedCoordinatorRole)
    coordination_authority_ref = $CoordinationAuthorityRef
    task_seconds = 2700
    batch_seconds = 14400
    max_items = 10
}
$configPath = Join-Path $installDirectory 'config.json'
$config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
$workflowFullPath = Join-Path $hostPath $WorkflowPath
$workflowDirectory = Split-Path -Parent $workflowFullPath
New-Item -ItemType Directory -Force -Path $workflowDirectory | Out-Null
$workflow = Get-Content -LiteralPath (Join-Path $source 'templates\ready-dispatch.yml.template') -Raw
$replacements = @{
    '__BASE_BRANCH__' = $BaseBranch
    '__WORK_ITEMS_PATH__' = $WorkItemsPath
    '__WORKFLOW_PATH__' = $WorkflowPath.Replace('\', '/')
    '__REPOSITORY__' = $repository
    '__REPOSITORY_SLUG__' = $repositorySlug
    '__RUNNER_LABEL__' = $RunnerLabel
    '__INVOKE_PATH__' = (Join-Path $installDirectory 'invoke-dispatch.ps1')
    '__CONFIG_PATH__' = $configPath
    '__EXPECTED_USER_CHECK__' = $(if ($ExpectedRunnerUser) { "if (`$env:USERNAME -ne '$ExpectedRunnerUser') { throw 'Unexpected runner user' }" } else { '# No runner username restriction configured.' })
    '__ADDITIONAL_PATHS__' = (($AdditionalTriggerPath | ForEach-Object { "      - '$($_.Replace('\', '/'))'" }) -join "`n")
}
foreach ($key in $replacements.Keys) { $workflow = $workflow.Replace($key, $replacements[$key]) }
$workflowPath = $workflowFullPath
if ((Test-Path -LiteralPath $workflowPath) -and
    -not ((Get-Content -LiteralPath $workflowPath -Raw).StartsWith('# Generated by github-codex-ready-work-dispatch'))) {
    throw "Refusing to overwrite a workflow not generated by setup: $workflowPath"
}
[System.IO.File]::WriteAllText($workflowPath, $workflow, [System.Text.UTF8Encoding]::new($false))
New-Item -ItemType Directory -Force -Path (Join-Path $hostPath $WorkItemsPath) | Out-Null
& (Join-Path $installDirectory 'invoke-dispatch.ps1') -Config $configPath -ValidateOnly
Write-Output "Setup complete for $repository"
Write-Output "Workflow created: $workflowPath"
Write-Output "Local config: $configPath"
Write-Output "Python: $pythonVersion"
Write-Output 'Next: review and commit the generated workflow. The GitHub runner must have the selected label.'

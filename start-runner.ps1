param([Parameter(Mandatory = $true)][string]$RunnerDirectory)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath (Join-Path $RunnerDirectory '.runner'))) {
    throw 'Runner not registered. Register for the host repository before starting.'
}
Set-Location -LiteralPath $RunnerDirectory
& (Join-Path $RunnerDirectory 'run.cmd')
exit $LASTEXITCODE

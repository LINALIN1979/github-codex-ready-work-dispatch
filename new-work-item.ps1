param(
    [Parameter(Mandatory = $true)][string]$HostRepo,
    [Parameter(Mandatory = $true)][string]$Title,
    [string]$Goal = '',
    [string]$Acceptance = "- Define the expected result.`n- Relevant tests pass."
)
$ErrorActionPreference = 'Stop'
$hostPath = (Resolve-Path -LiteralPath $HostRepo).Path
$directory = Join-Path $hostPath 'docs\work-items'
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$numbers = Get-ChildItem -LiteralPath $directory -Filter 'WI-*.md' -ErrorAction SilentlyContinue |
    ForEach-Object { if ($_.Name -match '^WI-(\d+)-') { [int]$Matches[1] } }
$number = if ($numbers) { ($numbers | Measure-Object -Maximum).Maximum + 1 } else { 1 }
$id = 'WI-{0:D3}' -f $number
$slug = (($Title.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-'))
if (-not $slug) { $slug = 'work-item' }
$path = Join-Path $directory "$id-$slug.md"
$resolvedGoal = if ($Goal) { $Goal } else { $Title }
$body = @"
# $id — $Title

Status: Ready
Owner Role: Implementer

## Goal

$resolvedGoal

## Acceptance criteria

$Acceptance
"@
[System.IO.File]::WriteAllText($path, $body.TrimStart() + "`n", [System.Text.UTF8Encoding]::new($false))
Write-Output "Created $path"
Write-Output 'Review the goal and acceptance criteria, then commit and push the file.'

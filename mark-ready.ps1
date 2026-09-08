param(
    [Parameter(Mandatory = $true)][string]$HostRepo,
    [Parameter(Mandatory = $true)][string]$WorkItem
)
$ErrorActionPreference = 'Stop'
$hostPath = (Resolve-Path -LiteralPath $HostRepo).Path
$directory = (Resolve-Path -LiteralPath (Join-Path $hostPath 'docs\work-items')).Path
$candidate = if ([System.IO.Path]::IsPathRooted($WorkItem)) { $WorkItem } else { Join-Path $directory $WorkItem }
$path = (Resolve-Path -LiteralPath $candidate).Path
if (-not $path.StartsWith($directory + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'WorkItem must be inside the host docs/work-items directory.'
}
if ((Split-Path -Leaf $path) -notmatch '^WI-\d+-[\w-]+\.md$') { throw 'WorkItem filename must look like WI-012-name.md.' }
$text = Get-Content -LiteralPath $path -Raw

function Field([string]$Name) {
    $matches = [regex]::Matches($text, "(?m)^$([regex]::Escape($Name)):\s*([^\r\n]+)$")
    if ($matches.Count -gt 1) { throw "WorkItem has duplicate $Name fields." }
    if ($matches.Count -eq 0) { return $null }
    return $matches[0].Groups[1].Value.Trim()
}

$statusMatches = [regex]::Matches($text, '(?m)^Status:\s*([^\r\n]+)$')
if ($statusMatches.Count -ne 1 -or $statusMatches[0].Groups[1].Value.Trim() -ne 'Planned') {
    throw 'Only one Status: Planned work item can be promoted.'
}
$role = Field 'Owner Role'
$validRoles = @('Implementer', 'Tester / Playtester', 'Docs / Traceability')
if ($role -and $validRoles -notcontains $role) { throw 'Owner Role is not in the closed dispatcher role vocabulary.' }
$tier = Field 'Capability Tier'
if ($tier -and $tier -notmatch '^T[12](?:\b| )') { throw 'Capability Tier must be T1 or T2.' }

foreach ($heading in @('Goal', 'Acceptance criteria')) {
    $headings = [regex]::Matches($text, "(?m)^##\s+$([regex]::Escape($heading))\s*$")
    if ($headings.Count -ne 1) { throw "WorkItem must contain exactly one ## $heading heading." }
    $start = $headings[0].Index + $headings[0].Length
    $remaining = $text.Substring($start)
    $next = [regex]::Match($remaining, '(?m)^##\s+')
    $body = if ($next.Success) { $remaining.Substring(0, $next.Index) } else { $remaining }
    if (-not $body.Trim()) { throw "## $heading must contain content." }
    if ($heading -eq 'Acceptance criteria' -and $body -notmatch '(?m)^\s*[-*+]\s+\S') {
        throw 'Acceptance criteria must contain at least one non-empty list item.'
    }
}

$status = $statusMatches[0]
$updated = $text.Remove($status.Index, $status.Length).Insert($status.Index, 'Status: Ready')
[System.IO.File]::WriteAllText($path, $updated, [System.Text.UTF8Encoding]::new($false))
Write-Output "Promoted $path to Ready"

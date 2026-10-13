param(
    [Parameter(Mandatory=$true)][string]$Plan,
    [Parameter(Mandatory=$true)][string]$VerifiedSources,
    [Parameter(Mandatory=$true)][string]$Report
)
$ErrorActionPreference = 'Stop'
$allowedRoots = @(
    'E:\Models Blender\From Scenario\Grenade',
    'E:\Games\RING-godot\_asset_src\grenade_codex'
)
$inventory = Get-Content -LiteralPath $Plan -Raw -Encoding utf8 | ConvertFrom-Json
$verified = Get-Content -LiteralPath $VerifiedSources -Raw -Encoding utf8 | ConvertFrom-Json
if (-not $verified.pass -or @($verified.files).Count -ne 2) { throw 'Current-source verification is missing' }
$protected = @($verified.files.file)
foreach ($source in $verified.files) {
    $sourceFolder = [IO.Path]::GetDirectoryName($source.file)
    foreach ($image in $source.images) { $protected += Join-Path $sourceFolder $image.path }
}
$protected = @($protected | Sort-Object -Unique)
foreach ($source in $verified.files) {
    if ((Get-FileHash -LiteralPath $source.file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $source.sha256) {
        throw ('Retained .blend changed after verification: ' + $source.file)
    }
}

# Validate every resolved absolute deletion target before the first deletion.
$validated = @()
foreach ($entry in $inventory.targets) {
    $root = (Resolve-Path -LiteralPath $entry.root).ProviderPath.TrimEnd('\')
    if ($root -notin $allowedRoots) { throw ('Unapproved root: ' + $root) }
    $target = (Resolve-Path -LiteralPath $entry.path).ProviderPath
    if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw ('Deletion target is outside its root: ' + $target)
    }
    foreach ($source in $protected) {
        if ($source -eq $target -or $source.StartsWith($target.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw ('Target contains the retained source: ' + $target)
        }
    }
    $item = Get-Item -LiteralPath $target -Force
    $entries = if ($item.PSIsContainer) { @(Get-ChildItem -LiteralPath $target -Recurse -Force) } else { @($item) }
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or @($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
        throw ('Deletion target contains a link or junction: ' + $target)
    }
    $bytes = [long](($entries | Where-Object { -not $_.PSIsContainer } | Measure-Object -Property Length -Sum).Sum)
    if ($bytes -ne [long]$entry.bytes) { throw ('Target changed since inventory: ' + $target) }
    $validated += [PSCustomObject]@{path=$target;directory=$item.PSIsContainer;bytes=$bytes}
}

$deleted = @()
foreach ($entry in $validated) {
    if ($entry.directory) { Remove-Item -LiteralPath $entry.path -Recurse -Force }
    else { Remove-Item -LiteralPath $entry.path -Force }
    if (Test-Path -LiteralPath $entry.path) { throw ('Deletion failed: ' + $entry.path) }
    $deleted += $entry
}
foreach ($source in $verified.files) {
    if ((Get-FileHash -LiteralPath $source.file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $source.sha256) {
        throw ('Retained .blend changed during cleanup: ' + $source.file)
    }
}
[PSCustomObject]@{
    completed=(Get-Date).ToString('o')
    deleted=$deleted
    bytes=[long](($deleted | Measure-Object -Property bytes -Sum).Sum)
    retained=$verified.files
} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Report -Encoding utf8
Write-Output ('CLEANUP_COMPLETED: {0} targets, {1:N2} GiB removed; both .blend hashes unchanged' -f $deleted.Count, (($deleted | Measure-Object bytes -Sum).Sum/1GB))

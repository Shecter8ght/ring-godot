$ErrorActionPreference = 'Stop'
$pmCleanupWorkspace = 'E:\Games\RING-godot\_asset_src\pm_texturing'
$pmCleanupPlan = Get-Content -LiteralPath (Join-Path $pmCleanupWorkspace 'checks\cleanup_plan.json') -Raw | ConvertFrom-Json
$pmCleanupRoots = @('E:\Models Blender\WEAPONS\ПМ — модели и текстуры', 'E:\Games\RING-godot\_asset_src\pm_refinement')
$pmProtectedSource = [IO.Path]::GetFullPath($pmCleanupPlan.approved_file)
$pmExpectedHash = $pmCleanupPlan.approved_sha256
$pmSourceBefore = (Get-FileHash -LiteralPath $pmProtectedSource -Algorithm SHA256).Hash.ToLowerInvariant()
$pmFrozenCopy = Join-Path $pmCleanupWorkspace 'approved\PM_Geometry_v11_APPROVED.blend'
if ($pmSourceBefore -ne $pmExpectedHash -or (Get-FileHash -LiteralPath $pmFrozenCopy -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pmExpectedHash) { throw 'Approved source differs from frozen acceptance' }
$pmDeleteVerified = @()
foreach ($pmTarget in $pmCleanupPlan.targets) {
    $pmAbsoluteTarget = [IO.Path]::GetFullPath($pmTarget.path)
    $pmInsideRoot = $false
    foreach ($pmAllowedRoot in $pmCleanupRoots) {
        $pmAbsoluteRoot = [IO.Path]::GetFullPath($pmAllowedRoot).TrimEnd('\')
        if ($pmAbsoluteTarget.StartsWith($pmAbsoluteRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { $pmInsideRoot = $true }
    }
    if (-not $pmInsideRoot -or $pmProtectedSource.StartsWith($pmAbsoluteTarget.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe cleanup target: $pmAbsoluteTarget" }
    $pmTargetItem = Get-Item -LiteralPath $pmAbsoluteTarget -Force
    if (-not $pmTargetItem.PSIsContainer -or ($pmTargetItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Unexpected target type: $pmAbsoluteTarget" }
    $pmChildren = @(Get-ChildItem -LiteralPath $pmAbsoluteTarget -Recurse -Force)
    if (@($pmChildren | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count -gt 0) { throw "Reparse point in target: $pmAbsoluteTarget" }
    $pmDeleteVerified += [PSCustomObject]@{ path = $pmAbsoluteTarget; files = @($pmChildren | Where-Object { -not $_.PSIsContainer }).Count; bytes = [long](($pmChildren | Where-Object { -not $_.PSIsContainer } | Measure-Object -Property Length -Sum).Sum) }
}
# Validate every absolute target before the first recursive delete.
$pmReportPath = Join-Path $pmCleanupWorkspace 'checks\cleanup_report.json'
$pmCleanupReport = [ordered]@{ authorization = $pmCleanupPlan.authorization; protected_source = $pmProtectedSource; approved_sha256 = $pmExpectedHash; targets = $pmDeleteVerified; complete = $false }
$pmCleanupReport | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $pmReportPath -Encoding utf8
foreach ($pmVerifiedTarget in $pmDeleteVerified) { Remove-Item -LiteralPath $pmVerifiedTarget.path -Recurse -Force }
$pmSourceAfter = (Get-FileHash -LiteralPath $pmProtectedSource -Algorithm SHA256).Hash.ToLowerInvariant()
if ($pmSourceBefore -ne $pmSourceAfter) { throw 'Approved file changed during cleanup' }
$pmCleanupReport.complete = $true
$pmCleanupReport.source_unchanged = $true
$pmCleanupReport.removed_bytes = [long](($pmDeleteVerified | Measure-Object -Property bytes -Sum).Sum)
$pmCleanupReport | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $pmReportPath -Encoding utf8
Write-Output ('PM_CLEANUP_PASS folders=' + $pmDeleteVerified.Count + ' bytes=' + $pmCleanupReport.removed_bytes)

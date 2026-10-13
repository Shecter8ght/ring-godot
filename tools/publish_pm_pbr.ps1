$ErrorActionPreference = 'Stop'
$pmStage = [IO.Path]::GetFullPath('E:\Games\RING-godot\_asset_src\pm_texturing\delivery')
$pmLibrary = [IO.Path]::GetFullPath('E:\Models Blender\WEAPONS\ПМ — модели и текстуры')
$pmPublish = [IO.Path]::GetFullPath((Join-Path $pmLibrary '14_Текстуры_v1_на_проверку'))
if (-not $pmPublish.StartsWith($pmLibrary.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or $pmPublish -eq $pmLibrary) { throw 'Unsafe PM destination' }
if (Test-Path -LiteralPath $pmPublish) { throw 'Existing library package will not be overwritten' }
$pmApproved = 'E:\Models Blender\WEAPONS\ПМ — модели и текстуры\13_Доработка_v11_Сопряжения_на_проверку\01_ПМ\PM_Geometry_v11.blend'
if ((Get-FileHash -LiteralPath $pmApproved -Algorithm SHA256).Hash.ToLowerInvariant() -ne '8de3fbd27661187aa0edcf5a21db05f07a5e104b0538735e6b181b7a62c2be09') { throw 'Approved geometry changed' }
foreach ($pmCondition in @(100,60,20)) {
    $pmCheck = Get-Content -Raw -LiteralPath (Join-Path $pmStage ('04_Проверки\native_' + $pmCondition + '.json')) | ConvertFrom-Json
    if (-not $pmCheck.pass_checks) { throw ('PBR validation failed for ' + $pmCondition) }
}
$pmStageFiles = @(Get-ChildItem -LiteralPath $pmStage -File -Recurse | Where-Object { $_.Extension -ne '.blend1' })
if (@(Get-ChildItem -LiteralPath $pmStage -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count -gt 0) { throw 'Reparse point in PM stage' }
$pmSnapshot = @()
foreach ($pmStageFile in $pmStageFiles) {
    $pmRelative = [IO.Path]::GetRelativePath($pmStage, $pmStageFile.FullName)
    $pmSnapshot += [PSCustomObject]@{ relative = $pmRelative; bytes = $pmStageFile.Length; sha256 = (Get-FileHash -LiteralPath $pmStageFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
}
New-Item -ItemType Directory -Path $pmPublish | Out-Null
foreach ($pmItem in $pmSnapshot) {
    $pmDestination = [IO.Path]::GetFullPath((Join-Path $pmPublish $pmItem.relative))
    if (-not $pmDestination.StartsWith($pmPublish.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Escaped PM destination' }
    $pmParent = [IO.Path]::GetDirectoryName($pmDestination)
    if (-not (Test-Path -LiteralPath $pmParent)) { New-Item -ItemType Directory -Path $pmParent | Out-Null }
    Copy-Item -LiteralPath (Join-Path $pmStage $pmItem.relative) -Destination $pmDestination
    if ((Get-FileHash -LiteralPath $pmDestination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pmItem.sha256) { throw ('Copied-file mismatch: ' + $pmItem.relative) }
}
[ordered]@{ source = $pmStage; destination = $pmPublish; files = $pmSnapshot; verified = $true } | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $pmPublish 'package_manifest.json') -Encoding utf8
Write-Output ('PM_PBR_PUBLISHED ' + $pmPublish + ' files=' + $pmSnapshot.Count)

$ErrorActionPreference = 'Stop'
$sourcePackage = 'E:\Games\RING-godot\_asset_src\pm_texturing\revision_20_v02\delivery'
$libraryRoot = [IO.Path]::GetFullPath('E:\Models Blender\WEAPONS\ПМ — модели и текстуры')
$targetPackage = [IO.Path]::GetFullPath((Join-Path $libraryRoot '15_Текстуры_v2_20_на_проверку'))
$expectedGeometry = '8de3fbd27661187aa0edcf5a21db05f07a5e104b0538735e6b181b7a62c2be09'
$geometryFile = Join-Path $libraryRoot '13_Доработка_v11_Сопряжения_на_проверку\01_ПМ\PM_Geometry_v11.blend'
if ((Get-FileHash -LiteralPath $geometryFile -Algorithm SHA256).Hash.ToLower() -ne $expectedGeometry) { throw 'Accepted geometry source hash changed' }
if (-not $targetPackage.StartsWith($libraryRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Target outside library root' }
if (Test-Path -LiteralPath $targetPackage) { throw 'New review folder already exists; refusing to overwrite it' }
$manifestPath = Join-Path $sourcePackage 'package_manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$validation = Get-Content -LiteralPath (Join-Path $sourcePackage '04_Проверки\delivery_validation.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $validation.pass_checks -or $manifest.geometry_source_sha256 -ne $expectedGeometry) { throw 'Review package not validated' }
$protectedFiles = @($geometryFile,(Join-Path $libraryRoot '14_Текстуры_v1_на_проверку\01_ПМ\PM_Textures_100_v01.blend'),(Join-Path $libraryRoot '14_Текстуры_v1_на_проверку\01_ПМ\PM_Textures_60_v01.blend'))
$protected = foreach ($path in $protectedFiles) { [pscustomobject]@{path=$path;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()} }
$copyPlan = foreach ($row in $manifest.files) {
    $src = [IO.Path]::GetFullPath((Join-Path $sourcePackage $row.file))
    $dst = [IO.Path]::GetFullPath((Join-Path $targetPackage $row.file))
    if (-not $src.StartsWith($sourcePackage + '\',[StringComparison]::OrdinalIgnoreCase) -or -not $dst.StartsWith($targetPackage + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid package path' }
    if ((Get-Item -LiteralPath $src).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse source file' }
    if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLower() -ne $row.sha256) { throw 'Source package hash mismatch' }
    [pscustomobject]@{source=$src;target=$dst;sha256=$row.sha256}
}
# Copy only the sealed, already validated file list to an entirely new folder.
New-Item -ItemType Directory -Path $targetPackage | Out-Null
foreach ($row in $copyPlan) {
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($row.target)) -Force | Out-Null
    Copy-Item -LiteralPath $row.source -Destination $row.target
    if ((Get-FileHash -LiteralPath $row.target -Algorithm SHA256).Hash.ToLower() -ne $row.sha256) { throw 'Published copy hash mismatch' }
}
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $targetPackage 'package_manifest.json')
foreach ($row in $protected) { if ((Get-FileHash -LiteralPath $row.path -Algorithm SHA256).Hash.ToLower() -ne $row.sha256) { throw 'Protected source changed during publication' } }
$report = [pscustomobject]@{target=$targetPackage;files=$copyPlan.Count;protected=$protected;pass_checks=$true;owner_accepted=$false}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath 'E:\Games\RING-godot\_asset_src\pm_texturing\revision_20_v02\checks\publication.json' -Encoding UTF8
Write-Output ('PM_20_PUBLISHED ' + $targetPackage + ' files=' + $copyPlan.Count)

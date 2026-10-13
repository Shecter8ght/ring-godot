$ErrorActionPreference = 'Stop'
$sourcePackage = 'E:\Games\RING-godot\_asset_src\pm_texturing\revision_20_v03\delivery'
$libraryRoot = [IO.Path]::GetFullPath('E:\Models Blender\WEAPONS\ПМ — модели и текстуры')
$targetPackage = [IO.Path]::GetFullPath((Join-Path $libraryRoot '16_Текстуры_v3_20_на_проверку'))
if (-not $targetPackage.StartsWith($libraryRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Target outside library root' }
if (Test-Path -LiteralPath $targetPackage) { throw 'Review folder already exists; refusing to overwrite it' }
$manifest = Get-Content -LiteralPath (Join-Path $sourcePackage 'package_manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$check = Get-Content -LiteralPath (Join-Path $sourcePackage '04_Проверки\delivery_validation.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $check.pass_checks) { throw 'Package not validated' }
$geometry = Join-Path $libraryRoot '13_Доработка_v11_Сопряжения_на_проверку\01_ПМ\PM_Geometry_v11.blend'
if ((Get-FileHash -LiteralPath $geometry -Algorithm SHA256).Hash.ToLower() -ne '8de3fbd27661187aa0edcf5a21db05f07a5e104b0538735e6b181b7a62c2be09') { throw 'Accepted geometry hash changed' }
$protected = @($geometry,(Join-Path $libraryRoot '15_Текстуры_v2_20_на_проверку\01_ПМ\PM_Textures_20_v02.blend'),(Join-Path $libraryRoot '14_Текстуры_v1_на_проверку\01_ПМ\PM_Textures_100_v01.blend'),(Join-Path $libraryRoot '14_Текстуры_v1_на_проверку\01_ПМ\PM_Textures_60_v01.blend'))
$hashes = foreach ($p in $protected) { [pscustomobject]@{path=$p;sha256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower()} }
$plan = foreach ($row in $manifest.files) {
    $src=[IO.Path]::GetFullPath((Join-Path $sourcePackage $row.file));$dst=[IO.Path]::GetFullPath((Join-Path $targetPackage $row.file))
    if (-not $src.StartsWith($sourcePackage + '\',[StringComparison]::OrdinalIgnoreCase) -or -not $dst.StartsWith($targetPackage + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid manifest path' }
    if ((Get-Item -LiteralPath $src).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse source file' }
    if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLower() -ne $row.sha256) { throw 'Source hash mismatch' }
    [pscustomobject]@{source=$src;target=$dst;sha256=$row.sha256}
}
New-Item -ItemType Directory -Path $targetPackage | Out-Null
foreach ($row in $plan) {
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($row.target)) -Force | Out-Null
    Copy-Item -LiteralPath $row.source -Destination $row.target
    if ((Get-FileHash -LiteralPath $row.target -Algorithm SHA256).Hash.ToLower() -ne $row.sha256) { throw 'Copy hash mismatch' }
}
Copy-Item -LiteralPath (Join-Path $sourcePackage 'package_manifest.json') -Destination (Join-Path $targetPackage 'package_manifest.json')
foreach ($row in $hashes) { if ((Get-FileHash -LiteralPath $row.path -Algorithm SHA256).Hash.ToLower() -ne $row.sha256) { throw 'Protected source changed' } }
[pscustomobject]@{target=$targetPackage;pass_checks=$true;protected=$hashes} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath 'E:\Games\RING-godot\_asset_src\pm_texturing\revision_20_v03\checks\publication.json' -Encoding UTF8
Write-Output ('PM_20_V03_PUBLISHED ' + $targetPackage)

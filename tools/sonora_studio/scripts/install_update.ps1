$ErrorActionPreference = 'Stop'
$sourceDir = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\dist\win-unpacked'))
$installRoot = 'D:\ПРОГРАММЫ\Sonora Studio'
$versionDir = Join-Path $installRoot 'Версии\1.6.0'
$backupDir = Join-Path $installRoot ('Резервные версии\До-1.6-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
foreach ($targetPath in @($versionDir, $backupDir)) {
    if (-not [IO.Path]::GetFullPath($targetPath).StartsWith($installRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Путь установки вышел за пределы папки Sonora Studio.'
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $sourceDir 'resources\app.asar'))) { throw 'Сборка не найдена.' }
$running = Get-Process | Where-Object { $_.ProcessName -eq 'Sonora Studio' -and $_.Path -eq (Join-Path $installRoot 'Sonora Studio.exe') }
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
foreach ($relative in @('Sonora Studio.exe', 'resources\app.asar', 'Руководство.md', 'Sonora-Studio-source.zip', 'SHA256SUMS.txt', 'Обновление запуска.json')) {
    $previous = Join-Path $installRoot $relative
    if (Test-Path -LiteralPath $previous) {
        $backupFile = Join-Path $backupDir $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $backupFile) -Force | Out-Null
        Copy-Item -LiteralPath $previous -Destination $backupFile
    }
}
New-Item -ItemType Directory -Path $versionDir -Force | Out-Null
foreach ($entry in Get-ChildItem -LiteralPath $sourceDir -Force) {
    Copy-Item -LiteralPath $entry.FullName -Destination $versionDir -Recurse -Force
    if (-not $running) { Copy-Item -LiteralPath $entry.FullName -Destination $installRoot -Recurse -Force }
}
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
foreach ($name in @('Новое в Sonora 1.6.md', 'README.ru.md')) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination (Join-Path $versionDir $name) -Force
    Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination (Join-Path $installRoot $name) -Force
}
Copy-Item -LiteralPath (Join-Path $sourceRoot 'dist\Sonora-Studio-source.zip') -Destination (Join-Path $installRoot 'Sonora-Studio-source.zip') -Force
foreach ($target in @($installRoot, $versionDir)) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot 'README.ru.md') -Destination (Join-Path $target 'Руководство.md') -Force
}
$shell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Sonora Studio.lnk'
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $versionDir 'Sonora Studio.exe'
$shortcut.WorkingDirectory = $versionDir
$shortcut.IconLocation = $shortcut.TargetPath
$shortcut.Description = 'Sonora Studio 1.6 — монтаж и звуковой стенд RING'
$shortcut.Save()
$filesVerified = 0
foreach ($relative in @('Sonora Studio.exe', 'resources\app.asar', 'resources\bin\ffmpeg.exe')) {
    $expected = (Get-FileHash -LiteralPath (Join-Path $sourceDir $relative) -Algorithm SHA256).Hash
    $targets = @($versionDir)
    if (-not $running) { $targets += $installRoot }
    foreach ($target in $targets) {
        if ((Get-FileHash -LiteralPath (Join-Path $target $relative) -Algorithm SHA256).Hash -ne $expected) { throw "Несовпадение файла: $relative" }
        $filesVerified++
    }
}
$record = [ordered]@{status='pass'; version='1.6.0'; installed=$versionDir; rootUpdated=(-not [bool]$running); backup=$backupDir; shortcut=$shortcutPath; filesVerified=$filesVerified}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $installRoot 'Обновление запуска.json') -Encoding utf8
$hashLines = foreach ($relative in @('Sonora Studio.exe', 'resources\app.asar')) {
    ((Get-FileHash -LiteralPath (Join-Path $versionDir $relative) -Algorithm SHA256).Hash.ToLowerInvariant()) + '  ' + $relative
}
$hashLines | Set-Content -LiteralPath (Join-Path $versionDir 'SHA256SUMS.txt') -Encoding utf8
if ($running) {
    $helperPath = Join-Path $versionDir 'Complete-RootUpdate.ps1'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'complete_root_update.ps1') -Destination $helperPath -Force
    $powerShellPath = (Get-Process -Id $PID).Path
    if ($powerShellPath -notmatch '(pwsh|powershell)\.exe$') { $powerShellPath = (Get-Command powershell.exe).Source }
    Start-Process -FilePath $powerShellPath -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $helperPath + '"')) -WindowStyle Hidden
}
$record | ConvertTo-Json

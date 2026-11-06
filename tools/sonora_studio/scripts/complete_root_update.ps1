$ErrorActionPreference = 'Stop'
$installRoot = 'D:\ПРОГРАММЫ\Sonora Studio'
$versionDir = Join-Path $installRoot 'Версии\1.6.0'
$rootExecutable = Join-Path $installRoot 'Sonora Studio.exe'
while (Get-Process | Where-Object { $_.ProcessName -eq 'Sonora Studio' -and $_.Path -eq $rootExecutable }) {
    Start-Sleep -Seconds 2
}
try {
    foreach ($entry in Get-ChildItem -LiteralPath $versionDir -Force) {
        if ($entry.Name -eq 'Complete-RootUpdate.ps1') { continue }
        Copy-Item -LiteralPath $entry.FullName -Destination $installRoot -Recurse -Force
    }
    $recordPath = Join-Path $installRoot 'Обновление запуска.json'
    $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    foreach ($relative in @('Sonora Studio.exe', 'resources\app.asar')) {
        if ((Get-FileHash -LiteralPath (Join-Path $versionDir $relative)).Hash -ne (Get-FileHash -LiteralPath (Join-Path $installRoot $relative)).Hash) {
            throw "Несовпадение файла: $relative"
        }
    }
    $record.rootUpdated = $true
    $record | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $versionDir 'Ошибка обновления основной копии.txt') -Encoding utf8
    exit 1
}

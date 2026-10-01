# Пакетный композит в установленной Krita, без изменения настроек пользователя.
param([string]$KritaRunner = 'D:\ПРОГРАММЫ\Krita (x64)\bin\kritarunner.exe', [string]$AssetId = '')
$vssProject = Split-Path $PSScriptRoot -Parent
$vssRaw = Join-Path $vssProject '_asset_src\vss_textured'
if ($AssetId -and ($AssetId -notmatch '^[A-Za-z0-9_]+$' -or -not (Test-Path -LiteralPath (Join-Path $vssRaw $AssetId) -PathType Container))) {
    throw 'Некорректный или отсутствующий идентификатор ассета.'
}
$vssRuntime = Join-Path $vssRaw 'krita_runtime'
$vssScripts = Join-Path $vssRuntime 'pykrita'
New-Item -ItemType Directory -Path $vssScripts -Force | Out-Null
$vssScriptModule = 'codex_vss_texture_finish_scoped_20261001'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'krita_vss_texture_finish.py') -Destination (Join-Path $vssScripts ($vssScriptModule + '.py'))
# Windows Runner ищет модуль в пользовательском каталоге pykrita; helper существует только на время запуска.
$vssUserScripts = Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'kritarunner\pykrita'
New-Item -ItemType Directory -Path $vssUserScripts -Force | Out-Null
$vssUserHelper = Join-Path $vssUserScripts ($vssScriptModule + '.py')
$vssPreviousHelper = if (Test-Path -LiteralPath $vssUserHelper) { [System.IO.File]::ReadAllBytes($vssUserHelper) } else { $null }
$vssFontConfig = Join-Path $vssRuntime 'fonts.conf'
$vssFontCache = (Join-Path $vssRuntime 'font-cache').Replace('\','/')
$vssXml = '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>C:/Windows/Fonts</dir><cachedir>'+[System.Security.SecurityElement]::Escape($vssFontCache)+'</cachedir></fontconfig>'
[System.IO.File]::WriteAllText($vssFontConfig,$vssXml)
$vssStart = New-Object System.Diagnostics.ProcessStartInfo
$vssStart.FileName = $KritaRunner
$vssStart.Arguments = '--script '+$vssScriptModule+' --function main "'+$vssRaw+'"'
if ($AssetId) {
    $vssStart.Arguments += ' '+$AssetId
}
$vssStart.UseShellExecute = $false
$vssStart.CreateNoWindow = $true
$vssStart.WindowStyle = 'Hidden'
$vssStart.EnvironmentVariables['QT_QPA_PLATFORM'] = 'windows'
$vssStart.EnvironmentVariables['FONTCONFIG_FILE'] = $vssFontConfig
$vssStart.EnvironmentVariables['EXTRA_RESOURCE_DIRS'] = $vssRuntime
$vssRun = New-Object System.Diagnostics.Process
$vssRun.StartInfo = $vssStart
$vssMarker = Join-Path $vssRaw 'krita-progress.json'
try {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'krita_vss_texture_finish.py') -Destination $vssUserHelper
    [System.IO.File]::WriteAllText($vssMarker,'{"phase":"waiting_for_Krita"}')
    $null = $vssRun.Start()
    $vssRun.WaitForExit()
} finally {
    if ($null -ne $vssPreviousHelper) {
        [System.IO.File]::WriteAllBytes($vssUserHelper,$vssPreviousHelper)
    } else {
        Remove-Item -LiteralPath $vssUserHelper
    }
}
$vssState = Get-Content -LiteralPath (Join-Path $vssRaw 'krita-progress.json') -Raw | ConvertFrom-Json
if ($vssRun.ExitCode -ne 0 -or $vssState.status -ne 'PASS') { throw 'Krita не подтвердила сохранение всех текстур.' }
if ($AssetId) {
    Write-Output ('Krita: атласы '+$AssetId+' сохранены и повторно открыты; остальные отчёты сохранены.')
} else {
    Write-Output ('Krita: '+$vssState.reports.Count+' слоистых атласов сохранены и повторно открыты.')
}

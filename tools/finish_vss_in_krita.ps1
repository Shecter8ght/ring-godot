# Пакетный композит в установленной Krita, без изменения настроек пользователя.
param([string]$KritaRunner = 'D:\ПРОГРАММЫ\Krita (x64)\bin\kritarunner.exe')
$vssProject = Split-Path $PSScriptRoot -Parent
$vssRaw = Join-Path $vssProject '_asset_src\vss_textured'
$vssRuntime = Join-Path $vssRaw 'krita_runtime'
$vssScripts = Join-Path $vssRuntime 'pykrita'
New-Item -ItemType Directory -Path $vssScripts -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'krita_vss_texture_finish.py') -Destination (Join-Path $vssScripts 'codex_vss_texture_finish_20261001.py')
$vssFontConfig = Join-Path $vssRuntime 'fonts.conf'
$vssFontCache = (Join-Path $vssRuntime 'font-cache').Replace('\','/')
$vssXml = '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>C:/Windows/Fonts</dir><cachedir>'+[System.Security.SecurityElement]::Escape($vssFontCache)+'</cachedir></fontconfig>'
[System.IO.File]::WriteAllText($vssFontConfig,$vssXml)
$vssStart = New-Object System.Diagnostics.ProcessStartInfo
$vssStart.FileName = $KritaRunner
$vssStart.Arguments = '--script codex_vss_texture_finish_20261001 --function main "'+$vssRaw+'"'
$vssStart.UseShellExecute = $false
$vssStart.CreateNoWindow = $true
$vssStart.WindowStyle = 'Hidden'
$vssStart.EnvironmentVariables['QT_QPA_PLATFORM'] = 'windows'
$vssStart.EnvironmentVariables['FONTCONFIG_FILE'] = $vssFontConfig
$vssStart.EnvironmentVariables['EXTRA_RESOURCE_DIRS'] = $vssRuntime
$vssRun = New-Object System.Diagnostics.Process
$vssRun.StartInfo = $vssStart
$null = $vssRun.Start()
$vssRun.WaitForExit()
$vssState = Get-Content -LiteralPath (Join-Path $vssRaw 'krita-progress.json') -Raw | ConvertFrom-Json
if ($vssRun.ExitCode -ne 0 -or $vssState.status -ne 'PASS') { throw 'Krita не подтвердила сохранение всех текстур.' }
Write-Output ('Krita: '+$vssState.reports.Count+' слоистых атласов сохранены и повторно открыты.')

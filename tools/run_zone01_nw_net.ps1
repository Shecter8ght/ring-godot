param(
    [ValidateSet('loot', 'population')][string]$Mode = 'loot',
    [ValidateSet(2, 3)][int]$Count = 3
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
# Путь движка читается из единственного принятого проектом места.
$taskConfig = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'godot.cmd') -Raw
if ($taskConfig -notmatch '(?m)^"([^"\r\n]+\.exe)"') { throw 'Не найден движок в godot.cmd' }
$taskEngine = $Matches[1]
$env:SDL_JOYSTICK_DIRECTINPUT = '0'
if ($Mode -eq 'loot') {
    $Count = 2
    $env:LOOT_NET_LEVEL = 'res://scenes/levels/zone01_mall.tscn'
    $taskScene = 'res://tools/loot_net_test.tscn'
} else {
    $env:COOP_POP_PEERS = [string]$Count
    $taskScene = 'res://tools/coop_population_test.tscn'
}
$taskChildren = @()
for ($taskIndex = 0; $taskIndex -lt $Count; $taskIndex++) {
    $taskRole = if ($taskIndex -eq 0) { 'host' } else { 'client' }
    $taskLabel = if ($taskIndex -eq 0) { 'host' } else { "client$taskIndex" }
    $taskPrefix = "tools/_probe/zone01_nw_${Mode}_$taskLabel"
    $env:APPDATA = Join-Path $taskRoot "tools/_probe/zone01_nw_${Mode}_${taskLabel}_appdata"
    $taskArgs = @('--path', $taskRoot, '--headless', $taskScene, '--log-file', "${taskPrefix}_engine.log", '--', $taskRole)
    $taskChild = Start-Process -FilePath $taskEngine -ArgumentList $taskArgs -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "${taskPrefix}.log" -RedirectStandardError "${taskPrefix}_err.log"
    $taskChildren += $taskChild
    Write-Output "$Mode $taskLabel PID=$($taskChild.Id)"
    if ($taskIndex -lt $Count - 1) { Start-Sleep -Seconds 3 }
}
$taskDeadline = (Get-Date).AddMinutes(4)
while ((@($taskChildren | Where-Object { -not $_.HasExited }).Count -gt 0) -and (Get-Date) -lt $taskDeadline) {
    $taskIds = @($taskChildren | Where-Object { -not $_.HasExited } | ForEach-Object { $_.Id })
    Wait-Process -Id $taskIds -Timeout 20 -ErrorAction SilentlyContinue
}
$taskFailed = $false
foreach ($taskChild in $taskChildren) {
    if (-not $taskChild.HasExited) {
        # Только процессы, созданные этим запуском; редактор и живую игру не трогаем.
        Stop-Process -Id $taskChild.Id
        Write-Output "$Mode TIMEOUT PID=$($taskChild.Id)"
        $taskFailed = $true
    } else {
        Write-Output "$Mode EXIT PID=$($taskChild.Id) CODE=$($taskChild.ExitCode)"
        if ($taskChild.ExitCode -ne 0) { $taskFailed = $true }
    }
}
if ($taskFailed) { exit 1 }

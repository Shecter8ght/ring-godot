$ErrorActionPreference='Stop'
$taskProject='E:\Games\RING-godot'
$taskWork=Join-Path $taskProject '_asset_src\grenade_codex\texture_v08'
$taskBlender='D:\ПРОГРАММЫ\Blender 5\blender.exe'
$taskPython='C:\Users\Schecter_8ght\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:OPTIX_CACHE_PATH=Join-Path $taskProject '_asset_src\grenade_codex\cache\optix'
$env:CUDA_CACHE_PATH=Join-Path $taskProject '_asset_src\grenade_codex\cache\cuda'
Set-Location -LiteralPath $taskProject
function Run-BlenderStage([string]$script,[string]$log,[string[]]$stageArgs) {
    Write-Host "Blender stage: $script $stageArgs"
    $stageLog=Join-Path $taskWork $log
    & $taskBlender --background --factory-startup --python-exit-code 1 --python $script -- @stageArgs *> $stageLog
    if ($LASTEXITCODE -ne 0) { Get-Content -LiteralPath $stageLog -Tail 30; throw "Blender stage failed: $script" }
}
function Run-PackageStage([string]$stage) {
    & $taskPython -X utf8 'tools\package_grenade_cast_v08.py' $stage
    if ($LASTEXITCODE -ne 0) { throw "Package stage failed: $stage" }
}
Run-BlenderStage 'tools\check_grenade_cast_v08.py' 'audit_full.log' @("$taskWork\Grenade_MkII_UCUPaint_v08.blend")
Run-BlenderStage 'tools\texture_grenade_cast_v08.py' 'render_full.log' @('render')
Run-BlenderStage 'tools\studio_grenade_cast_v08.py' 'studio_build.log' @('build')
Run-BlenderStage 'tools\studio_grenade_cast_v08.py' 'studio_render.log' @('render')
Run-BlenderStage 'tools\check_grenade_cast_v08.py' 'studio_audit.log' @("$taskWork\Grenade_MkII_Studio_v08.blend")
foreach ($stage in @('maps','previews','investor','supporting')) { Run-PackageStage $stage }
Write-Host "Completed in $taskWork. Final publication follows visual review."

@echo off
chcp 65001 >nul
rem ПМ, руки от первого лица: пересборка после правки хвата или поз владельцем.
rem   1) проверка файла хвата PM_FPS_Grip_v03.blend (зазоры, проникновения, суставы) -> PM_FPS_Grip_v03_check.json
rem   2) правая из хвата переносится в файл поз перезарядки PM_FPS_ReloadPoses_v01.blend (левая не трогается)
rem   3) клипы собираются заново -> PM_FPS_Clips_v02.blend (правая и стойки из хвата, левая по фазам из файла поз)
rem Запуск: tools\pm_grip_rebuild.cmd            (из папки проекта или двойным щелчком)
rem         tools\pm_grip_rebuild.cmd shots      — ещё и кадры поз в anim\Кадры_перезарядка_позы
setlocal
set BLENDER=D:\ПРОГРАММЫ\Blender 5\blender.exe
set ROOT=%~dp0..
set ANIM=%ROOT%\_asset_src\pm_game\anim
echo [1/3] проверка хвата
"%BLENDER%" --background --factory-startup --python-exit-code 1 --python "%ROOT%\tools\pm_grip_lock.py" -- check "%ANIM%\PM_FPS_Grip_v03.blend" | findstr /i "PM_LOCK Error Traceback"
if errorlevel 1 goto fail
echo [2/3] правая в файл поз
"%BLENDER%" --background --factory-startup --python-exit-code 1 --python "%ROOT%\tools\pm_grip_lock.py" -- poses_sync_right | findstr /i "PM_LOCK Error Traceback"
if errorlevel 1 goto fail
echo [3/3] клипы
"%BLENDER%" --background --factory-startup --python-exit-code 1 --python "%ROOT%\tools\pm_grip_lock.py" -- reload | findstr /i "PM_CLIPS Error Traceback"
if errorlevel 1 goto fail
if /i "%~1"=="shots" (
  echo [+] кадры поз
  "%BLENDER%" --background --factory-startup --python-exit-code 1 --python "%ROOT%\tools\pm_grip_lock.py" -- poses_stills | findstr /i "PM_STILLS Error Traceback"
)
echo Готово: %ANIM%\PM_FPS_Clips_v02.blend
goto end
:fail
echo ОШИБКА — см. вывод выше
:end
endlocal
pause

@echo off
chcp 65001 >nul
rem АСТЕН-919, клипы рук: пересборка после правки поз (хватов) владельцем в действии ASTEN919_Poses.
rem Читает позы из файла клипов, строит клипы заново (движение — из tools\asten919\clips\build_clips.py) и сохраняет
rem в тот же файл; прежний файл — рядом с приставкой «до_пересборки_».
setlocal
set BLENDER=D:\ПРОГРАММЫ\Blender 5\blender.exe
set ROOT=%~dp0..\..\..
set DIR=E:\Models Blender\WEAPONS\АСТЕН-919
set FILE=АСТЕН-919_руки_клипы_v01.blend
copy /y "%DIR%\%FILE%" "%DIR%\до_пересборки_%FILE%" >nul
"%BLENDER%" -b "%DIR%\%FILE%" --python-exit-code 1 --python "%ROOT%\tools\asten919\clips\build_clips.py" -- "%DIR%\%FILE%" | findstr /i "ASTEN_CLIPS Error Traceback"
if errorlevel 1 (echo ОШИБКА — см. вывод выше) else (echo Готово: %DIR%\%FILE%)
endlocal
pause

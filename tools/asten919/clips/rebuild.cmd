@echo off
chcp 65001 >nul
rem АСТЕН-919, клипы рук: пересборка после правки поз (хватов) владельцем — кадры 1–61, действие ASTEN919_Poses.
rem Читает позы из файла клипов, строит клипы заново (движение — из tools\asten919\clips\build_clips.py) и сохраняет
rem в тот же файл; прежний файл — рядом с приставкой «до_пересборки_». Перед запуском сохранить файл в Blender,
rem после — File → Revert. Свой файл: rebuild.cmd "<полный путь.blend>".
setlocal
set BLENDER=D:\ПРОГРАММЫ\Blender 5\blender.exe
set ROOT=%~dp0..\..\..
set DIR=E:\Models Blender\WEAPONS\АСТЕН-919
set FILE=АСТЕН-919_руки_клипы_v01.blend
if not "%~1"=="" (
  set DIR=%~dp1
  set FILE=%~nx1
)
if "%DIR:~-1%"=="\" set DIR=%DIR:~0,-1%
set LOG=%TEMP%\asten919_rebuild.log
copy /y "%DIR%\%FILE%" "%DIR%\до_пересборки_%FILE%" >nul
"%BLENDER%" -b "%DIR%\%FILE%" --python-exit-code 1 --python "%ROOT%\tools\asten919\clips\build_clips.py" -- "%DIR%\%FILE%" > "%LOG%" 2>&1
set CODE=%ERRORLEVEL%
findstr /i "ASTEN_CLIPS Error Traceback" "%LOG%"
if not "%CODE%"=="0" (
  echo.
  echo ОШИБКА: клипы не пересобраны, файл возвращён прежний. Полный вывод: %LOG%
  copy /y "%DIR%\до_пересборки_%FILE%" "%DIR%\%FILE%" >nul
) else (
  echo.
  echo Готово: %DIR%\%FILE%  — в Blender: File - Revert
)
endlocal
if "%~2"=="" pause

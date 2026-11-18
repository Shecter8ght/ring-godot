@echo off
chcp 65001 >nul
rem ВЕРАС-54, клипы рук: собрать ВСЕ клипы заново из таблиц build_clips.py. Ручные правки клипов пропадут
rem (позы — кадры 1–86 — остаются). Прежний файл — рядом, «до_пересборки_». Свой файл: regenerate.cmd "<путь.blend>".
setlocal
set BLENDER=D:\ПРОГРАММЫ\Blender 5\blender.exe
set ROOT=%~dp0..\..\..
set DIR=E:\Models Blender\WEAPONS\ВЕРАС-54 — модель и обвесы\ВЕРАС-54
set FILE=ВЕРАС-54_руки_клипы_v01.blend
if not "%~1"=="" (
  set DIR=%~dp1
  set FILE=%~nx1
)
if "%DIR:~-1%"=="\" set DIR=%DIR:~0,-1%
set LOG=%TEMP%\veras54_rebuild.log
if not "%~2"=="" goto run
echo Клипы будут собраны заново из таблиц. Ключи, поправленные в клипах руками, пропадут; позы останутся.
set /p OK=Напечатайте ДА и нажмите Enter, чтобы продолжить:
if /i not "%OK%"=="ДА" (
  echo Отменено.
  endlocal
  pause
  exit /b 0
)
:run
copy /y "%DIR%\%FILE%" "%DIR%\до_пересборки_%FILE%" >nul
"%BLENDER%" -b "%DIR%\%FILE%" --python-exit-code 1 --python "%ROOT%\tools\veras54_v14\clips\rebuild.py" -- "%DIR%\%FILE%" --regenerate > "%LOG%" 2>&1
set CODE=%ERRORLEVEL%
findstr /i "VERAS_CLIPS Error Traceback" "%LOG%"
if not "%CODE%"=="0" (
  echo.
  echo ОШИБКА: файл возвращён прежний. Полный вывод: %LOG%
  copy /y "%DIR%\до_пересборки_%FILE%" "%DIR%\%FILE%" >nul
) else (
  echo.
  echo Готово: %DIR%\%FILE%  — в Blender: File - Revert
)
endlocal
if "%~2"=="" pause

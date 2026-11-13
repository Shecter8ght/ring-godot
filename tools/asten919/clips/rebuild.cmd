@echo off
chcp 65001 >nul
rem АСТЕН-919, клипы рук. Обычно не нужен: позы в клипы переносит кнопка панели «АСТЕН» прямо в Blender.
rem На файле с клипами владельца делает то же, что эта кнопка (движение и ручные ключи клипов не трогает).
rem На файле прежнего устройства (клипы дорожкой NLA) один раз собирает клипы заново и ставит панель.
rem Перед запуском сохранить файл в Blender, после — File - Revert. Прежний файл — рядом, «до_пересборки_».
rem Свой файл: rebuild.cmd "<полный путь.blend>".
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
"%BLENDER%" -b "%DIR%\%FILE%" --python-exit-code 1 --python "%ROOT%\tools\asten919\clips\rebuild.py" -- "%DIR%\%FILE%"  > "%LOG%" 2>&1
set CODE=%ERRORLEVEL%
findstr /i "ASTEN_CLIPS Error Traceback" "%LOG%"
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

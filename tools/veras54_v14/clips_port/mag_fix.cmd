@echo off
chcp 65001 >nul
rem ВЕРАС-54, файл клипов v02 (автомат v14): путь магазина у шахты заново, старый магазин быстрой стоит в шахте до удара,
rem большой палец на защёлке (поза 91) — без вывернутых фаланг, панель «ВЕРАС» — новая (правка хвата не ломает путь магазина).
rem Трогает: ключи левой кисти и плеча на кадрах, где кисть держит магазин, в 15 перезарядках; старый магазин в быстрых
rem и уроненный в «выскользнул»; большой палец в позе 91 и на кадрах нажатия защёлки; версии собираются заново.
rem Перед запуском — сохранить файл в Blender (Ctrl+S), после — File - Revert. Прежний файл — рядом, «до_исправления_».
rem Свой файл: mag_fix.cmd "<полный путь.blend>".
setlocal
set BLENDER=D:\ПРОГРАММЫ\Blender 5\blender.exe
set ROOT=%~dp0..\..\..
set DIR=E:\Models Blender\WEAPONS\ВЕРАС-54 — модель и обвесы\ВЕРАС-54
set FILE=ВЕРАС-54_руки_клипы_v02.blend
if not "%~1"=="" (
  set DIR=%~dp1
  set FILE=%~nx1
)
if "%DIR:~-1%"=="\" set DIR=%DIR:~0,-1%
set LOG=%TEMP%\veras54_mag_fix.log
copy /y "%DIR%\%FILE%" "%DIR%\до_исправления_%FILE%" >nul
"%BLENDER%" -b "%DIR%\%FILE%" --factory-startup --python-exit-code 1 --python "%ROOT%\tools\veras54_v14\clips_port\mag_path_fix.py" -- "%DIR%\%FILE%"  > "%LOG%" 2>&1
set CODE=%ERRORLEVEL%
findstr /i "FIX Error Traceback" "%LOG%" | findstr /v /i "поправлено"
if not "%CODE%"=="0" (
  echo.
  echo ОШИБКА: файл возвращён прежний. Полный вывод: %LOG%
  copy /y "%DIR%\до_исправления_%FILE%" "%DIR%\%FILE%" >nul
) else (
  echo.
  echo Готово: %DIR%\%FILE%  — в Blender: File - Revert
)
endlocal
if "%~2"=="" pause

@echo off
chcp 65001 >nul
rem Substance 3D Designer с мостом Claude (tools/sd_bridge/claude_sd_bridge): задания *.py из папки заданий
rem выполняются в Designer (в задании есть sd, ctx, app, pkg_mgr), ответ — <имя>.out. Настройки Designer не меняются:
rem папку плагинов он берёт из переменной SBS_DESIGNER_PYTHON_PATH. Готовность — файл _bridge_ready.txt в папке заданий.
rem designer_open.cmd [папка заданий] — по умолчанию _asset_src\sd_jobs. Собранный граф (.sbs) дальше без окна:
rem   sbscooker.exe --inputs <граф.sbs> --output-path <папка>   (библиотека sbs:// находится сама)
rem   sbsrender.exe render --inputs <граф.sbsar> --output-path <папка> --set-value $outputsize@11,11
set "SD=D:\ПРОГРАММЫ\Substance designer\Adobe Substance 3D Designer"
set "SBS_DESIGNER_PYTHON_PATH=%~dp0."
set "SD_BRIDGE_DIR=%~1"
if "%SD_BRIDGE_DIR%"=="" set "SD_BRIDGE_DIR=%~dp0..\..\_asset_src\sd_jobs"
for %%I in ("%SD_BRIDGE_DIR%") do set "SD_BRIDGE_DIR=%%~fI"
if not exist "%SD_BRIDGE_DIR%" mkdir "%SD_BRIDGE_DIR%"
start "" "%SD%\Adobe Substance 3D Designer.exe"

@echo off
chcp 65001 >nul
rem ВСС-М v8: Substance Painter для ручной работы с проектами ВСС (docs/assets/vss_m_painter_manual_wear.md).
rem OCIO — то же цветовое управление, с которым созданы проекты: без него Painter открывает их с вопросом о цвете
rem и может перевести в старую схему. Мост sp_bridge — чтобы Claude мог по просьбе выгрузить карты и проверить слои.
rem painter_open.cmd [receiver | parts | путь к .spp] — сразу открыть проект (без аргумента — пустой Painter).
set "SP=D:\ПРОГРАММЫ\Substance Painter\Adobe Substance 3D Painter"
set "OCIO=%SP%\resources\ocio\substance\config.ocio"
set "SUBSTANCE_PAINTER_PLUGINS_PATH=%~dp0sp_bridge"
set "SP_BRIDGE_DIR=%~dp0..\..\_asset_src\vss_m_v8\sp_jobs"
set "PROJ=%~1"
if /i "%PROJ%"=="receiver" set "PROJ=%~dp0..\..\_asset_src\vss_m_v8\sp_receiver\receiver.spp"
if /i "%PROJ%"=="parts" set "PROJ=%~dp0..\..\_asset_src\vss_m_v8\sp_parts\parts.spp"
rem путь — полный, без «..»: с ним Painter открывает проект, но не находит сцену («Failed to load 3D scene») и висит
if not "%PROJ%"=="" for %%I in ("%PROJ%") do set "PROJ=%%~fI"
if "%PROJ%"=="" (
    start "" "%SP%\Adobe Substance 3D Painter.exe"
) else (
    start "" "%SP%\Adobe Substance 3D Painter.exe" "%PROJ%"
)

@echo off
chcp 65001 >nul
rem Цевьё по ролику Dolinskyi: Substance Painter с проектом Цевьё_Dolinskyi_v01.spp (стек как в ролике, слои «РУКАМИ»).
rem OCIO — то же цветовое управление, с которым создан проект: без него Painter открывает его с вопросом о цвете или
rem висит «busy». Неявные слои Vulkan (RivaTuner / MSI Afterburner, оверлеи Steam и Epic) выключены только для этого
rem Painter: 2026-11-01 с ними он падал в nvoglv64.dll на первом кадре 3D-вида. Мост sp_bridge — чтобы Claude мог по
rem просьбе выгрузить карты после ручных мазков.
set "SP=D:\ПРОГРАММЫ\Substance Painter\Adobe Substance 3D Painter"
set "OCIO=%SP%\resources\ocio\substance\config.ocio"
set "VK_LOADER_LAYERS_DISABLE=~implicit~"
set "DISABLE_RTSS_LAYER=1"
set "DISABLE_VK_LAYER_VALVE_steam_overlay_1=1"
set "DISABLE_VK_LAYER_VALVE_steam_fossilize_1=1"
set "DISABLE_EOS_OVERLAY=1"
set "SUBSTANCE_PAINTER_PLUGINS_PATH=%~dp0..\vss_m_v8\sp_bridge"
set "SP_BRIDGE_DIR=%~dp0..\..\_asset_src\handguard_dolinskyi\sp_jobs"
set "PROJ=E:\Models Blender\WEAPONS\Цевьё — Dolinskyi, анодирование 2026-11-01\Цевьё_Dolinskyi_v01.spp"
if not "%~1"=="" set "PROJ=%~1"
for %%I in ("%PROJ%") do set "PROJ=%%~fI"
start "" "%SP%\Adobe Substance 3D Painter.exe" "%PROJ%"

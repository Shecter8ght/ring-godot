@echo off
rem Painter для отделки опор касс v01: своя папка заданий, слои Vulkan оверлеев выключены;
rem временные файлы Painter — на E: (на C: мало места: Painter встаёт на окне «Configuration Issues / DISK SPACE»)
set VK_LOADER_LAYERS_DISABLE=~implicit~
set DISABLE_RTSS_LAYER=1
if not exist E:\RING_tmp_painter mkdir E:\RING_tmp_painter
set TEMP=E:\RING_tmp_painter
set TMP=E:\RING_tmp_painter
set FINISH_SP_JOBS=E:\Games\RING-godot\_asset_src\loot_containers\sp_jobs_counters
cd /d E:\Games\RING-godot
python -X utf8 tools\asset_kit\finish\sp_run.py start

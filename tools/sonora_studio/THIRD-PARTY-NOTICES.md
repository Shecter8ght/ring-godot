# Компоненты Sonora Studio

- Код Sonora Studio распространяется на условиях GNU GPL v3 или более поздней версии. Текст лицензии — `LICENSE.txt` в архиве исходников.
- Electron 45.0.0 — MIT. Исходники: https://github.com/electron/electron/tree/v45.0.0 . Лицензии Electron и Chromium сохраняются в поставке приложения (`LICENSE.electron.txt`, `LICENSES.chromium.html`).
- fflate 0.8.3 — MIT. Исходники и лицензия: https://github.com/101arrowz/fflate . Используется для хранения проектов без распаковки содержимого на диск.
- FFmpeg — сборка N-124714-g49a77d37be-20260531, собрана с GPL v3, libmp3lame и libvorbis. Оригинальная лицензия находится в `FFmpeg-LICENSE.txt`, конфигурация — в `FFmpeg-BUILD-CONFIGURATION.txt` рядом с программой. Исходники FFmpeg: https://github.com/FFmpeg/FFmpeg/commit/49a77d37be . Информация проекта и ссылки на сборки: https://ffmpeg.org/ . Бинарный файл взят из уже установленной на компьютере пользователя копии. Sonora вызывает его отдельным процессом только для локального чтения/кодирования аудио.
- Инструменты разработки: electron-builder (MIT), Playwright (Apache-2.0). Они не включены в код исполняемого приложения.

Изменение высоты и скорости использует фильтр `rubberband` встроенной сборки FFmpeg с `--enable-librubberband`. Rubber Band Library — GNU GPL, исходники и условия: https://breakfastquay.com/rubberband/ . Сохранение формант и независимые изменения высоты/скорости выполняются локально. Версия библиотеки внутри этой сборки отдельно не заявляется.

Sonora Studio не использует внешние изображения, шрифты, записанные звуки или сетевые службы. Демонстрационные звуки синтезируются локально из генераторов и шума.

# Universal Image Downloader

Загрузчик изображений с публичных HTML-страниц. Домен не зашит в коде: URL передаётся аргументом командной строки или задаётся в `config.py`. По умолчанию он переходит по внутренним ссылкам того же сайта.

## Установка

```powershell
python -m pip install -r requirements.txt
```

## Запуск

```powershell
python downloader_img.py https://example.com/gallery --max-pages 50 --max-depth 2 --max-images 200
python resize_img.py
```

Для Pinterest и других JavaScript-сайтов установите браузер Chromium. Для Pinterest режим браузера включается автоматически:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python downloader_img.py https://ru.pinterest.com/ --max-pages 1 --max-images 50
python downloader_img.py "https://ru.pinterest.com/search/pins/?q=ангел%20и%20дявол" --max-pages 1 --max-images 50
```

Все пути по умолчанию вычисляются относительно каталога проекта. Результат сохраняется в `downloads`, обработанные изображения — в `resized`.

Основные настройки находятся в `config.py`. Параметр `resize_max_side` задаёт максимальную сторону обработанного изображения в пикселях. Например, для разрешения до 2048 пикселей измените его на `2048`.

В `config.py` можно изменить `max_pages`, `max_depth`, `follow_links`, `max_images`, `max_file_size_mb` и задержку между запросами. Загрузчик ищет `img[src]`, `srcset`, `data-src`, `data-original`, OpenGraph/Twitter image и ссылки на изображения.

Сканируются только страницы того же домена, что и начальный URL. Страницы, где изображения появляются только после выполнения JavaScript, требуют браузерной автоматизации и не гарантируются обычным HTTP-загрузчиком.

Браузерный режим прокручивает страницу, чтобы подгрузить динамическую ленту. Он не обходит авторизацию, CAPTCHA или ограничения доступа. Если сайт требует вход, используйте только свой разрешённый сеанс и не передавайте проекту чужие cookies.

Используйте инструмент только для материалов, которые разрешено скачивать, и соблюдайте правила сайта.

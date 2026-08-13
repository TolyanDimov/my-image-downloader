"""Настройки проекта.

Все пути автоматически строятся относительно корня проекта, поэтому проект
можно переносить на другой компьютер или в другую папку.
"""

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    # Начальная страница сайта. Можно оставить пустой строкой и передавать URL
    # при запуске: python downloader_img.py https://example.com
    start_url: str = ""

    # Папка, куда сохраняются скачанные изображения.
    output_dir: Path = PROJECT_ROOT / "downloads"

    # Папка для изображений после уменьшения размера.
    resized_dir: Path = PROJECT_ROOT / "resized"

    # Максимальное время ожидания одного HTTP-запроса в секундах.
    timeout: int = 30

    # Пауза между запросами. Увеличьте значение для снижения нагрузки на сайт.
    delay: float = 0.25

    # Максимальное количество скачиваемых изображений.
    # 0 означает «без ограничения».
    max_images: int = 0

    # Максимальное количество HTML-страниц, которые будут обработаны.
    max_pages: int = 50

    # Максимальная глубина перехода по ссылкам от начальной страницы.
    # 0 — только начальная страница, 1 — ещё один уровень ссылок и т.д.
    max_depth: int = 2

    # Переходить ли по внутренним ссылкам сайта.
    follow_links: bool = True

    # Максимальный размер одного файла в мегабайтах.
    max_file_size_mb: int = 50

    # Максимальная сторона изображения после обработки resize_img.py, в пикселях.
    resize_max_side: int = 2024

    # Имя клиента, которое передаётся сайту в HTTP-заголовке User-Agent.
    user_agent: str = "UniversalImageDownloader/1.0"

    # Использовать браузер Playwright для сайтов с JavaScript, например Pinterest.
    use_browser: bool = False

    # Запускать браузер без окна. Для отладки можно поставить False.
    browser_headless: bool = True

    # Сколько раз прокручивать страницу в браузерном режиме.
    browser_scrolls: int = 8

    # Пауза после прокрутки браузерной страницы в миллисекундах.
    browser_scroll_delay_ms: int = 1200


CONFIG = Config()


def ensure_directories() -> None:
    CONFIG.output_dir.mkdir(parents=True, exist_ok=True)
    CONFIG.resized_dir.mkdir(parents=True, exist_ok=True)

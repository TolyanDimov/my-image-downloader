#!/usr/bin/env python3
"""Universal static-site image crawler and downloader.

The crawler starts at one HTTP(S) page, follows same-site HTML links up to
configured limits, extracts image URLs from every visited page, and downloads
unique images. It does not bypass authentication, CAPTCHA, robots restrictions,
or JavaScript-only content.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from config import CONFIG, ensure_directories


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".svg"}
PAGE_EXTENSIONS = IMAGE_EXTENSIONS | {".css", ".js", ".json", ".pdf", ".zip", ".mp4", ".mp3"}
SKIP_HINTS = ("logo", "icon", "sprite", "favicon", "captcha", "avatar", "banner")


def clean_name(value: str, fallback: str = "image") -> str:
    value = html.unescape(value).strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" ._")
    return value[:120].rstrip(" ._") or fallback


def normalize_url(raw: str, base_url: str) -> str:
    absolute = urljoin(base_url, html.unescape(raw.strip()))
    absolute, _ = urldefrag(absolute)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return ""
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", parsed.query, ""))


def same_origin(url: str, origin: str) -> bool:
    left, right = urlparse(url), urlparse(origin)
    return left.scheme == right.scheme and left.netloc == right.netloc


def looks_like_image(url: str) -> bool:
    path = urlparse(url).path.lower()
    return Path(path).suffix in IMAGE_EXTENSIONS or any(token in path for token in ("/image", "/img", "/photo", "/media", "/upload"))


def likely_html_page(url: str) -> bool:
    return Path(urlparse(url).path.lower()).suffix not in PAGE_EXTENSIONS


def extract_image_urls(soup: BeautifulSoup, page_url: str) -> list[str]:
    scores: dict[str, int] = {}

    def add(raw: str | None, score: int, *, image_context: bool = False) -> None:
        if not raw:
            return
        candidate = normalize_url(raw.split(",")[0].split()[0], page_url)
        if not candidate or (not image_context and not looks_like_image(candidate)):
            return
        lowered = candidate.lower()
        if any(hint in lowered for hint in SKIP_HINTS):
            score -= 80
        scores[candidate] = max(scores.get(candidate, -1000), score)

    for meta in soup.select("meta[property='og:image'], meta[name='twitter:image']"):
        add(meta.get("content"), 120, image_context=True)
    for link in soup.select("link[rel='image_src'], a[href]"):
        add(link.get("href"), 115 if link.name == "link" else 80, image_context=link.name == "link")
    for image in soup.select("img"):
        for attribute, score in (("data-original", 125), ("data-lazy-src", 120), ("data-src", 115), ("src", 100)):
            add(image.get(attribute), score, image_context=True)
        for item in image.get("srcset", "").split(","):
            add(item, 110, image_context=True)
    return [url for url, _ in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)]


def extract_page_links(soup: BeautifulSoup, page_url: str, origin: str) -> list[str]:
    links: set[str] = set()
    for anchor in soup.select("a[href]"):
        url = normalize_url(anchor.get("href", ""), page_url)
        if url and same_origin(url, origin) and likely_html_page(url):
            links.add(url)
    return sorted(links)


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": CONFIG.user_agent, "Accept-Language": "ru,en;q=0.8"})
    return session


def requires_browser(url: str) -> bool:
    """Определяет сайты, для которых обычного HTML-запроса недостаточно."""
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return hostname == "pinterest.com" or hostname.endswith(".pinterest.com")


def browser_crawl(start_url: str, max_pages: int, max_depth: int, follow_links: bool) -> tuple[list[str], list[str]]:
    """Обходит динамический сайт через Chromium и собирает URLs изображений."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Для браузерного режима установите зависимости: "
            "python -m pip install -r requirements.txt && "
            "python -m playwright install chromium"
        ) from error

    origin = start_url
    queue = deque([(start_url, 0)])
    visited: set[str] = set()
    pages: list[str] = []
    images: set[str] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=CONFIG.browser_headless)
        context = browser.new_context(
            user_agent=CONFIG.user_agent,
            locale="ru-RU",
            viewport={"width": 1440, "height": 1000},
        )
        page = context.new_page()
        try:
            while queue and len(pages) < max_pages:
                page_url, depth = queue.popleft()
                if page_url in visited:
                    continue
                visited.add(page_url)
                try:
                    page.goto(page_url, wait_until="domcontentloaded", timeout=CONFIG.timeout * 1000)
                    page.wait_for_timeout(1500)
                    for _ in range(max(0, CONFIG.browser_scrolls)):
                        page.mouse.wheel(0, 2200)
                        page.wait_for_timeout(max(100, CONFIG.browser_scroll_delay_ms))

                    rendered = page.content()
                    soup = BeautifulSoup(rendered, "html.parser")
                    pages.append(page_url)
                    images.update(extract_image_urls(soup, page_url))

                    # currentSrc содержит уже выбранный браузером URL из srcset.
                    for item in page.locator("img").all():
                        current_src = item.get_attribute("src") or item.get_attribute("data-src")
                        if current_src:
                            normalized = normalize_url(current_src, page_url)
                            if normalized and looks_like_image(normalized):
                                images.add(normalized)

                    print(f"Браузерная страница {len(pages)}/{max_pages}: {page_url} | изображений: {len(images)}")
                    if follow_links and depth < max_depth:
                        for anchor in page.locator("a[href]").all():
                            href = anchor.get_attribute("href") or ""
                            link = normalize_url(href, page_url)
                            if link and same_origin(link, origin) and likely_html_page(link) and link not in visited:
                                queue.append((link, depth + 1))
                except Exception as error:
                    print(f"Пропуск динамической страницы: {page_url} — {error}", file=sys.stderr)
        finally:
            context.close()
            browser.close()
    return pages, sorted(images)


def fetch(session: requests.Session, url: str, *, stream: bool = False) -> requests.Response:
    response = session.get(url, timeout=CONFIG.timeout, stream=stream)
    response.raise_for_status()
    return response


def crawl_site(session: requests.Session, start_url: str, max_pages: int, max_depth: int, follow_links: bool) -> tuple[list[str], list[str]]:
    origin = start_url
    queue = deque([(start_url, 0)])
    visited: set[str] = set()
    pages: list[str] = []
    images: set[str] = set()

    while queue and len(pages) < max_pages:
        page_url, depth = queue.popleft()
        if page_url in visited:
            continue
        visited.add(page_url)
        try:
            response = fetch(session, page_url)
            content_type = response.headers.get("content-type", "").lower()
            if content_type and "html" not in content_type:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            pages.append(page_url)
            found = extract_image_urls(soup, page_url)
            images.update(found)
            print(f"Страница {len(pages)}/{max_pages}: {page_url} | изображений: {len(images)}")
            if follow_links and depth < max_depth:
                for link in extract_page_links(soup, page_url, origin):
                    if link not in visited:
                        queue.append((link, depth + 1))
            time.sleep(CONFIG.delay)
        except requests.RequestException as error:
            print(f"Пропуск страницы: {page_url} — {error}", file=sys.stderr)
    return pages, sorted(images)


def filename_for(url: str, index: int, content_type: str) -> str:
    stem = clean_name(Path(urlparse(url).path).stem, f"image_{index:04d}")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(
        content_type.split(";", 1)[0].lower(), Path(urlparse(url).path).suffix.lower() or ".jpg"
    )
    return f"{stem}_{digest}{extension}"


def download_images(session: requests.Session, image_urls: list[str], output_dir: Path, max_images: int) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    if max_images > 0:
        image_urls = image_urls[:max_images]
    downloaded = 0
    limit = CONFIG.max_file_size_mb * 1024 * 1024
    print(f"К скачиванию изображений: {len(image_urls)}")
    for index, image_url in enumerate(image_urls, 1):
        temporary: Path | None = None
        try:
            response = fetch(session, image_url, stream=True)
            content_type = response.headers.get("content-type", "")
            if not content_type.lower().startswith("image/"):
                response.close()
                continue
            length = int(response.headers.get("content-length", "0") or 0)
            if length > limit:
                response.close()
                print(f"[{index}] пропуск: превышен лимит размера")
                continue
            target = output_dir / filename_for(image_url, index, content_type)
            if target.exists() and target.stat().st_size:
                response.close()
                print(f"[{index}] уже есть: {target.name}")
                continue
            temporary = target.with_suffix(target.suffix + ".part")
            size = 0
            with temporary.open("wb") as file:
                for chunk in response.iter_content(256 * 1024):
                    if chunk:
                        size += len(chunk)
                        if size > limit:
                            raise ValueError("file exceeds configured size limit")
                        file.write(chunk)
            response.close()
            temporary.replace(target)
            downloaded += 1
            print(f"[{index}] OK: {target.name}")
            time.sleep(CONFIG.delay)
        except Exception as error:
            print(f"[{index}] ошибка: {image_url} — {error}", file=sys.stderr)
            if temporary:
                temporary.unlink(missing_ok=True)
    return downloaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Обход сайта и скачивание изображений")
    parser.add_argument("url", nargs="?", default=CONFIG.start_url, help="Начальный URL")
    parser.add_argument("-o", "--output", type=Path, default=CONFIG.output_dir)
    parser.add_argument("-n", "--max-images", type=int, default=CONFIG.max_images)
    parser.add_argument("--max-pages", type=int, default=CONFIG.max_pages)
    parser.add_argument("--max-depth", type=int, default=CONFIG.max_depth)
    parser.add_argument("--no-follow", action="store_true", help="Не переходить по внутренним ссылкам")
    parser.add_argument("--browser", action="store_true", help="Использовать Chromium для JavaScript-сайтов")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.url or urlparse(args.url).scheme not in {"http", "https"}:
        print("Укажите URL: python downloader_img.py https://example.com", file=sys.stderr)
        return 2
    ensure_directories()
    session = create_session()
    try:
        # Pinterest автоматически запускается в браузерном режиме, потому что
        # поисковая лента и изображения появляются после выполнения JavaScript.
        use_browser = CONFIG.use_browser or args.browser or requires_browser(args.url)
        if use_browser:
            pages, images = browser_crawl(
                args.url,
                max(1, args.max_pages),
                max(0, args.max_depth),
                CONFIG.follow_links and not args.no_follow,
            )
        else:
            pages, images = crawl_site(
                session,
                args.url,
                max(1, args.max_pages),
                max(0, args.max_depth),
                CONFIG.follow_links and not args.no_follow,
            )
        count = download_images(session, images, args.output, args.max_images)
        print(f"Обработано страниц: {len(pages)}")
        print(f"Скачано новых изображений: {count}")
        print(f"Папка: {args.output.resolve()}")
        return 0
    except requests.RequestException as error:
        print(f"Ошибка сети: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Остановлено пользователем")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

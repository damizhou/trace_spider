from pathlib import Path

from scrapy import signals
from scrapy.exceptions import IgnoreRequest
from scrapy.http import HtmlResponse

from auto_spider import (
    CONFIG_MIN_REQUEST_INTERVAL_SECONDS,
    CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER,
    create_browser,
    fetch,
)


class ChromeCollectorDownloaderMiddleware:
    def __init__(self):
        self.browser = create_browser()

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_request(self, request, spider):
        last_error = None
        for attempt in range(1, CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER + 1):
            spider.crawl_state.wait_for_node_request_slot(
                spider.node_key,
                CONFIG_MIN_REQUEST_INTERVAL_SECONDS,
            )
            try:
                final_url, content_type, body = fetch(self.browser, request.url)
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise ValueError(f"非 HTML/XHTML 主文档: {final_url} ({content_type})")
                return HtmlResponse(
                    url=final_url,
                    body=body.encode("utf-8"),
                    encoding="utf-8",
                    request=request,
                )
            except (RuntimeError, ValueError) as exc:
                last_error = str(exc)
                if attempt < CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER:
                    print(
                        f"[{spider.domain}] URL 请求失败，将重试 "
                        f"{attempt + 1}/{CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER}: "
                        f"{request.url}；{last_error}",
                        flush=True,
                    )

        self._record_homepage_failure(request, spider, last_error)
        raise IgnoreRequest(
            f"{request.url} 在当前容器中连续 "
            f"{CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER} 次请求失败: {last_error}"
        )

    @staticmethod
    def _record_homepage_failure(request, spider, message):
        if not request.meta.get("homepage_candidate", False):
            return
        with Path(spider.homepage_failure_path).open("a", encoding="utf-8") as file:
            file.write(f"{request.url}: {message}\n")

    def spider_closed(self, spider, reason):
        self.browser.quit()

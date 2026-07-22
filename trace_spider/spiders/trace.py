from pathlib import Path

import scrapy

from auto_spider import AtomicCsvUrlState, normalize_domain, normalize_page_url


class TraceSpider(scrapy.Spider):
    name = "trace"

    def __init__(
        self,
        domain=None,
        output_path=None,
        node_key=None,
        claim_limit=None,
        homepage_failure_path=None,
        max_urls=1000,
        max_candidates=10000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if (
            not domain
            or not output_path
            or not node_key
            or claim_limit is None
            or not homepage_failure_path
        ):
            raise ValueError(
                "trace Spider 缺少 domain、output_path、node_key、claim_limit "
                "或 homepage_failure_path"
            )

        self.domain = normalize_domain(domain)
        self.allowed_domains = [self.domain]
        self.output_path = output_path
        self.node_key = node_key
        self.claim_limit = int(claim_limit)
        self.homepage_failure_path = homepage_failure_path
        self.max_urls = int(max_urls)
        self.max_candidates = int(max_candidates)
        self.exclude_keywords = self._load_exclude_keywords()
        self.crawl_state = AtomicCsvUrlState(
            self.output_path,
            self.domain,
            max_urls=self.max_urls,
        )
        self.crawl_state.remove_candidates_matching(self.exclude_keywords)
        self.collected_urls = set(self.crawl_state.urls())
        self.scheduled_urls = set()
        self.homepage_url = self.crawl_state.homepage_url

    @staticmethod
    def _load_exclude_keywords():
        path = Path("exclude_keywords")
        if not path.is_file():
            return ()
        return tuple(
            keyword.strip()
            for keyword in path.read_text(encoding="utf-8").splitlines()
            if keyword.strip()
        )

    def _build_request(self, url, homepage_candidate=False, priority=0, claimed=False):
        normalized_url = normalize_page_url(url, url, self.domain)
        if not normalized_url or normalized_url in self.scheduled_urls:
            return None
        if any(keyword in normalized_url for keyword in self.exclude_keywords):
            return None
        if not claimed and not self.crawl_state.ensure_and_claim_candidate(
            normalized_url, max_total=min(self.max_urls, self.max_candidates)
        ):
            return None
        self.collected_urls.add(normalized_url)
        self.scheduled_urls.add(normalized_url)
        return scrapy.Request(
            normalized_url,
            callback=self.parse,
            meta={"homepage_candidate": homepage_candidate},
            priority=priority,
        )

    def start_requests(self):
        if self.crawl_state.unrequested_count() == 0:
            return

        for url in self.crawl_state.claim_unrequested(self.claim_limit):
            is_homepage = url == self.homepage_url
            request = self._build_request(
                url,
                homepage_candidate=is_homepage,
                priority=1_000_000 if is_homepage else 0,
                claimed=True,
            )
            if request:
                yield request

    def parse(self, response, **kwargs):
        page_url = normalize_page_url(response.url, response.url, self.domain)
        if not page_url:
            return []

        request_url = normalize_page_url(response.request.url, response.request.url, self.domain)
        if not request_url:
            return []

        results = []
        for raw_link in response.css("a::attr(href)").getall():
            full_url = response.urljoin(raw_link)
            request = self._build_request(full_url)
            if request:
                results.append(request)

        return results

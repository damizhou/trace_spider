import csv
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


CONFIG_DOMAINS = (
    'rajwap.cc',
    'nhentai.net',
    'uk.com',
    'uiuc.edu',
    'lwsdns.com',
    'e-volution.ai',
    'tradingview.com',
    'mit.edu',
    'dhl.com',
    'fuq.com',
    'arbada.com',
    'mobile-tracker-free.com',
    'vmware.com',
    'nic.do',
    'watchguard.com',
    'flashtalking.com',
    'goal.co',
    'networkadvertising.org',
    'kompoz2.com',
    'gamewith.jp',
    'smartthings.com',
    'irs.gov',
    'porn300.com',
    'rainberrytv.com',
    'dyndns.org',
    'ip-api.com',
    'screenrant.com',
    'ixxx.com',
    'infonline.de',
    'launchpad.net',
    'dan.com',
    'ico.org.uk',
    'qorno.com',
    'getbootstrap.com',
    'ilovepdf.com',
    'supercell.com',
    'b-cdn.net',
    'psiphon.news',
    'meraki.com',
    'sexemodel.com',
    'tplinkcloud.com',
    'worldbank.org',
    'afternic.com',
    'moengage.com',
    'sexvid.pro',
    'abc.net.au',
    'getpocket.com',
    'sinsay.com',
    'kaspi.kz',
    'applovin.com'
)
CONFIG_URLS_PER_DOMAIN = 1000
CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN = 1000
CONFIG_MAX_CANDIDATES_PER_DOMAIN = 10000
# 避免同一节点的出口 IP 因页面请求过密触发风控。
CONFIG_MIN_REQUEST_INTERVAL_SECONDS = 120
CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER = 1
CONFIG_DOMAIN_OUTPUT_DIR = Path("domain_url_results")
CONFIG_RESULT_CSV_DIR = Path("result_csv")
CONFIG_RESULT_CSV_MIN_ROWS_EXCLUSIVE = 10
CONFIG_DOCKER_IMAGE = "chuanzhoupan/trace_spider:250912"
CONFIG_DOCKER_NETWORK_NAME = "trace_spider"
CONFIG_DOCKER_NETWORK_SUBNET = "172.20.0.0/24"
CONFIG_DOCKER_NETWORK_GATEWAY = "172.20.0.1"
CONFIG_RETRIES_PER_SOURCE_IP = 1
CONFIG_SOURCE_IPS = tuple(f"172.20.0.{host}" for host in range(2, 192))
CONFIG_DISTINCT_NODE_COUNT = 19
CONFIG_REQUEST_TIMEOUT_SECONDS = 20
CONFIG_SOURCE_IP_ATTEMPT_TIMEOUT_SECONDS = (
    CONFIG_MAX_CANDIDATES_PER_DOMAIN
    * CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER
    * CONFIG_MIN_REQUEST_INTERVAL_SECONDS
    + CONFIG_REQUEST_TIMEOUT_SECONDS
)
CONFIG_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
CONFIG_CHROME_BINARY_PATH = "/usr/bin/google-chrome"
CONFIG_CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"
CONFIG_CONTAINER_WORKER_HOME = "/tmp/url_crawler_home"
CONFIG_CONTAINER_WORKER_TMPDIR = "/tmp/url_crawler_tmp"
CONFIG_SCRAPY_SPIDER_NAME = "trace"
CSV_FIELDNAMES = ("id", "url", "domain", "requested")
LEGACY_CSV_FIELDNAMES = ("id", "url", "domain")
CSV_REQUESTED_NO = "0"
CSV_REQUESTED_YES = "1"

WORKER_FLAG_ENV = "URL_CRAWLER_WORKER"
WORKER_DOMAIN_ENV = "URL_CRAWLER_DOMAIN"
WORKER_OUTPUT_ENV = "URL_CRAWLER_OUTPUT"
WORKER_NODE_KEY_ENV = "URL_CRAWLER_NODE_KEY"
WORKER_CLAIM_LIMIT_ENV = "URL_CRAWLER_CLAIM_LIMIT"
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_NAMES = {"fbclid", "gclid", "mc_cid", "mc_eid"}
PAGE_SUFFIXES_TO_SKIP = {
    ".7z", ".apk", ".atom", ".avi", ".azw", ".azw3", ".bin", ".bz2",
    ".css", ".csv", ".db", ".deb", ".dmg", ".doc", ".docx", ".epub",
    ".exe", ".gif", ".gz", ".ico", ".ics", ".iso", ".jpeg", ".jpg",
    ".js", ".json", ".m4a", ".mkv", ".mobi", ".mov", ".mp3", ".mp4",
    ".mpeg", ".mpg", ".msi", ".odp", ".ods", ".odt", ".pdf", ".pkg",
    ".png", ".ppt", ".pptx", ".ps", ".rar", ".rpm", ".rss", ".rtf",
    ".sql", ".sqlite", ".svg", ".tar", ".tgz", ".tif", ".tiff",
    ".torrent", ".tsv", ".txt", ".vcf", ".wav", ".webm", ".webp",
    ".woff", ".woff2", ".xls", ".xlsx", ".xml", ".yaml", ".yml", ".zip",
}


def log(message, *, file=None):
    output = file if file is not None else sys.stdout
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", file=output, flush=True)


def normalize_domain(domain):
    value = domain.strip().lower().rstrip(".")
    if "://" in value:
        value = (urlsplit(value).hostname or "").lower().rstrip(".")
    if not value or "." not in value or not re.fullmatch(r"[a-z0-9.-]+", value):
        raise ValueError(f"无效域名: {domain!r}")
    return value


def unique_domains(domains):
    return list(dict.fromkeys(normalize_domain(domain) for domain in domains))


def homepage_url_for_domain(domain):
    return f"https://{normalize_domain(domain)}/"


def is_related_host(hostname, domain):
    host = (hostname or "").lower().rstrip(".")
    return host == domain or host.endswith(f".{domain}")


def normalize_page_url(raw_url, base_url, domain):
    absolute_url = urljoin(base_url, raw_url.strip())
    parts = urlsplit(absolute_url)
    if parts.scheme.lower() not in {"http", "https"} or not is_related_host(parts.hostname, domain):
        return None

    path = re.sub(r"/{2,}", "/", parts.path or "/")
    suffix_path = path.rstrip("/").lower()
    if any(suffix_path.endswith(suffix) for suffix in PAGE_SUFFIXES_TO_SKIP):
        return None

    query_items = [
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if name.lower() not in TRACKING_QUERY_NAMES
        and not name.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    hostname = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    return urlunsplit((parts.scheme.lower(), hostname, path, urlencode(query_items, doseq=True), ""))


def create_browser():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    os.environ["SE_OFFLINE"] = "true"
    chrome_options = Options()
    chrome_options.binary_location = CONFIG_CHROME_BINARY_PATH
    for argument in (
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--incognito",
        "--disable-application-cache",
        "--disable-background-networking",
        "--disable-extensions",
        "--disable-sync",
        "--no-first-run",
        "--no-default-browser-check",
        "--homepage=about:blank",
    ):
        chrome_options.add_argument(argument)
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    service = Service(executable_path=CONFIG_CHROMEDRIVER_PATH)
    browser = webdriver.Chrome(service=service, options=chrome_options)
    browser.set_page_load_timeout(CONFIG_REQUEST_TIMEOUT_SECONDS)
    browser.execute_cdp_cmd("Network.enable", {})
    return browser


def _normalize_log_url(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _get_document_response(browser, final_url):
    document_responses = []
    for entry in browser.get_log("performance"):
        try:
            message = json.loads(entry["message"])["message"]
        except (KeyError, TypeError, ValueError):
            continue
        if message.get("method") != "Network.responseReceived":
            continue
        params = message.get("params", {})
        if params.get("type") != "Document":
            continue
        document_responses.append(params.get("response", {}))

    normalized_final_url = _normalize_log_url(final_url)
    matching_responses = [
        response
        for response in document_responses
        if _normalize_log_url(response.get("url", "")) == normalized_final_url
    ]
    if matching_responses:
        return matching_responses[-1]
    if document_responses:
        return document_responses[-1]
    raise RuntimeError(f"Chrome 性能日志中没有主文档响应: {final_url}")


def _read_browser_document(browser, content_type):
    if content_type == "text/plain":
        return browser.execute_script("return document.body ? document.body.innerText : '';")
    if content_type.endswith("/xml") or content_type.endswith("+xml"):
        return browser.execute_script("return new XMLSerializer().serializeToString(document);")
    return browser.page_source


def fetch(browser, url):
    from selenium.common.exceptions import TimeoutException, WebDriverException

    browser.get_log("performance")
    try:
        browser.get(url)
    except TimeoutException:
        browser.execute_script("window.stop();")
    except WebDriverException as exc:
        raise RuntimeError(f"Chrome 访问失败 {url}: {exc}") from exc

    final_url = browser.current_url
    response = _get_document_response(browser, final_url)
    try:
        status_code = int(response.get("status"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Chrome 未返回有效 HTTP 状态码: {final_url}") from exc
    if not 200 <= status_code < 400:
        raise RuntimeError(f"HTTP {status_code}: {final_url}")

    content_type = str(response.get("mimeType", "")).split(";", 1)[0].strip().lower()
    if not content_type:
        content_type = str(browser.execute_script("return document.contentType || ''; ")).lower()
    body = _read_browser_document(browser, content_type)
    if not isinstance(body, str):
        raise RuntimeError(f"Chrome 未返回可读文档内容: {final_url}")
    if len(body.encode("utf-8")) > CONFIG_MAX_RESPONSE_BYTES:
        raise ValueError(f"响应超过 {CONFIG_MAX_RESPONSE_BYTES} 字节限制: {final_url}")
    return final_url, content_type, body


class AtomicCsvUrlState:
    def __init__(self, path, domain, max_urls=CONFIG_URLS_PER_DOMAIN):
        self.path = Path(path)
        self.domain = normalize_domain(domain)
        self.homepage_url = homepage_url_for_domain(self.domain)
        self.max_urls = int(max_urls)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._mutate(lambda rows: rows)

    @property
    def lock_path(self):
        return self.path.with_suffix(f"{self.path.suffix}.lock")

    @staticmethod
    def _normalize_requested(value):
        normalized = str(value or "").strip().lower()
        if normalized in {"", "0", "false", "no"}:
            return CSV_REQUESTED_NO
        if normalized in {"1", "true", "yes"}:
            return CSV_REQUESTED_YES
        raise ValueError(f"CSV requested 字段无效: {value!r}")

    def _read_rows_unlocked(self):
        rows_by_url = {}
        ordered_urls = []
        if self.path.is_file() and self.path.stat().st_size > 0:
            with self.path.open("r", newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                fieldnames = tuple(reader.fieldnames or ())
                if fieldnames not in {CSV_FIELDNAMES, LEGACY_CSV_FIELDNAMES}:
                    raise ValueError(f"CSV 表头不正确: {self.path}，实际为 {fieldnames}")
                for row in reader:
                    raw_url = row["url"].strip()
                    url = normalize_page_url(raw_url, raw_url, self.domain) if raw_url else None
                    if not url:
                        continue
                    requested = self._normalize_requested(row.get("requested", CSV_REQUESTED_NO))
                    if url not in rows_by_url:
                        rows_by_url[url] = {"url": url, "requested": requested}
                        ordered_urls.append(url)
                    elif requested == CSV_REQUESTED_YES:
                        rows_by_url[url]["requested"] = CSV_REQUESTED_YES

        homepage_row = rows_by_url.get(
            self.homepage_url,
            {"url": self.homepage_url, "requested": CSV_REQUESTED_NO},
        )
        rows = [homepage_row]
        rows.extend(
            rows_by_url[url]
            for url in ordered_urls
            if url != self.homepage_url
        )
        return rows[:self.max_urls]

    def _write_rows_unlocked(self, rows):
        temporary_path = self.path.with_name(
            f"{self.path.name}.{os.getpid()}.{time.time_ns()}.tmp"
        )
        try:
            with temporary_path.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()
                for row_id, row in enumerate(rows[:self.max_urls], start=1):
                    writer.writerow(
                        {
                            "id": row_id,
                            "url": row["url"],
                            "domain": self.domain,
                            "requested": row["requested"],
                        }
                    )
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _mutate(self, callback):
        with self.lock_path.open("a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            rows = self._read_rows_unlocked()
            result = callback(rows)
            self._write_rows_unlocked(rows)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return result

    def _read(self, callback):
        with self.lock_path.open("a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)
            rows = self._read_rows_unlocked()
            result = callback(rows)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return result

    def urls(self):
        return self._read(lambda rows: [row["url"] for row in rows])

    def count(self):
        return self._read(len)

    def unrequested_count(self):
        return self._read(
            lambda rows: sum(row["requested"] == CSV_REQUESTED_NO for row in rows)
        )

    def requested_count(self):
        return self._read(
            lambda rows: sum(row["requested"] == CSV_REQUESTED_YES for row in rows)
        )

    def homepage_requested(self):
        return self._read(
            lambda rows: bool(rows) and rows[0]["requested"] == CSV_REQUESTED_YES
        )

    def remove_candidates_matching(self, keywords):
        normalized_keywords = tuple(keyword for keyword in keywords if keyword)
        if not normalized_keywords:
            return 0

        def remove(rows):
            kept = [rows[0]]
            kept.extend(
                row
                for row in rows[1:]
                if not any(keyword in row["url"] for keyword in normalized_keywords)
            )
            removed_count = len(rows) - len(kept)
            rows[:] = kept
            return removed_count

        return self._mutate(remove)

    def claim_unrequested(self, limit):
        if limit < 1:
            return []

        def claim(rows):
            claimed = []
            for row in rows:
                if row["requested"] != CSV_REQUESTED_NO:
                    continue
                row["requested"] = CSV_REQUESTED_YES
                claimed.append(row["url"])
                if len(claimed) >= limit:
                    break
            return claimed

        return self._mutate(claim)

    def ensure_and_claim_candidate(self, url, max_total=None):
        normalized_url = normalize_page_url(url, url, self.domain)
        if not normalized_url:
            return False

        def ensure_and_claim(rows):
            for row in rows:
                if row["url"] != normalized_url:
                    continue
                if row["requested"] == CSV_REQUESTED_YES:
                    return False
                row["requested"] = CSV_REQUESTED_YES
                return True
            limit = self.max_urls if max_total is None else min(self.max_urls, max_total)
            if len(rows) >= limit:
                return False
            rows.append({"url": normalized_url, "requested": CSV_REQUESTED_YES})
            return True

        return self._mutate(ensure_and_claim)

    def wait_for_node_request_slot(self, node_key, minimum_interval_seconds):
        # 串行化同一节点的请求启动时间，保护该节点对应的出口 IP。
        safe_node_key = re.sub(r"[^a-z0-9_-]+", "_", node_key.lower())
        timestamp_path = self.path.with_suffix(
            f"{self.path.suffix}.{safe_node_key}.request_time"
        )
        while True:
            with timestamp_path.open("a+", encoding="utf-8") as file:
                fcntl.flock(file.fileno(), fcntl.LOCK_EX)
                file.seek(0)
                value = file.read().strip()
                last_started_at = float(value) if value else None
                now = time.time()
                remaining = (
                    minimum_interval_seconds - (now - last_started_at)
                    if last_started_at is not None
                    else 0
                )
                if remaining <= 0:
                    file.seek(0)
                    file.truncate()
                    file.write(str(now))
                    file.flush()
                    os.fsync(file.fileno())
                    fcntl.flock(file.fileno(), fcntl.LOCK_UN)
                    return
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
            time.sleep(remaining)


def run_worker():
    Path(CONFIG_CONTAINER_WORKER_HOME).mkdir(parents=True, exist_ok=True)
    Path(CONFIG_CONTAINER_WORKER_TMPDIR).mkdir(parents=True, exist_ok=True)
    domain = normalize_domain(os.environ[WORKER_DOMAIN_ENV])
    output_path = Path(os.environ[WORKER_OUTPUT_ENV])
    node_key = os.environ[WORKER_NODE_KEY_ENV]
    claim_limit = int(os.environ[WORKER_CLAIM_LIMIT_ENV])
    crawl_state = AtomicCsvUrlState(output_path, domain)
    starting_requested_count = crawl_state.requested_count()
    domain_digest = hashlib.sha1(domain.encode("utf-8")).hexdigest()[:8]
    homepage_failure_path = Path(f"/tmp/url_spider_{domain_digest}.homepage_failure")
    homepage_failure_path.unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "scrapy",
        "crawl",
        CONFIG_SCRAPY_SPIDER_NAME,
        "-a",
        f"domain={domain}",
        "-a",
        f"output_path={output_path}",
        "-a",
        f"node_key={node_key}",
        "-a",
        f"claim_limit={claim_limit}",
        "-a",
        f"homepage_failure_path={homepage_failure_path}",
        "-a",
        f"max_urls={CONFIG_URLS_PER_DOMAIN}",
        "-a",
        f"max_candidates={CONFIG_MAX_CANDIDATES_PER_DOMAIN}",
    ]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parent, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{domain} trace_spider 执行失败，退出码 {result.returncode}")
    ending_requested_count = crawl_state.requested_count()
    log(
        f"[{domain}] Worker 完成，CSV {crawl_state.count()} 条，"
        f"本次新增 requested {ending_requested_count - starting_requested_count} 条，"
        f"剩余未请求 {crawl_state.unrequested_count()} 条"
    )


def container_name(domain, suffix=None):
    slug = re.sub(r"[^a-z0-9]+", "_", domain).strip("_")[:40]
    digest = hashlib.sha1(domain.encode("utf-8")).hexdigest()[:8]
    name = f"url_spider_{slug}_{digest}"
    if suffix:
        suffix_slug = re.sub(r"[^a-z0-9]+", "_", str(suffix).lower()).strip("_")[:20]
        name = f"{name}_{suffix_slug}"
    return name


def remove_stale_container(name):
    inspect_result = subprocess.run(
        ["docker", "container", "inspect", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if inspect_result.returncode == 0:
        subprocess.run(["docker", "rm", "-f", name], check=True)


def remove_container(name):
    subprocess.run(
        ["docker", "rm", "-f", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def terminate_process(process):
    if process.poll() is not None:
        return
    try:
        process.kill()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def cleanup_domain_attempt(process, name):
    terminate_process(process)
    remove_container(name)


def cleanup_running_attempts(running):
    for _, process, name, _, _, _ in running:
        cleanup_domain_attempt(process, name)


def ensure_docker_network():
    inspect_result = subprocess.run(
        ["docker", "network", "inspect", CONFIG_DOCKER_NETWORK_NAME, "--format", "{{json .IPAM.Config}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if inspect_result.returncode != 0:
        subprocess.run(
            [
                "docker", "network", "create",
                "--driver", "bridge",
                "--subnet", CONFIG_DOCKER_NETWORK_SUBNET,
                "--gateway", CONFIG_DOCKER_NETWORK_GATEWAY,
                CONFIG_DOCKER_NETWORK_NAME,
            ],
            check=True,
        )
        log(
            f"已创建 Docker 网络 {CONFIG_DOCKER_NETWORK_NAME}: "
            f"{CONFIG_DOCKER_NETWORK_SUBNET}，网关 {CONFIG_DOCKER_NETWORK_GATEWAY}"
        )
        return

    ipam_configs = json.loads(inspect_result.stdout)
    expected_subnet = str(ipaddress.ip_network(CONFIG_DOCKER_NETWORK_SUBNET, strict=True))
    expected_gateway = str(ipaddress.ip_address(CONFIG_DOCKER_NETWORK_GATEWAY))
    if not any(
        config.get("Subnet") == expected_subnet and config.get("Gateway") == expected_gateway
        for config in ipam_configs
    ):
        raise RuntimeError(
            f"Docker 网络 {CONFIG_DOCKER_NETWORK_NAME} 已存在，但不是要求的 "
            f"{expected_subnet} / {expected_gateway}"
        )


def validate_source_ips():
    network = ipaddress.ip_network(CONFIG_DOCKER_NETWORK_SUBNET, strict=True)
    gateway = ipaddress.ip_address(CONFIG_DOCKER_NETWORK_GATEWAY)
    source_ips = [ipaddress.ip_address(source_ip) for source_ip in CONFIG_SOURCE_IPS]
    if len(source_ips) != len(set(source_ips)):
        raise ValueError("CONFIG_SOURCE_IPS 中存在重复源 IP")
    for source_ip in CONFIG_SOURCE_IPS:
        ip = ipaddress.ip_address(source_ip)
        if ip not in network or ip in {network.network_address, network.broadcast_address, gateway}:
            raise ValueError(f"源 IP 不可用: {source_ip}")
    if CONFIG_RETRIES_PER_SOURCE_IP < 1:
        raise ValueError("CONFIG_RETRIES_PER_SOURCE_IP 必须至少为 1")
    if CONFIG_DISTINCT_NODE_COUNT < 1:
        raise ValueError("CONFIG_DISTINCT_NODE_COUNT 必须至少为 1")
    if len(CONFIG_SOURCE_IPS) < CONFIG_DISTINCT_NODE_COUNT:
        raise ValueError("CONFIG_SOURCE_IPS 数量少于需要遍历的节点数量")
    if len(CONFIG_SOURCE_IPS) % CONFIG_DISTINCT_NODE_COUNT != 0:
        raise ValueError("CONFIG_SOURCE_IPS 数量必须是 CONFIG_DISTINCT_NODE_COUNT 的整数倍")


def build_initial_source_ips(domain_count):
    validate_source_ips()
    if domain_count > len(CONFIG_SOURCE_IPS):
        raise ValueError(
            f"域名数量 {domain_count} 超过可用源 IP 数量 {len(CONFIG_SOURCE_IPS)}"
        )
    return list(CONFIG_SOURCE_IPS[:domain_count])


def build_retry_node_source_ip_candidates(initial_source_ip_index):
    source_ip_count = len(CONFIG_SOURCE_IPS)
    candidates_per_node = source_ip_count // CONFIG_DISTINCT_NODE_COUNT
    node_candidates = []
    for node_offset in range(CONFIG_DISTINCT_NODE_COUNT):
        preferred_index = (initial_source_ip_index + node_offset) % source_ip_count
        candidates = tuple(
            CONFIG_SOURCE_IPS[
                (preferred_index + cycle * CONFIG_DISTINCT_NODE_COUNT) % source_ip_count
            ]
            for cycle in range(candidates_per_node)
        )
        node_candidates.append(candidates)
    return node_candidates


def get_occupied_source_ips():
    inspect_result = subprocess.run(
        [
            "docker", "network", "inspect", CONFIG_DOCKER_NETWORK_NAME,
            "--format", "{{json .Containers}}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    container_configs = json.loads(inspect_result.stdout)
    occupied_source_ips = set()
    for container_config in (container_configs or {}).values():
        address = container_config.get("IPv4Address")
        if address:
            occupied_source_ips.add(str(ipaddress.ip_interface(address).ip))
    return occupied_source_ips


def select_available_source_ip(candidates):
    occupied_source_ips = get_occupied_source_ips()
    skipped_source_ips = []
    for source_ip in candidates:
        if source_ip in occupied_source_ips:
            skipped_source_ips.append(source_ip)
            continue
        return source_ip, tuple(skipped_source_ips)
    return None, tuple(candidates)


def source_ip_node_key(source_ip):
    try:
        source_ip_index = CONFIG_SOURCE_IPS.index(source_ip)
    except ValueError as exc:
        raise ValueError(f"源 IP 不在 CONFIG_SOURCE_IPS 中: {source_ip}") from exc
    return f"node_{source_ip_index % CONFIG_DISTINCT_NODE_COUNT:02d}"


def start_domain_container(
    domain,
    container_ip,
    node_key,
    claim_limit,
    attempt,
    project_dir,
    output_dir,
    name_suffix=None,
):
    name = container_name(domain, name_suffix)
    remove_stale_container(name)
    container_output = f"/output/{domain}.csv"
    create_command = [
        "docker", "run", "--init", "--privileged", "--interactive", "--tty", "--detach", "--name", name,
        "--network", CONFIG_DOCKER_NETWORK_NAME,
        "--ip", container_ip,
        "--volume", f"{project_dir}:/app:ro",
        "--volume", f"{output_dir}:/output",
        CONFIG_DOCKER_IMAGE,
        "/bin/bash",
    ]
    log(
        f"[{domain}] 启动容器 {name}，源 IP {container_ip}，"
        f"第 {attempt}/{CONFIG_RETRIES_PER_SOURCE_IP} 次"
    )
    try:
        subprocess.run(create_command, check=True)
        worker_command = [
            "docker", "exec",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--env", f"HOME={CONFIG_CONTAINER_WORKER_HOME}",
            "--env", f"TMPDIR={CONFIG_CONTAINER_WORKER_TMPDIR}",
            "--env", f"{WORKER_FLAG_ENV}=1",
            "--env", f"{WORKER_DOMAIN_ENV}={domain}",
            "--env", f"{WORKER_OUTPUT_ENV}={container_output}",
            "--env", f"{WORKER_NODE_KEY_ENV}={node_key}",
            "--env", f"{WORKER_CLAIM_LIMIT_ENV}={claim_limit}",
            name, "python", "/app/auto_spider.py",
        ]
        output_path = output_dir / f"{domain}.csv"
        starting_requested_count = AtomicCsvUrlState(output_path, domain).requested_count()
        process = subprocess.Popen(worker_command)
        return process, output_path, name, starting_requested_count, time.monotonic()
    except BaseException:
        remove_container(name)
        raise


def csv_data_row_count(path):
    if not path.is_file() or path.stat().st_size == 0:
        return 0
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return sum(1 for _ in csv.DictReader(file))


def select_domains_requiring_collection(domains, output_dir):
    maximum_collectible_urls = min(
        CONFIG_URLS_PER_DOMAIN,
        CONFIG_MAX_CANDIDATES_PER_DOMAIN,
    )
    if CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN < 1:
        raise ValueError("CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN 不能小于 1")
    if CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN > maximum_collectible_urls:
        raise ValueError(
            "CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN 不能大于当前 URL 采集上限 "
            f"{maximum_collectible_urls}"
        )

    selected_domains = []
    skipped_domains = []
    for domain in domains:
        output_path = output_dir / f"{domain}.csv"
        crawl_state = AtomicCsvUrlState(output_path, domain)
        unique_url_count = crawl_state.count()
        if unique_url_count >= CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN:
            skipped_domains.append((domain, unique_url_count))
            log(
                f"[{domain}] CSV 已有 {unique_url_count} 条不同 URL，达到目标 "
                f"{CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN}，不创建容器"
            )
            continue
        selected_domains.append(domain)
    return selected_domains, skipped_domains


def sync_existing_domain_csvs(domains, output_dir):
    for domain in domains:
        output_path = output_dir / f"{domain}.csv"
        AtomicCsvUrlState(output_path, domain)


def copy_result_csv_files(output_dir, result_dir):
    result_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for csv_path in sorted(output_dir.glob("*.csv")):
        row_count = csv_data_row_count(csv_path)
        if row_count <= CONFIG_RESULT_CSV_MIN_ROWS_EXCLUSIVE:
            continue
        target_path = result_dir / csv_path.name
        shutil.copy2(csv_path, target_path)
        copied.append((target_path, row_count))
    return copied


def wait_domain_attempt(
    domain,
    process,
    name,
    output_path,
    starting_requested_count,
    started_at,
):
    timed_out = False
    elapsed = time.monotonic() - started_at
    remaining_timeout = max(CONFIG_SOURCE_IP_ATTEMPT_TIMEOUT_SECONDS - elapsed, 0.0)
    try:
        return_code = process.wait(timeout=remaining_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_process(process)
    except BaseException:
        terminate_process(process)
        raise
    finally:
        remove_container(name)

    if not timed_out:
        return return_code

    ending_requested_count = AtomicCsvUrlState(output_path, domain).requested_count()
    if ending_requested_count > starting_requested_count:
        log(
            f"[{domain}] 单次尝试超过 {CONFIG_SOURCE_IP_ATTEMPT_TIMEOUT_SECONDS} 秒，"
            f"但新增 {ending_requested_count - starting_requested_count} 条 requested 记录，"
            "保留进度并视为当前 IP 可用"
        )
        return 0
    log(
        f"[{domain}] 单次尝试超过 {CONFIG_SOURCE_IP_ATTEMPT_TIMEOUT_SECONDS} 秒且零新增，"
        "判定源 IP 失败"
    )
    return 124


def collect_domain_on_source_ips(domain, initial_source_ip_index, project_dir, output_dir):
    node_candidates = build_retry_node_source_ip_candidates(initial_source_ip_index)
    output_path = output_dir / f"{domain}.csv"
    crawl_state = AtomicCsvUrlState(output_path, domain)
    node_attempts = [0] * CONFIG_DISTINCT_NODE_COUNT
    blocked_nodes = set()
    while (
        crawl_state.count() < CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN
        and crawl_state.unrequested_count() > 0
    ):
        eligible_nodes = [
            node_offset
            for node_offset in range(CONFIG_DISTINCT_NODE_COUNT)
            if node_offset not in blocked_nodes
            and node_attempts[node_offset] < CONFIG_RETRIES_PER_SOURCE_IP
        ]
        eligible_nodes.sort(
            key=lambda node_offset: (
                node_attempts[node_offset] != 0,
                node_attempts[node_offset],
            )
        )
        unrequested_count = crawl_state.unrequested_count()
        selected_nodes = eligible_nodes[:min(unrequested_count, len(eligible_nodes))]
        if not selected_nodes:
            break

        claim_limit = (unrequested_count + len(selected_nodes) - 1) // len(selected_nodes)
        running = []
        try:
            for node_offset in selected_nodes:
                candidates = node_candidates[node_offset]
                attempt = node_attempts[node_offset] + 1
                source_ip, occupied_candidates = select_available_source_ip(candidates)
                if source_ip is None:
                    blocked_nodes.add(node_offset)
                    log(
                        f"[{domain}] 第 {node_offset + 1}/{CONFIG_DISTINCT_NODE_COUNT} 个节点的 "
                        f"{len(candidates)} 个候选源 IP 均已被占用，跳过该节点"
                    )
                    continue
                if occupied_candidates:
                    log(
                        f"[{domain}] 节点 {node_offset + 1} 的候选源 IP 已被占用: "
                        f"{', '.join(occupied_candidates)}，改用 {source_ip}"
                    )

                node_key = source_ip_node_key(source_ip)
                process, worker_output_path, name, starting_requested_count, started_at = (
                    start_domain_container(
                        domain,
                        source_ip,
                        node_key,
                        claim_limit,
                        attempt,
                        project_dir,
                        output_dir,
                        name_suffix=f"{node_key}_try_{attempt}",
                    )
                )
                node_attempts[node_offset] = attempt
                running.append(
                    (
                        node_offset,
                        process,
                        name,
                        worker_output_path,
                        starting_requested_count,
                        started_at,
                    )
                )
        except BaseException:
            cleanup_running_attempts(running)
            raise

        if not running:
            continue
        log(
            f"[{domain}] 已并发启动 {len(running)} 个不同节点处理 "
            f"{unrequested_count} 条未请求 URL"
        )
        try:
            for (
                node_offset,
                process,
                name,
                worker_output_path,
                starting_requested_count,
                started_at,
            ) in running:
                return_code = wait_domain_attempt(
                    domain,
                    process,
                    name,
                    worker_output_path,
                    starting_requested_count,
                    started_at,
                )
                log(
                    f"[{domain}] 节点 {node_offset + 1} 第 "
                    f"{node_attempts[node_offset]}/{CONFIG_RETRIES_PER_SOURCE_IP} 次并发尝试"
                    f"{'完成' if return_code == 0 else f'失败，退出码 {return_code}'}"
                )
        except BaseException:
            cleanup_running_attempts(running)
            raise

    unique_url_count = crawl_state.count()
    if unique_url_count >= CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN:
        log(
            f"[{domain}] CSV 已有 {unique_url_count} 条不同 URL，达到目标 "
            f"{CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN}"
        )
        return output_path

    remaining_count = crawl_state.unrequested_count()
    log(
        f"[{domain}] 节点处理结束，CSV 只有 {unique_url_count} 条不同 URL，"
        f"未达到目标 {CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN}；"
        f"剩余 {remaining_count} 条未请求 URL"
    )
    return None


def run_host():
    domains = unique_domains(CONFIG_DOMAINS)
    if not domains:
        raise ValueError("CONFIG_DOMAINS 中没有可采集的域名")

    project_dir = Path(__file__).resolve().parent
    output_dir = (project_dir / CONFIG_DOMAIN_OUTPUT_DIR).resolve()
    result_dir = (project_dir / CONFIG_RESULT_CSV_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sync_existing_domain_csvs(domains, output_dir)
    copied_files = copy_result_csv_files(output_dir, result_dir)
    log(
        f"已将 {len(copied_files)} 个数据行数大于 "
        f"{CONFIG_RESULT_CSV_MIN_ROWS_EXCLUSIVE} 的 CSV 复制到 {result_dir}"
    )
    domains, skipped_domains = select_domains_requiring_collection(domains, output_dir)
    if not domains:
        log(
            f"全部 {len(skipped_domains)} 个域名的 CSV 均已达到至少 "
            f"{CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN} 条不同 URL，无需创建容器"
        )
        return

    ensure_docker_network()
    initial_source_ips = build_initial_source_ips(len(domains))
    domain_files = []
    final_failures = []
    for initial_source_ip_index, (domain, _) in enumerate(zip(domains, initial_source_ips)):
        expected_output_path = output_dir / f"{domain}.csv"
        output_path = collect_domain_on_source_ips(
            domain,
            initial_source_ip_index,
            project_dir,
            output_dir,
        )
        domain_files.append((domain, expected_output_path))
        if output_path is None:
            final_failures.append(domain)
    if final_failures:
        raise RuntimeError(
            f"以下域名已遍历 {CONFIG_DISTINCT_NODE_COUNT} 个不同节点对应的源 IP，"
            f"每个节点最多尝试 {CONFIG_RETRIES_PER_SOURCE_IP} 次后，CSV 中不同 URL "
            f"仍不足 {CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN} 条: "
            f"{', '.join(final_failures)}"
        )

    missing_files = [str(csv_path) for _, csv_path in domain_files if not csv_path.is_file()]
    if missing_files:
        raise FileNotFoundError(f"容器未生成结果文件: {', '.join(missing_files)}")
    log(
        f"采集完成：{len(domains)} 个域名已执行采集，"
        f"{len(skipped_domains)} 个域名因 CSV 已达到不同 URL 数量目标被跳过，"
        f"结果目录 {output_dir}"
    )


def main():
    if os.environ.get(WORKER_FLAG_ENV) == "1":
        try:
            run_worker()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            domain = os.environ.get(WORKER_DOMAIN_ENV, "unknown")
            log(f"[{domain}] 本次采集尝试失败: {exc}", file=sys.stderr)
            return 1
        return 0

    run_host()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

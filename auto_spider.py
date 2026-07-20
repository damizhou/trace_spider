import csv
import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ElementTree
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


CONFIG_DOMAINS = (
    "meraki.com",
    "applovin.com",
    "mit.edu",
    "b-cdn.net",
    "tradingview.com",
    "worldbank.org",
    "supercell.com",
    "flashtalking.com",
    "kaspi.kz",
    "irs.gov",
    "networkadvertising.org",
    "launchpad.net",
)
CONFIG_URLS_PER_DOMAIN = 1000
CONFIG_CSV_BATCH_SIZE = 50
CONFIG_MAX_CANDIDATES_PER_DOMAIN = 10000
CONFIG_REVALIDATE_EXISTING_URLS = False
CONFIG_DOMAIN_OUTPUT_DIR = Path("domain_url_results")
CONFIG_DOCKER_IMAGE = "chuanzhoupan/trace_spider:250912"
CONFIG_DOCKER_NETWORK_NAME = "trace_spider"
CONFIG_DOCKER_NETWORK_SUBNET = "172.20.0.0/24"
CONFIG_DOCKER_NETWORK_GATEWAY = "172.20.0.1"
CONFIG_RETRIES_PER_SOURCE_IP = 3
CONFIG_PROXY_ATTEMPT_TIMEOUT_SECONDS = 120
CONFIG_PROXY_ROUTES = (
    ("172.20.0.2", "la01"),
    ("172.20.0.3", "la02"),
    ("172.20.0.4", "la03"),
    ("172.20.0.5", "la04"),
    ("172.20.0.6", "la05"),
    ("172.20.0.7", "la06"),
    ("172.20.0.8", "la07"),
    ("172.20.0.9", "la08"),
    ("172.20.0.10", "la09"),
    ("172.20.0.11", "la10"),
    ("172.20.0.12", "la11"),
    ("172.20.0.13", "la12"),
    ("172.20.0.14", "la13"),
    ("172.20.0.15", "la14"),
    ("172.20.0.16", "la15"),
    ("172.20.0.17", "fra1"),
    ("172.20.0.18", "fra2"),
    ("172.20.0.19", "sgp1"),
    ("172.20.0.20", "sgp2"),
    ("172.20.0.21", "la01"),
    ("172.20.0.22", "la02"),
    ("172.20.0.23", "la03"),
    ("172.20.0.24", "la04"),
    ("172.20.0.25", "la05"),
    ("172.20.0.26", "la06"),
    ("172.20.0.27", "la07"),
    ("172.20.0.28", "la08"),
    ("172.20.0.29", "la09"),
    ("172.20.0.30", "la10"),
    ("172.20.0.31", "la11"),
    ("172.20.0.32", "la12"),
    ("172.20.0.33", "la13"),
    ("172.20.0.34", "la14"),
    ("172.20.0.35", "la15"),
    ("172.20.0.36", "fra1"),
    ("172.20.0.37", "fra2"),
    ("172.20.0.38", "sgp1"),
    ("172.20.0.39", "sgp2"),
)
CONFIG_REQUEST_TIMEOUT_SECONDS = 20
CONFIG_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
CONFIG_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

WORKER_FLAG_ENV = "URL_CRAWLER_WORKER"
WORKER_DOMAIN_ENV = "URL_CRAWLER_DOMAIN"
WORKER_OUTPUT_ENV = "URL_CRAWLER_OUTPUT"
WORKER_PROXY_RETRY_ENV = "URL_CRAWLER_PROXY_RETRY"
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


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() not in {"a", "area"}:
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)


def normalize_domain(domain):
    value = domain.strip().lower().rstrip(".")
    if "://" in value:
        value = (urlsplit(value).hostname or "").lower().rstrip(".")
    if value.startswith("www."):
        value = value[4:]
    if not value or "." not in value or not re.fullmatch(r"[a-z0-9.-]+", value):
        raise ValueError(f"无效域名: {domain!r}")
    return value


def unique_domains(domains):
    return list(dict.fromkeys(normalize_domain(domain) for domain in domains))


def is_related_host(hostname, domain):
    host = (hostname or "").lower().rstrip(".")
    return host == domain or host.endswith(f".{domain}")


def normalize_page_url(raw_url, base_url, domain):
    absolute_url = urljoin(base_url, raw_url.strip())
    parts = urlsplit(absolute_url)
    if parts.scheme.lower() not in {"http", "https"} or not is_related_host(parts.hostname, domain):
        return None

    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if any(path.lower().endswith(suffix) for suffix in PAGE_SUFFIXES_TO_SKIP):
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


def fetch(url):
    request = Request(
        url,
        headers={
            "User-Agent": CONFIG_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=CONFIG_REQUEST_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        body = response.read(CONFIG_MAX_RESPONSE_BYTES + 1)
        if len(body) > CONFIG_MAX_RESPONSE_BYTES:
            raise ValueError(f"响应超过 {CONFIG_MAX_RESPONSE_BYTES} 字节限制: {url}")
        charset = response.headers.get_content_charset() or "utf-8"
        return response.geturl(), content_type, body.decode(charset, errors="replace")


def validate_page_url(url, domain):
    request = Request(url, headers={"User-Agent": CONFIG_USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with urlopen(request, timeout=CONFIG_REQUEST_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return None
            response.read(1)
            return normalize_page_url(response.geturl(), url, domain)
    except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError):
        return None


def extract_sitemap_urls(xml_text, base_url, domain):
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return [], []

    page_urls = []
    sitemap_urls = []
    root_name = root.tag.rsplit("}", 1)[-1].lower()
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() != "loc" or not element.text:
            continue
        url = urljoin(base_url, element.text.strip())
        if root_name == "sitemapindex":
            if is_related_host(urlsplit(url).hostname, domain):
                sitemap_urls.append(url)
        else:
            normalized = normalize_page_url(url, base_url, domain)
            if normalized:
                page_urls.append(normalized)
    return page_urls, sitemap_urls


def discover_sitemaps(domain, known_candidates):
    sitemap_urls = deque([f"https://{domain}/sitemap.xml"])
    seen_sitemaps = set()
    page_urls = []

    robots_url = f"https://{domain}/robots.txt"
    try:
        _, _, robots_text = fetch(robots_url)
        for line in robots_text.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_urls.append(line.split(":", 1)[1].strip())
    except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError) as exc:
        print(f"[{domain}] robots.txt 读取失败: {exc}", file=sys.stderr)

    while sitemap_urls and len(known_candidates) < CONFIG_MAX_CANDIDATES_PER_DOMAIN:
        sitemap_url = sitemap_urls.popleft()
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)
        try:
            final_url, _, xml_text = fetch(sitemap_url)
        except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError) as exc:
            print(f"[{domain}] 站点地图读取失败 {sitemap_url}: {exc}", file=sys.stderr)
            continue
        urls, nested_sitemaps = extract_sitemap_urls(xml_text, final_url, domain)
        for url in urls:
            if url in known_candidates:
                continue
            known_candidates.add(url)
            page_urls.append(url)
            if len(known_candidates) >= CONFIG_MAX_CANDIDATES_PER_DOMAIN:
                break
        sitemap_urls.extend(url for url in nested_sitemaps if url not in seen_sitemaps)
    return page_urls


def collect_domain_urls(domain, existing_urls, on_urls):
    collected = list(existing_urls)
    collected_set = set(existing_urls)
    if len(collected) >= CONFIG_URLS_PER_DOMAIN:
        return collected[:CONFIG_URLS_PER_DOMAIN]

    known_candidates = set(existing_urls)
    sitemap_candidates = discover_sitemaps(domain, known_candidates)
    seeds = [f"https://{domain}/", f"https://www.{domain}/"]
    queue = deque(dict.fromkeys([*sitemap_candidates, *existing_urls, *seeds]))
    queued_urls = set(queue)
    attempted = set()

    while queue and len(collected) < CONFIG_URLS_PER_DOMAIN:
        url = queue.popleft()
        if url in attempted:
            continue
        attempted.add(url)
        try:
            final_url, content_type, html = fetch(url)
        except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError) as exc:
            print(f"[{domain}] 页面读取失败 {url}: {exc}", file=sys.stderr)
            continue

        normalized_final_url = normalize_page_url(final_url, url, domain)
        if not normalized_final_url or content_type not in {"text/html", "application/xhtml+xml"}:
            continue
        if normalized_final_url not in collected_set:
            collected_set.add(normalized_final_url)
            collected.append(normalized_final_url)
            on_urls([normalized_final_url])

        parser = LinkParser()
        parser.feed(html)
        for raw_link in parser.links:
            normalized_url = normalize_page_url(raw_link, final_url, domain)
            if not normalized_url or normalized_url in queued_urls or normalized_url in attempted:
                continue
            queued_urls.add(normalized_url)
            queue.append(normalized_url)
    return collected[:CONFIG_URLS_PER_DOMAIN]


class CsvBatchWriter:
    FIELDNAMES = ("id", "url", "domain")

    def __init__(self, path, domain):
        self.path = path
        self.domain = domain
        self.buffer = []
        self.existing_urls = []
        self.known_urls = set()
        self.next_id = 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._load_existing()
        file_exists = self.path.is_file() and self.path.stat().st_size > 0
        self._open_append()
        if not file_exists:
            self.writer.writeheader()
            self._sync()

    def _open_append(self):
        self.file = self.path.open("a", newline="", encoding="utf-8-sig")
        self.writer = csv.DictWriter(self.file, fieldnames=self.FIELDNAMES)

    def _load_existing(self):
        if not self.path.is_file() or self.path.stat().st_size == 0:
            return
        with self.path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if tuple(reader.fieldnames or ()) != self.FIELDNAMES:
                raise ValueError(f"CSV 表头不正确，无法断点续采: {self.path}")
            max_id = 0
            needs_rewrite = False
            for row in reader:
                if row["domain"] != self.domain:
                    raise ValueError(
                        f"CSV 域名与当前任务不一致: {self.path} 中为 {row['domain']!r}，当前为 {self.domain!r}"
                    )
                try:
                    row_id = int(row["id"])
                except ValueError as exc:
                    raise ValueError(f"CSV id 不是整数: {self.path} -> {row['id']!r}") from exc
                max_id = max(max_id, row_id)
                raw_url = row["url"].strip()
                url = normalize_page_url(raw_url, raw_url, self.domain) if raw_url else None
                if not url or url in self.known_urls:
                    needs_rewrite = True
                    continue
                if url != raw_url or row_id != len(self.existing_urls) + 1:
                    needs_rewrite = True
                self.known_urls.add(url)
                self.existing_urls.append(url)
            if needs_rewrite:
                self._rewrite_existing()
                self.next_id = len(self.existing_urls) + 1
            else:
                self.next_id = max_id + 1

    def _rewrite_existing(self):
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temporary_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
            writer.writeheader()
            for row_id, url in enumerate(self.existing_urls, start=1):
                writer.writerow({"id": row_id, "url": url, "domain": self.domain})
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, self.path)
        print(f"[{self.domain}] 已清理非页面 URL，保留 {len(self.existing_urls)} 条")

    def add_urls(self, urls):
        for url in urls:
            if url in self.known_urls:
                continue
            self.known_urls.add(url)
            self.buffer.append(url)
            if len(self.buffer) >= CONFIG_CSV_BATCH_SIZE:
                self.flush()

    def replace_existing_urls(self, urls):
        self.flush()
        self.file.close()
        self.existing_urls = list(dict.fromkeys(urls))
        self.known_urls = set(self.existing_urls)
        self.next_id = len(self.existing_urls) + 1
        self._rewrite_existing()
        self._open_append()

    def flush(self):
        if not self.buffer:
            return
        for url in self.buffer:
            self.writer.writerow({"id": self.next_id, "url": url, "domain": self.domain})
            self.next_id += 1
        self.buffer.clear()
        self._sync()

    def _sync(self):
        self.file.flush()
        os.fsync(self.file.fileno())

    def close(self):
        self.flush()
        self.file.close()


def revalidate_existing_urls(domain, csv_writer):
    original_urls = list(csv_writer.existing_urls)
    if not original_urls or not CONFIG_REVALIDATE_EXISTING_URLS:
        return

    valid_urls = []
    valid_set = set()
    for index, url in enumerate(original_urls, start=1):
        validated_url = validate_page_url(url, domain)
        if validated_url and validated_url not in valid_set:
            valid_set.add(validated_url)
            valid_urls.append(validated_url)
        if index % 100 == 0 or index == len(original_urls):
            print(f"[{domain}] 复检已有 URL: {index}/{len(original_urls)}，有效 {len(valid_urls)}")

    if valid_urls != original_urls:
        csv_writer.replace_existing_urls(valid_urls)
        print(f"[{domain}] 复检完成，删除 {len(original_urls) - len(valid_urls)} 条无效或非页面 URL")


def run_worker():
    domain = normalize_domain(os.environ[WORKER_DOMAIN_ENV])
    output_path = Path(os.environ[WORKER_OUTPUT_ENV])
    csv_writer = CsvBatchWriter(output_path, domain)
    revalidate_existing_urls(domain, csv_writer)
    starting_count = len(csv_writer.existing_urls)
    if len(csv_writer.existing_urls) >= CONFIG_URLS_PER_DOMAIN:
        csv_writer.close()
        print(f"[{domain}] 已有 {len(csv_writer.existing_urls)} 条 URL，跳过已完成任务")
        return
    if os.environ.get(WORKER_PROXY_RETRY_ENV) == "1":
        preflight_urls = (f"https://{domain}/", f"https://www.{domain}/")
        accessible_url = next(
            (url for url in preflight_urls if validate_page_url(url, domain)),
            None,
        )
        if accessible_url is None:
            csv_writer.close()
            raise RuntimeError(f"{domain} 代理重试预检失败，根页面无法正常返回 HTML/XHTML")
        print(f"[{domain}] 代理重试预检通过: {accessible_url}")
    print(
        f"[{domain}] 从第 {len(csv_writer.existing_urls) + 1} 条继续采集，"
        f"每 {CONFIG_CSV_BATCH_SIZE} 条写入一次"
    )
    try:
        urls = collect_domain_urls(domain, csv_writer.existing_urls, csv_writer.add_urls)
    finally:
        csv_writer.close()
    if len(urls) <= starting_count:
        raise RuntimeError(f"{domain} 本次没有新增任何有效页面 URL")
    print(f"[{domain}] 已采集 {len(urls)} 条 URL，结果写入 {output_path}")


def container_name(domain):
    slug = re.sub(r"[^a-z0-9]+", "_", domain).strip("_")[:40]
    digest = hashlib.sha1(domain.encode("utf-8")).hexdigest()[:8]
    return f"url_spider_{slug}_{digest}"


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
        print(
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


def validate_proxy_routes():
    network = ipaddress.ip_network(CONFIG_DOCKER_NETWORK_SUBNET, strict=True)
    gateway = ipaddress.ip_address(CONFIG_DOCKER_NETWORK_GATEWAY)
    route_ips = [ipaddress.ip_address(source_ip) for source_ip, _ in CONFIG_PROXY_ROUTES]
    if len(route_ips) != len(set(route_ips)):
        raise ValueError("CONFIG_PROXY_ROUTES 中存在重复源 IP")
    for source_ip, proxy_name in CONFIG_PROXY_ROUTES:
        ip = ipaddress.ip_address(source_ip)
        if ip not in network or ip in {network.network_address, network.broadcast_address, gateway}:
            raise ValueError(f"代理 {proxy_name} 的源 IP 不可用: {source_ip}")
    if CONFIG_RETRIES_PER_SOURCE_IP < 1:
        raise ValueError("CONFIG_RETRIES_PER_SOURCE_IP 必须至少为 1")


def build_initial_routes(domain_count):
    validate_proxy_routes()
    if domain_count > len(CONFIG_PROXY_ROUTES):
        raise ValueError(
            f"域名数量 {domain_count} 超过可用源 IP 数量 {len(CONFIG_PROXY_ROUTES)}"
        )
    return list(CONFIG_PROXY_ROUTES[:domain_count])


def build_distinct_node_routes(initial_route_index):
    initial_source_ip, initial_proxy_name = CONFIG_PROXY_ROUTES[initial_route_index]
    proxy_names = list(dict.fromkeys(proxy_name for _, proxy_name in CONFIG_PROXY_ROUTES))
    initial_proxy_index = proxy_names.index(initial_proxy_name)
    ordered_proxy_names = proxy_names[initial_proxy_index:] + proxy_names[:initial_proxy_index]

    routes = []
    for proxy_name in ordered_proxy_names:
        if proxy_name == initial_proxy_name:
            routes.append((initial_source_ip, proxy_name))
            continue
        source_ip = next(
            source_ip
            for source_ip, mapped_proxy_name in CONFIG_PROXY_ROUTES
            if mapped_proxy_name == proxy_name
        )
        routes.append((source_ip, proxy_name))
    return routes


def iter_retry_routes(initial_route_index):
    for node_offset, (source_ip, proxy_name) in enumerate(build_distinct_node_routes(initial_route_index)):
        first_attempt = 2 if node_offset == 0 else 1
        for attempt in range(first_attempt, CONFIG_RETRIES_PER_SOURCE_IP + 1):
            yield source_ip, proxy_name, attempt


def start_domain_container(domain, container_ip, proxy_name, attempt, is_proxy_retry, project_dir, output_dir):
    name = container_name(domain)
    remove_stale_container(name)
    container_output = f"/output/{domain}.csv"
    create_command = [
        "docker", "run", "--init", "--privileged", "--interactive", "--tty", "--detach", "--name", name,
        "--network", CONFIG_DOCKER_NETWORK_NAME,
        "--ip", container_ip,
        "--volume", f"{project_dir}:/app:ro",
        "--volume", f"{output_dir}:/output",
        "--env", f"HOST_UID={os.getuid()}",
        "--env", f"HOST_GID={os.getgid()}",
        CONFIG_DOCKER_IMAGE,
        "/bin/bash",
    ]
    print(
        f"[{domain}] 启动容器 {name}，源 IP {container_ip}，"
        f"代理 {proxy_name}，第 {attempt}/{CONFIG_RETRIES_PER_SOURCE_IP} 次"
    )
    subprocess.run(create_command, check=True)
    worker_command = [
        "docker", "exec",
        "--env", f"{WORKER_FLAG_ENV}=1",
        "--env", f"{WORKER_DOMAIN_ENV}={domain}",
        "--env", f"{WORKER_OUTPUT_ENV}={container_output}",
        "--env", f"{WORKER_PROXY_RETRY_ENV}={'1' if is_proxy_retry else '0'}",
        name, "python", "/app/auto_spider.py",
    ]
    output_path = output_dir / f"{domain}.csv"
    starting_count = csv_data_row_count(output_path)
    process = subprocess.Popen(worker_command)
    return process, output_path, name, starting_count, time.monotonic()


def csv_data_row_count(path):
    if not path.is_file() or path.stat().st_size == 0:
        return 0
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return sum(1 for _ in csv.DictReader(file))


def wait_domain_attempt(domain, process, name, output_path, starting_count, started_at):
    timed_out = False
    elapsed = time.monotonic() - started_at
    remaining_timeout = max(CONFIG_PROXY_ATTEMPT_TIMEOUT_SECONDS - elapsed, 0.0)
    try:
        return_code = process.wait(timeout=remaining_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait()
    finally:
        remove_container(name)

    if not timed_out:
        return return_code

    ending_count = csv_data_row_count(output_path)
    if ending_count > starting_count:
        print(
            f"[{domain}] 单次尝试超过 {CONFIG_PROXY_ATTEMPT_TIMEOUT_SECONDS} 秒，"
            f"但新增 {ending_count - starting_count} 条有效 URL，保留进度并视为节点可用"
        )
        return 0
    print(
        f"[{domain}] 单次尝试超过 {CONFIG_PROXY_ATTEMPT_TIMEOUT_SECONDS} 秒且零新增，判定节点失败"
    )
    return 124


def retry_domain_on_all_routes(domain, initial_route_index, project_dir, output_dir):
    for source_ip, proxy_name, attempt in iter_retry_routes(initial_route_index):
        process, output_path, name, starting_count, started_at = start_domain_container(
            domain,
            source_ip,
            proxy_name,
            attempt,
            True,
            project_dir,
            output_dir,
        )
        return_code = wait_domain_attempt(
            domain, process, name, output_path, starting_count, started_at
        )
        if return_code == 0:
            print(f"[{domain}] 使用 {source_ip} -> {proxy_name} 获取 URL 成功")
            return output_path
        print(
            f"[{domain}] 使用 {source_ip} -> {proxy_name} 获取 URL 失败，"
            f"本 IP 已尝试 {attempt}/{CONFIG_RETRIES_PER_SOURCE_IP} 次"
        )
    return None


def run_host():
    domains = unique_domains(CONFIG_DOMAINS)
    if not domains:
        raise ValueError("CONFIG_DOMAINS 中没有可采集的域名")
    ensure_docker_network()
    initial_routes = build_initial_routes(len(domains))

    project_dir = Path(__file__).resolve().parent
    output_dir = (project_dir / CONFIG_DOMAIN_OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    running = []
    try:
        for route_index, (domain, (source_ip, proxy_name)) in enumerate(zip(domains, initial_routes)):
            process, output_path, name, starting_count, started_at = start_domain_container(
                domain,
                source_ip,
                proxy_name,
                1,
                False,
                project_dir,
                output_dir,
            )
            running.append(
                (domain, route_index, process, output_path, name, starting_count, started_at)
            )
    except Exception:
        for _, _, process, _, name, _, _ in running:
            process.kill()
            remove_container(name)
        raise

    failed_domains = []
    domain_files = []
    try:
        for domain, route_index, process, output_path, name, starting_count, started_at in running:
            return_code = wait_domain_attempt(
                domain, process, name, output_path, starting_count, started_at
            )
            if return_code != 0:
                failed_domains.append((domain, route_index))
            domain_files.append((domain, output_path))
    except KeyboardInterrupt:
        for _, _, process, _, name, _, _ in running:
            process.kill()
            remove_container(name)
        raise

    final_failures = []
    for domain, initial_route_index in failed_domains:
        output_path = retry_domain_on_all_routes(
            domain,
            initial_route_index,
            project_dir,
            output_dir,
        )
        if output_path is None:
            final_failures.append(domain)
    if final_failures:
        distinct_proxy_count = len({proxy_name for _, proxy_name in CONFIG_PROXY_ROUTES})
        raise RuntimeError(
            f"以下域名在全部 {distinct_proxy_count} 个不同代理节点上各重试 "
            f"{CONFIG_RETRIES_PER_SOURCE_IP} 次后仍未获取到有效 URL: {', '.join(final_failures)}"
        )

    missing_files = [str(csv_path) for _, csv_path in domain_files if not csv_path.is_file()]
    if missing_files:
        raise FileNotFoundError(f"容器未生成结果文件: {', '.join(missing_files)}")
    print(f"采集完成：{len(domains)} 个域名的独立 CSV 已写入 {output_dir}")


def main():
    if os.environ.get(WORKER_FLAG_ENV) == "1":
        run_worker()
    else:
        run_host()


if __name__ == "__main__":
    main()

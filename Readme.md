# 站内 URL 采集

最后更新：2026-07-21 11:03:38

本项目在本机通过 Docker 并行采集站内页面 URL。每个去重后的目标域名首轮启动一个独立容器，需要换 IP 时可为同一域名并发启动多个不同节点容器。每个域名最多收集 1000 条 URL，并分别输出独立 CSV 文件。

## 配置

在 auto_spider.py 文件顶部修改以下 CONFIG_* 配置：

- CONFIG_DOMAINS：目标域名列表，重复域名会自动去重。
- CONFIG_URLS_PER_DOMAIN：每个域名最多采集的 URL 数量，默认 1000。
- CONFIG_SKIP_DOMAIN_CSV_ROWS_GREATER_THAN：CSV 数据行数大于该值时直接跳过域名且不创建容器，默认 999。
- CONFIG_MAX_CANDIDATES_PER_DOMAIN：单域名最多检查的候选 URL 数量，默认 10000。
- CONFIG_MIN_REQUEST_INTERVAL_SECONDS：同一域名在同一节点上的相邻页面请求最小启动间隔，跨容器生效，默认 120 秒。
- CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER：单个 URL 在同一容器内的最大请求次数，默认 3。
- CONFIG_DOMAIN_OUTPUT_DIR：各域名结果目录，默认 domain_url_results/。
- CONFIG_DOCKER_IMAGE：采集容器使用的镜像，默认 chuanzhoupan/trace_spider:250912。
- CONFIG_DOCKER_NETWORK_NAME：专用 Docker bridge 网络名称，默认 trace_spider。
- CONFIG_DOCKER_NETWORK_SUBNET：容器子网，默认 172.20.0.0/24。
- CONFIG_DOCKER_NETWORK_GATEWAY：容器网关，默认 172.20.0.1。
- CONFIG_RETRIES_PER_SOURCE_IP：每个源 IP 的最大尝试次数，默认 3。
- CONFIG_SOURCE_IP_ATTEMPT_TIMEOUT_SECONDS：单个源 IP 尝试的硬超时；根据最大候选数量和请求间隔自动计算，避免限速等待期间被提前终止。
- CONFIG_SOURCE_IPS：可分配给容器的源 IP 列表，当前为 172.20.0.2–172.20.0.191。
- CONFIG_DISTINCT_NODE_COUNT：每个域名需要轮换尝试的不同节点数，当前为 19。
- CONFIG_CHROME_BINARY_PATH：容器内 Chrome 可执行文件路径。
- CONFIG_CHROMEDRIVER_PATH：容器内 ChromeDriver 可执行文件路径。
- CONFIG_SCRAPY_SPIDER_NAME：容器内执行的 Scrapy Spider 名称，默认 trace。

## 运行

本机需要已安装 Docker，并且当前用户可以直接执行 Docker 命令。

    venv/bin/python auto_spider.py

也可以通过兼容入口运行：

    venv/bin/python main.py

调度器会完成以下工作：

1. 对 CONFIG_DOMAINS 去重，并在创建 Docker 网络和容器前检查每个域名的 CSV；数据行数大于配置阈值时直接跳过。
2. 自动创建 172.20.0.0/24 专用 bridge 网络，并从 172.20.0.2 开始按域名顺序分配固定容器 IP。
3. 每个域名首轮创建一个后台 Docker 容器；需要换 IP 且存在多条 pending URL 时，会按可用的不同节点并发创建多个容器。
4. 容器工作进程执行 python -m scrapy crawl trace，由 trace Spider 从持久化状态中的未访问 URL 队列继续遍历站内链接。
5. Scrapy 下载中间件在单个域名任务内复用一个 Selenium Chrome 会话，通过 driver.get() 请求页面，并从 Chrome 性能日志获取 HTTP 状态码和 MIME 类型。
   同一域名在同一节点上的相邻请求启动时间至少间隔 120 秒，该时间记录跨容器共享；不同节点之间无需等待，可以并行请求。
6. Scrapy Pipeline 只保留同域名且成功返回 HTML/XHTML 的 URL，并通过文件锁从 SQLite 成功状态原子同步 CSV，保证第 1 条是首页且并发容器不会覆盖结果。
7. 每个域名单独输出 domain_url_results/域名.csv，并使用同目录下的域名.crawl_state.sqlite3 保存待访问、成功和失败状态。
8. 容器任务结束后由宿主机删除对应容器，专用网络保留供下次运行复用。

如果容器异常退出，或者本次没有新增有效 URL 且仍有 pending URL，则进入换 IP 阶段。程序优先选择尚未尝试的节点，并发节点数不超过 pending URL 数量；每个容器通过 SQLite 原子领取不同的 pending URL，避免多个节点请求同一 URL。某个节点没有可用源 IP 时跳过该节点，同一节点最多尝试 3 次。所有已发现 URL 都变为 success 或 failed 后正常结束。

不同域名的首轮任务仍然并行。单个域名进入换 IP 阶段后，其多个不同节点也可以并行；同一节点对同一域名始终只有一个活动容器，并通过 SQLite 中的节点时间记录保证容器重建前后仍满足 120 秒间隔。

单个源 IP 的硬超时会根据最大候选数量、120 秒请求间隔和单次请求超时自动计算。超时前如果 CSV 已新增有效 URL，则保留结果并把该 IP 视为可用；超时且零新增时才记为失败并进入重试或换 IP。

首轮并发容器的硬超时从各自实际启动时间计算，不会因为宿主机按顺序等待而额外延长后续容器的运行时间。

首次采集会把域名根页面加入待访问队列。根页面一旦成功，后续切换 IP 或重新运行时不会再次请求；如果在同一容器内连续 3 次失败，则标记为失败并永久跳过。其他 URL 使用相同规则。

## CSV 格式

    id,url,domain
    1,https://bsky.app/,bsky.app

每个域名的 CSV 位于 domain_url_results/，例如 domain_url_results/mit.edu.csv。每个文件中的 id 都从 1 开始连续编号，第 1 条固定为该域名首页的最终可访问地址。

SQLite 状态文件在发现链接时立即记录待访问 URL，在页面解析完成后记录成功状态，在同一容器连续 3 次失败后记录失败状态。每次成功状态变化都会在文件锁保护下重新生成 CSV，并通过原子替换发布完整结果，因此多个容器同时完成页面时不会产生重复 ID、部分覆盖或交叉写入。

新 URL 在写入前已由 Chrome 验证为可访问的 HTML/XHTML 页面。断点续采或切换 IP 时，trace Spider 只调度状态为 pending 的 URL；success 和 failed URL 均不会再次请求。旧 CSV 会在首次使用新逻辑时自动迁移为 success 状态。

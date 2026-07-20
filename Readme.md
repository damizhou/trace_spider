# 站内 URL 采集

最后更新：2026-07-14 20:19:56

本项目在本机通过 Docker 并行采集站内页面 URL。每个去重后的目标域名启动一个独立容器，每个域名最多收集 1000 条 URL，并分别输出独立 CSV 文件。

## 配置

在 auto_spider.py 文件顶部修改以下 CONFIG_* 配置：

- CONFIG_DOMAINS：目标域名列表，重复域名会自动去重。
- CONFIG_URLS_PER_DOMAIN：每个域名最多采集的 URL 数量，默认 1000。
- CONFIG_CSV_BATCH_SIZE：增量写入批次大小，默认每 50 条写入并同步到磁盘。
- CONFIG_MAX_CANDIDATES_PER_DOMAIN：单域名最多检查的候选 URL 数量，默认 10000。
- CONFIG_REVALIDATE_EXISTING_URLS：断点续采前是否重新验证已有 URL，默认关闭，避免每次代理重试重复复检。
- CONFIG_DOMAIN_OUTPUT_DIR：各域名结果目录，默认 domain_url_results/。
- CONFIG_DOCKER_IMAGE：采集容器使用的镜像，默认 chuanzhoupan/trace_spider_chrome_149:260611。
- CONFIG_DOCKER_NETWORK_NAME：专用 Docker bridge 网络名称，默认 trace_spider_172_20。
- CONFIG_DOCKER_NETWORK_SUBNET：容器子网，默认 172.20.0.0/24。
- CONFIG_DOCKER_NETWORK_GATEWAY：容器网关，默认 172.20.0.1。
- CONFIG_RETRIES_PER_SOURCE_IP：每个源 IP 的最大尝试次数，默认 3。
- CONFIG_PROXY_ATTEMPT_TIMEOUT_SECONDS：单次代理尝试的硬超时，默认 120 秒。
- CONFIG_PROXY_ROUTES：38 组源 IP 与代理节点对应关系。

## 运行

本机需要已安装 Docker，并且当前用户可以直接执行 Docker 命令。

    python auto_spider.py

也可以通过兼容入口运行：

    python main.py

调度器会完成以下工作：

1. 对 CONFIG_DOMAINS 去重。
2. 自动创建 172.20.0.0/24 专用 bridge 网络，并从 172.20.0.2 开始按域名顺序分配固定容器 IP。
3. 每个域名创建一个带 init、特权模式和交互终端的后台 Docker 容器。
4. 容器优先从站点地图(Sitemap)获取候选 URL，再通过页面链接补充候选。
5. 只有实际请求成功、最终地址仍属于目标域名且响应为 HTML/XHTML 的 URL 才写入 CSV；电子书、文档、图片、音视频、压缩包和其他下载资源会被排除。
6. 每个域名单独输出 domain_url_results/域名.csv。
7. 再次运行时直接读取已有 CSV，从尚未完成的数量继续采集；达到 1000 条的域名直接跳过。
8. 容器任务结束后由宿主机删除对应容器，专用网络保留供下次运行复用。

如果某次容器执行没有新增任何通过校验的 HTML/XHTML 页面 URL，则判定当前代理节点获取失败。同一个源 IP 总共尝试 3 次，之后切换到下一个不同代理节点，直到成功或 19 个不同节点都尝试完。38 个源 IP 是 19 个代理节点的两组映射；单个域名重试时不会重复尝试同名节点。首轮域名任务并行执行，换节点重试阶段按域名串行执行，避免固定 IP 冲突。

每次代理尝试最多运行 120 秒。超时前如果 CSV 已新增有效 URL，则保留结果并把该节点视为可用；超时且零新增时才记为失败并进入重试或换节点。

首轮并发容器的 120 秒从各自实际启动时间计算，不会因为宿主机按顺序等待而额外延长后续容器的运行时间。

换节点重试前会先请求目标域名根页面进行预检。根页面无法正常返回 HTML/XHTML 时立即判定该节点失败；预检通过后才执行完整 URL 续采，避免在明显不可访问的节点上长时间遍历候选 URL。

## CSV 格式

    id,url,domain
    1,https://bsky.app/profile/atproto.com,bsky.app

每个域名的 CSV 位于 domain_url_results/，例如 domain_url_results/mit.edu.csv。每个文件中的 id 都从 1 开始连续编号。

采集期间每累计 50 条 URL 就会追加写入 CSV；正常结束、异常或手动中断时，不足 50 条的尾批次也会写入。因此重新运行程序即可从已有 CSV 断点续采，无需额外进度文件。

新 URL 在写入前已经验证为可访问的 HTML/XHTML 页面，因此断点续采默认信任已有 CSV，不再逐条重复复检。只有手动把 CONFIG_REVALIDATE_EXISTING_URLS 改为 True 时，才会重新验证已有记录。

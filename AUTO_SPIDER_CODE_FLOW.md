# auto_spider.py 代码流程

最后更新：2026-07-22 15:31:40

本文档按当前代码实现说明 `auto_spider.py` 的入口分支、宿主机调度、单域名节点调度、容器 Worker、Scrapy 页面遍历、Chrome 请求以及原子 CSV 状态流转。

## 一、总入口

入口函数为 `main()`：

```text
main()
├─ URL_CRAWLER_WORKER != 1
│  └─ run_host()       宿主机调度模式
└─ URL_CRAWLER_WORKER == 1
   └─ run_worker()     Docker 容器 Worker 模式
```

- 直接执行 `venv/bin/python auto_spider.py` 时进入 `run_host()`。
- 宿主机通过 `docker exec` 设置 `URL_CRAWLER_WORKER=1` 后，容器内同一个脚本进入 `run_worker()`。
- Worker 捕获普通异常后记录当前域名的失败日志并返回退出码 1；宿主模式异常直接向外抛出。

### 1.1 首页定义

首页有且只有一个定义：`CONFIG_DOMAINS` 中每个元素规范化为 hostname 后，首次种子请求 URL `https://<hostname>/` 就是该任务的首页。

```text
CONFIG_DOMAINS 元素：google.com
首页：https://google.com/

CONFIG_DOMAINS 元素：www.google.com
首页：https://www.google.com/
```

首页定义遵循以下规则：

- 保留完整 hostname，`google.com` 和 `www.google.com` 是两个独立任务。
- 首页始终是代码首次安排访问的种子请求 URL。
- 旧 CSV 第 1 行不能重新定义首页。
- 页面发生重定向时，最终 URL 只用于本次响应解析，不持久化，也不能替代首页。
- CSV 第 1 行固定写入种子请求 URL。
- 首页和其他 URL 都通过 `requested` 字段记录是否已经被原子领取并安排请求。

CSV 的 URL 来源也只有两类：

1. 第 1 行固定为种子首页 `https://<hostname>/`。
2. 其余行来自已访问页面中 `<a href>` 提取、规范化并通过规则过滤的候选 URL。

页面重定向后的最终 URL 不会替换请求 URL，也不会因为重定向自动新增为 CSV 行。只有当该最终 URL 后续也从某个页面的 `<a href>` 中被提取时，它才会作为独立候选进入 CSV。

## 二、宿主机调度流程

入口函数为 `run_host()`：

```text
run_host()
│
├─ 1. unique_domains(CONFIG_DOMAINS)
│     规范化域名并去重
│
├─ 2. 创建输出目录
│     domain_url_results/
│     result_csv/
│
├─ 3. sync_existing_domain_csvs()
│     原子迁移和规范化已有 CSV
│
├─ 4. copy_result_csv_files()
│     将数据行数大于 10 的 CSV 复制到 result_csv/
│
├─ 5. select_domains_requiring_collection()
│     CSV 去重后的 URL 数量达到配置目标时跳过
│
├─ 6. ensure_docker_network()
│     检查或创建 trace_spider Docker 网络
│
├─ 7. build_initial_source_ips()
│     校验源 IP 并建立每个域名的起始节点索引
│
├─ 8. 按 CONFIG_DOMAINS 顺序逐个处理域名
│     └─ collect_domain_on_source_ips()
│
└─ 9. 汇总结果
      ├─ 域名未完成：抛出 RuntimeError
      ├─ 结果 CSV 不存在：抛出 FileNotFoundError
      └─ 全部完成：输出完成日志
```

### 2.1 域名初始化

`unique_domains()` 对配置域名执行以下处理：

1. 去除首尾空白并转为小写。
2. 如果配置值包含协议，则提取 hostname。
3. 保留完整 hostname，包括开头的 `www.`。
4. 移除结尾的点号。
5. 校验域名格式。
6. 按首次出现顺序去重；`google.com` 和 `www.google.com` 视为两个独立目标。

如果最终域名列表为空，`run_host()` 直接抛出异常。

### 2.2 已有数据同步

`sync_existing_domain_csvs()` 为每个域名创建 `AtomicCsvUrlState`，并在文件锁保护下规范化 CSV：

```text
已有三字段 CSV：id,url,domain
├─ 增加 requested 字段
├─ 旧 URL 默认 requested=0
├─ 清理不符合页面规则的 URL
├─ URL 去重
├─ 将 https://<hostname>/ 固定到第 1 行
└─ 通过临时文件 + fsync + os.replace 原子发布
```

随后 `copy_result_csv_files()` 扫描 `domain_url_results/*.csv`，将数据行数大于 `CONFIG_RESULT_CSV_MIN_ROWS_EXCLUSIVE`，即大于 10 的文件复制到 `result_csv/`。复制发生在本轮新采集开始之前。

### 2.3 域名跳过条件

`select_domains_requiring_collection()` 统计每个域名 CSV 经过规范化和去重后的 URL 数量：

```text
CSV 去重后的 URL 数量 >= CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN
└─ 跳过该域名，不创建容器

CSV 去重后的 URL 数量 < CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN
└─ 进入本轮采集
```

当前 `CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN = 1000`。该变量表示每个域名 CSV 至少需要保存的不同 URL 数量；`requested` 仅表示 URL 是否已被原子领取，不参与域名跳过判断。

配置值必须大于等于 1，且不能超过 `min(CONFIG_URLS_PER_DOMAIN, CONFIG_MAX_CANDIDATES_PER_DOMAIN)`，否则目标在当前采集上限下不可达，程序会直接抛出异常。

### 2.4 Docker 网络和源 IP

`ensure_docker_network()` 检查名为 `trace_spider` 的 bridge 网络：

- 网络不存在：创建 `172.20.0.0/24`，网关为 `172.20.0.1`。
- 网络已存在且配置正确：直接复用。
- 网络已存在但子网或网关不一致：抛出异常，不自动覆盖网络。

`build_initial_source_ips()` 校验：

- `172.20.0.2` 到 `172.20.0.191` 中没有重复 IP。
- 所有 IP 都属于指定子网且不是网关、网络地址或广播地址。
- 源 IP 数量能够整除 19 个节点。
- 待采集域名数量不能超过源 IP 数量。

### 2.5 域名之间的执行关系

`run_host()` 使用普通 `for` 循环调用 `collect_domain_on_source_ips()`，因此不同域名按配置顺序串行处理。

并发只发生在同一个域名内部：当该域名存在多条 `requested=0` URL 时，可以为不同节点同时启动多个容器。

## 三、单域名节点调度

入口函数为 `collect_domain_on_source_ips()`：

```text
collect_domain_on_source_ips(domain)
│
├─ 创建或打开 domain.csv
│  ├─ 迁移为 id,url,domain,requested
│  └─ 将 https://domain/ 固定到第 1 行
│
└─ while 存在 requested=0 URL
   ├─ 选择尚未尝试的节点
   ├─ 为节点选择未占用的源 IP
   ├─ 计算每个 Worker 的 claim_limit
   ├─ 并发启动多个节点容器
   ├─ 等待各容器结束或超时
   ├─ 删除容器
   └─ 再次检查 requested=0 数量
```

### 3.1 节点和候选源 IP

190 个源 IP 按 19 个节点组织，每个节点有 10 个候选源 IP。`build_retry_node_source_ip_candidates()` 根据域名的初始索引旋转节点起点，避免所有域名始终从同一个节点开始。

启动容器前，`select_available_source_ip()` 检查 Docker 网络中已经占用的 IP：

- 当前候选 IP 已占用：尝试该节点的下一个候选 IP。
- 该节点全部候选 IP 都被占用：将节点加入 `blocked_nodes`，本域名后续不再选择该节点。

### 3.2 未请求 URL 分配

每轮选择的节点数为：

```text
min(requested=0 URL 数量, 当前可用节点数量)
```

每个 Worker 的领取上限为：

```text
claim_limit = ceil(requested=0 URL 数量 / 选中节点数量)
```

每个 Worker 启动 Spider 时，在 `.csv.lock` 文件锁保护下领取一批 `requested=0` URL，并在同一次原子写入中将其改为 `requested=1`。多个容器因此不会领取同一 URL。

### 3.3 容器启动

`start_domain_container()` 分两步启动任务：

```text
docker run
├─ 创建后台容器
├─ 使用 trace_spider 网络和固定源 IP
├─ 项目目录挂载到 /app:ro
└─ 结果目录挂载到 /output

docker exec
├─ 使用宿主机 UID:GID
├─ 设置 Worker 环境变量
└─ 执行 python /app/auto_spider.py
```

项目代码以只读方式挂载，CSV 写入宿主机的 `domain_url_results/`。

### 3.4 容器等待和清理

`wait_domain_attempt()` 从容器实际启动时间计算剩余硬超时：

```text
Worker 正常退出
└─ 返回 Worker 退出码

Worker 超时且 requested=1 数量有新增
├─ 保留已写入进度
└─ 将当前尝试视为完成

Worker 超时且 requested=1 数量零新增
└─ 返回退出码 124
```

无论正常退出还是超时，都会删除临时容器。URL 一旦原子领取即保持 `requested=1`，不会因容器失败恢复为 0。

### 3.5 单域名完成条件

节点循环结束后检查 CSV：

```text
CSV 去重后的 URL 数量 >= CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN
└─ 域名完成

CSV 去重后的 URL 数量 < CONFIG_MIN_UNIQUE_URLS_PER_DOMAIN
└─ 域名未完成，日志同时输出当前不同 URL 数和剩余未请求数
```

当前 `CONFIG_RETRIES_PER_SOURCE_IP = 1`，每个节点最多启动一次容器尝试。

## 四、容器 Worker 流程

入口函数为 `run_worker()`：

```text
run_worker()
│
├─ 创建 Worker HOME 和 TMPDIR
├─ 从环境变量读取域名、输出路径、节点和领取数量
├─ 删除本次首页失败详情临时文件
│
├─ subprocess.run()
│  └─ python -m scrapy crawl trace
│
├─ Scrapy 非零退出：抛出异常
└─ Scrapy 正常退出：记录 CSV 总数、requested 新增数和未请求数量
```

Worker 不再创建或读取 SQLite 文件，所有 URL 状态变化都直接通过 `AtomicCsvUrlState` 原子写入 CSV。

## 五、Scrapy URL 遍历

Spider 为 `trace_spider.spiders.trace.TraceSpider`。

### 5.1 Spider 初始化

Spider 启动时：

1. 校验宿主机传入的所有参数。
2. 创建 `AtomicCsvUrlState`，自动迁移并规范化 CSV。
3. 从项目根目录的 `exclude_keywords` 文件读取排除关键词。
4. 原子删除旧 CSV 中命中排除关键词的非首页候选，避免未请求 URL 被误标为 `requested=1`。
5. 将 `https://<hostname>/` 固定为 CSV 第 1 行；旧 CSV 第 1 行不会改变首页定义。
6. 将 CSV 中所有已记录 URL 加载到 `collected_urls`。
7. 从 `AtomicCsvUrlState.homepage_url` 读取固定的种子首页 URL。

### 5.2 初始请求

`start_requests()` 执行：

```text
存在 requested=0 URL
└─ 从 CSV 原子领取 claim_limit 条 URL 并设置 requested=1
```

首页请求使用更高的 Scrapy priority。

### 5.3 URL 规则

所有 URL 都通过 `normalize_page_url()`：

- 只接受 `http` 和 `https`。
- 只接受目标域名本身或其子域名。
- 使用当前页面地址补全相对 URL。
- 合并路径中的重复斜杠。
- 移除 URL fragment。
- 移除 `utm_*`、`fbclid`、`gclid`、`mc_cid` 和 `mc_eid`。
- 移除默认的 80/443 端口表示。
- 排除图片、视频、音频、压缩包、脚本、样式、字体、文档、数据库、JSON、XML 等资源后缀。
- 排除包含 `exclude_keywords` 中任一关键词的 URL。

URL 通过规则后，`ensure_and_claim_candidate()` 在文件锁内执行一次原子操作：URL 不存在时新增，并直接写为 `requested=1`；URL 已存在且为 0 时改为 1；已为 1 时不再创建重复请求。

### 5.4 页面解析

`parse()` 的执行流程：

```text
parse(response)
│
├─ 规范化最终 URL 和原请求 URL
├─ 提取全部 a::attr(href)
├─ 对新链接执行 URL 规则和原子 CSV 领取
├─ 新 href 候选通过原子 CSV 操作新增并设置 requested=1
├─ 最终跳转 URL 不自动成为新的候选记录
└─ 返回新建的 Scrapy Request
```

Spider 会继续调度当前页面新发现的链接，因此 Worker 不只处理启动时领取的 URL，还可能在同一个浏览器会话中继续深度遍历新链接。

## 六、Chrome 请求流程

Worker 模式启用 `ChromeCollectorDownloaderMiddleware`，每个 Worker 创建并复用一个 Selenium Chrome 会话。

```text
process_request(request)
│
├─ wait_for_node_request_slot()
│     保证同一域名、同一节点的请求启动间隔 >= 120 秒，
│     避免该节点的出口 IP 因页面请求过密触发风控
│
├─ fetch(browser, request.url)
│  ├─ 清空旧 performance log
│  ├─ browser.get(url)
│  ├─ 超时时执行 window.stop()
│  ├─ 获取最终跳转 URL
│  ├─ 从 performance log 获取主文档响应
│  ├─ 校验 HTTP 状态码为 200～399
│  ├─ 读取页面 MIME 类型和正文
│  └─ 校验正文不超过 5 MB
│
├─ MIME 是 text/html 或 application/xhtml+xml
│  └─ 构造 HtmlResponse 交给 Spider
│
└─ 请求失败或 MIME 不符合要求
   ├─ requested 保持 1
   ├─ 首页请求失败时记录失败详情
   └─ 抛出 IgnoreRequest
```

同一节点的上次请求启动时间保存在 `域名.csv.node_xx.request_time` 侧车文件中，并使用 `flock`、`fsync` 进行原子更新。因此即使容器被删除并重新创建，120 秒间隔仍然有效。这个间隔是出口 IP 风控规避策略，不是为了限制程序性能；目的是避免同一节点请求页面过快而触发 IP 风控。不同节点使用不同 `node_key`，可以同时请求。

当前 `CONFIG_REQUEST_ATTEMPTS_PER_CONTAINER = 1`，所以每条 URL 在当前容器内只请求一次。

## 七、CSV 状态流转

每个域名只使用独立 CSV 保存 URL 状态：

```csv
id,url,domain,requested
1,https://example.com/,example.com,0
2,https://example.com/about,example.com,1
```

字段含义：

- `id`：按 CSV 当前顺序重新生成的连续编号。
- `url`：种子首页或页面 `<a href>` 提取出的候选 URL。
- `domain`：该 CSV 对应的配置 hostname。
- `requested`：`0` 表示尚未领取，`1` 表示已被原子领取并安排请求。

状态变化：

```text
任务初始化时的种子首页 URL
└─ requested=0

旧三字段 CSV 中的 URL
└─ 迁移为 requested=0

Worker 原子领取 URL
└─ requested: 0 -> 1

页面提取新的 href URL
└─ 原子新增 requested=1，并立即安排 Scrapy Request

Chrome 请求成功或失败
└─ requested 保持 1，不记录第二套状态
```

`requested=1` 表示该 URL 已被原子领取并安排请求。代码不再记录 `pending/success/failed`、`claim_owner`、`last_error` 或 `final_url` 持久化状态。

历史 `.crawl_state.sqlite3` 文件不会再被代码读取、更新或删除；如需清理这些旧文件，应在确认不再需要回退后单独处理。

## 八、CSV 生成流程

`AtomicCsvUrlState` 的每次修改都重新生成完整 CSV：

```text
按发现顺序读取当前 CSV 候选 URL
将固定种子首页 URL 放到第 1 行
截取前 1000 条
写入 requested=0/1
写入临时文件并 fsync
原子替换正式 CSV
```

写入过程使用独立的 `.csv.lock` 文件和 `fcntl.flock()`，避免多个容器同时同步时互相覆盖。

因此：

- CSV 是 URL 集合和请求状态的唯一来源。
- CSV 包含种子首页和通过 URL 规则的页面 `<a href>` 候选。
- `requested=1` 只表示已领取并安排请求，不表示请求成功。
- CSV 第 1 行固定为配置域名的种子首页 URL；即使该请求发生跳转，首页仍是首次请求 URL，而不是最终跳转 URL。

## 九、当前实现的关键实际行为

### 9.1 失败 URL 不会跨节点重试

URL 被 Worker 原子领取后立即写为 `requested=1`。无论 Chrome 请求成功、失败或容器随后异常，该 URL 都不会再交给其他节点。

当前 19 节点的作用是并发分配多条 `requested=0` URL，而不是让同一条失败 URL 依次尝试 19 个节点。

### 9.2 新链接通常由发现它的 Worker 继续处理

Spider 解析页面时，会原子新增、标记并调度新发现的链接。这些新链接不受 Worker 启动时 `claim_limit` 的再次分配，因此单个 Worker 可能继续遍历大量新 URL。

多个节点并发主要发生在 Worker 启动前 CSV 已经存在多条 `requested=0` URL 时。

### 9.3 域名之间不并发

虽然单域名可以启动多个节点 Worker，但 `run_host()` 会等待当前域名结束后才进入下一个域名。

### 9.4 候选数量实际受 1000 限制

Spider 新建 URL 状态时使用：

```text
min(CONFIG_URLS_PER_DOMAIN, CONFIG_MAX_CANDIDATES_PER_DOMAIN)
```

当前配置为 `min(1000, 10000)`，所以新发现候选的实际状态总量上限是 1000。

### 9.5 CSV 不记录未提取的重定向目标

访问候选 URL 时发生跳转，不持久化最终 URL。重定向目标不会自动进入 CSV，避免 CSV 混入并非从页面链接提取的地址。

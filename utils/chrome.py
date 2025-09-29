import json
import re
import time
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
from tools.math_tool import generate_normal_random
from utils.task import task_instance
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, JavascriptException
from utils.logger import logger

JS_SELECT_ALL_AND_COPY_CAPTURE = r"""
function __select_all_and_copy_capture(){
  try{
    const sel = window.getSelection();
    // 备份原选区
    const saved = [];
    for (let i=0;i<sel.rangeCount;i++){ saved.push(sel.getRangeAt(i).cloneRange()); }
    function restore(){
      sel.removeAllRanges();
      for (const r of saved) sel.addRange(r);
    }
    // Ctrl+A：全选 <body>（尽量贴近浏览器行为）
    sel.removeAllRanges();
    const root = document.body || document.documentElement;
    const range = document.createRange();
    range.selectNodeContents(root);
    sel.addRange(range);

    function selectionPlain(){ return sel.toString(); }
    function selectionHTML(){
      const box = document.createElement('div');
      for (let i=0;i<sel.rangeCount;i++) box.appendChild(sel.getRangeAt(i).cloneContents());
      return box.innerHTML;
    }
    const defaultPlain = selectionPlain();
    const defaultHtml  = selectionHTML();

    // 监听 copy，尽量捕获站点可能改写的内容（若站点在 copy 里 setData）
    let copiedPlain = null, copiedHtml = null;
    function onCopyCapture(e){ /* 预留 */ }
    function onCopyBubble(e){
      try{ copiedHtml  = e.clipboardData.getData('text/html')  || null; }catch(_){}
      try{ copiedPlain = e.clipboardData.getData('text/plain') || null; }catch(_){}
    }
    document.addEventListener('copy', onCopyCapture, true);
    document.addEventListener('copy', onCopyBubble, false);

    let execOk = false;
    try { execOk = document.execCommand('copy'); } catch(_){}

    document.removeEventListener('copy', onCopyCapture, true);
    document.removeEventListener('copy', onCopyBubble, false);
    restore();

    // 如果站点没改写，则 copied* 可能是空，就用默认选区内容兜底
    return {
      execOk,
      plain: copiedPlain  != null && copiedPlain  !== '' ? copiedPlain  : defaultPlain,
      html:  copiedHtml   != null && copiedHtml   !== '' ? copiedHtml   : defaultHtml,
      // 也把默认的带上，便于对比
      _defaultPlain: defaultPlain,
      _defaultHtml:  defaultHtml
    };
  }catch(e){
    return { error: String(e) };
  }
}
"""

def is_docker():
    # 检查cgroup文件
    try:
        with open('/proc/1/cgroup', 'r') as f:
            for line in f:
                if 'docker' in line or 'kubepods' in line:
                    return True
    except FileNotFoundError:
        pass

    # 检查环境变量
    if os.path.exists('/.dockerenv'):
        return True

    return False


def create_chrome_driver():
    # 在当前目录中创建download文件夹
    download_folder = os.path.join(os.getcwd(), 'download')
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    # 创建 ChromeOptions 实例
    chrome_options = Options()
    os.environ["SE_OFFLINE"] = "true"
    _ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9"
    _LANG_PRIMARY = "zh-CN"
    chrome_options.binary_location = "/usr/bin/google-chrome"  # 固定 Chrome 路径，避免联网查询
    chrome_options.add_argument('--headless')  # 无界面模式
    chrome_options.add_argument("--disable-gpu")  # 禁用 GPU 加速
    chrome_options.add_argument("--no-sandbox")  # 禁用沙盒
    chrome_options.add_argument("--disable-dev-shm-usage")  # 限制使用/dev/shm
    chrome_options.add_argument("--incognito")  # 隐身模式
    chrome_options.add_argument("--disable-application-cache")  # 禁用应用缓存
    chrome_options.add_argument("--disable-extensions")  # 禁用扩展
    chrome_options.add_argument("--disable-infobars")  # 禁用信息栏
    chrome_options.add_argument("--disable-software-rasterizer")  # 禁用软件光栅化
    chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")  # 允许自动播放
    chrome_options.add_argument(f"--lang={_LANG_PRIMARY}") # ✅ 启动语言
    chrome_options.add_argument(f"--ssl-key-log-file={task_instance.ssl_key_path}")  # 设置 SSL 密钥日志文件路径
    chrome_options.add_argument("--disable-background-networking")  # 降低背景“噪音”联网
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--homepage=about:blank")
    chrome_options.add_argument("--log-net-log=/tmp/netlog.json")
    chrome_options.add_argument("--net-log-capture-mode=Everything")
    print(f"SSL 密钥日志文件路径: {task_instance.ssl_key_path}")
    # chrome_options.add_argument(f'--proxy-server=http://127.0.0.1:7890')

    # 设置实验性首选项
    prefs = {
        "profile.default_content_settings.popups": 0,
        "credentials_enable_service": False,  # 禁用密码管理器弹窗
        "profile.password_manager_enabled": False,  # 禁用密码管理器
        "download.default_directory": download_folder,  # 默认下载目录
        "download.prompt_for_download": False,  # 不提示下载
        "download.directory_upgrade": True,  # 升级下载目录
        "safebrowsing.enabled": True,  # 启用安全浏览
        "intl.accept_languages": _ACCEPT_LANGUAGE,  # ✅ 首选语言
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # 启用性能日志记录
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # 创建 WebDriver 实例
    service = Service(executable_path="/usr/local/bin/chromedriver")
    browser = webdriver.Chrome(service=service, options=chrome_options)
    browser.execute_cdp_cmd('Network.enable', {})
    # browser.execute_cdp_cmd('Network.setBlockedURLs',
    #                         {
    #                             'urls': ['*://plausible.io/*', '*://*.plausible.io/*']
    #                         })
    browser.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': {'Accept-Language': _ACCEPT_LANGUAGE}})
    browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                            {'source': '''
                            Object.defineProperty(navigator,"webdriver",{get:()=>undefined});
                            Object.defineProperty(navigator,"language",{get:()=> "zh-CN"});
                            Object.defineProperty(navigator,"languages",{get:()=> ["zh-CN","zh"]});
                            '''.strip()})
    return browser

def open_url_and_save_content(driver, url, wait_secs=20):
    """
    1) 尝试进入 interactive/complete
    2) 等待 DOM 短暂稳定
    3) 若仍然超时，强制 stopLoading，尽力保存当前内容
    """
    # 可选：缩短脚本执行超时，避免挂死
    driver.set_script_timeout(max(10, wait_secs))

    driver.get(url)

    # 第一步：不强求 complete，先到 interactive/complete
    try:
        WebDriverWait(driver, max(5, wait_secs // 2)).until(
            lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
        )
    except TimeoutException as e:
        # 忽略，进入下一阶段稳定性等待
        logger.warning(f"等待 readyState 失败，进入下一阶段：{e}")

    # 第二步：等待 DOM 短暂稳定（文本长度不再增长）
    state = wait_until_ready_or_stable(driver, max_wait=wait_secs, min_stable_time=1.0, poll=0.25)

    # 若还是不行，第三步：强制停载，尽力保存
    if state not in ("interactive", "complete"):
        try:
            driver.execute_cdp_cmd("Page.stopLoading", {})
        except Exception as e:
            logger.warning(f"强制 stopLoading 失败，继续保存：{e}")

    # 轻微喘口气，保证同步任务（如布局、微任务队列）落地
    time.sleep(1.0)

    # 之后与你原来的逻辑一致：执行全选复制 + 落盘
    script = JS_SELECT_ALL_AND_COPY_CAPTURE + "\nreturn __select_all_and_copy_capture();"
    res = driver.execute_script(script)
    if not isinstance(res, dict) or res.get("error"):
        raise RuntimeError(f"JS失败: {res}")

    plain = re.sub(
        r'(?:[ \t\f\u00A0\u3000\u200B\u200C\u200D\uFEFF\u2060\u00AD\v]*\r?\n)+',
        '\n',
        res.get("plain", "")
    )
    os.makedirs(os.path.dirname(task_instance.content_path), exist_ok=True)
    with open(task_instance.content_path, "w", encoding="utf-8") as f:
        f.write(plain)

    html = driver.page_source  # 当前 DOM（含动态渲染结果）
    os.makedirs(os.path.dirname(task_instance.html_path), exist_ok=True)
    with open(task_instance.html_path, "w", encoding="utf-8") as f:
        f.write(html)

def wait_until_ready_or_stable(driver, max_wait=25, min_stable_time=1.0, poll=0.25):
    """
    认为页面“可用”的条件：
      1) readyState ∈ {interactive, complete}
      2) body.innerText.length 在 min_stable_time 时间内保持稳定
    这样能覆盖大量永不到 complete 的页面，也能等一等 SPA 首屏渲染。
    """
    deadline = time.time() + max_wait
    last_len = None
    stable_since = None
    last_state = None

    while time.time() < deadline:
        try:
            state = driver.execute_script("return document.readyState")
        except JavascriptException:
            state = None

        try:
            length = driver.execute_script(
                "return (document.body && document.body.innerText) ? document.body.innerText.length : 0;"
            )
        except JavascriptException:
            length = 0

        if state in ("interactive", "complete"):
            if last_len == length:
                # 开始累计“稳定”时长
                if stable_since is None:
                    stable_since = time.time()
                elif (time.time() - stable_since) >= min_stable_time:
                    return state
            else:
                stable_since = None
                last_len = length

        last_state = state
        time.sleep(poll)

    return last_state  # 返回最后一次看到的状态，供上层决策

# 定义一个函数来滚动页面
def scroll_to_bottom(driver):
    times = 0
    last_height = driver.execute_script("return document.body.scrollHeight")
    is_continue = True
    while is_continue:
        times += 1

        delay = generate_normal_random() / times
        # print(f'加载等待延时: {delay}')
        time.sleep(delay)

        # 滚动到页面底部
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # 使用显式等待等待页面加载新内容
        try:
            WebDriverWait(driver, 2).until(
                lambda d: d.execute_script("return document.body.scrollHeight") > last_height
            )
        except:
            is_continue = False

        # 计算新的滚动高度并与最后的高度进行比较
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height or times == 100:
            is_continue = False
        last_height = new_height


def add_cookies(browser):
    with open("youtube_cookie.txt", "r", encoding="utf-8") as f:
        raw_cookies = json.load(f)

    for ck in raw_cookies:
        try:
            browser.add_cookie(sanitize(ck))
        except Exception as e:
            print("跳过无效 cookie:", ck["name"], e)

def sanitize(raw: dict) -> dict:
    """把 DevTools 导出的 cookie → Selenium 可接受格式"""
    c = {}

    # ===== 必选键 =====
    c["name"] = raw["name"]
    c["value"] = raw["value"]

    # ===== 可选键 =====
    if "domain" in raw:
        c["domain"] = raw["domain"].lstrip(".")  # 去掉前导点
    c["path"] = raw.get("path", "/")

    # secure / httpOnly
    c["secure"] = bool(raw.get("secure", False))
    c["httpOnly"] = bool(raw.get("httpOnly", False))

    # SameSite：枚举映射
    samesite_map = {"no_restriction": "None", "unspecified": None,  # 直接忽略
                    "lax": "Lax", "strict": "Strict", "none": "None", }
    ss = raw.get("sameSite")
    ss_fixed = samesite_map.get(str(ss).lower())
    if ss_fixed:
        c["sameSite"] = ss_fixed

    # expiry
    if "expirationDate" in raw:
        c["expiry"] = int(raw["expirationDate"])
    elif "expiry" in raw:
        c["expiry"] = int(raw["expiry"])

    return c
# 使用示例
# browser = create_chrome_driver()
# # ... 你的其他浏览器自动化任务
# browser.quit()

import json
import re
import time
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
from selenium.webdriver.support.ui import WebDriverWait  # 从selenium.webdriver.support.wait改为支持ui
from tools.math_tool import generate_normal_random
from utils.task import task_instance
import base64
from pathlib import Path
from typing import Optional

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
    browser.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': {'Accept-Language': _ACCEPT_LANGUAGE}})
    browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                            {'source': '''
                            Object.defineProperty(navigator,"webdriver",{get:()=>undefined});
                            Object.defineProperty(navigator,"language",{get:()=> "zh-CN"});
                            Object.defineProperty(navigator,"languages",{get:()=> ["zh-CN","zh"]});
                            '''.strip()})
    return browser

def open_url_and_save_content(driver, url, wait_secs=8):
    driver.get(url)
    WebDriverWait(driver, wait_secs).until(lambda d: d.execute_script("return document.readyState") == "complete")
    time.sleep(15)
    screenshot_full_page(driver, Path(task_instance.screenshot_path), dpr=2.0)
    script = JS_SELECT_ALL_AND_COPY_CAPTURE + "\nreturn __select_all_and_copy_capture();"
    res = driver.execute_script(script)
    if not isinstance(res, dict) or res.get("error"):
        raise RuntimeError(f"JS失败: {res}")
    plain = re.sub(r'(?:[ \t\f\u00A0\u3000\u200B\u200C\u200D\uFEFF\u2060\u00AD\v]*\r?\n)+', '\n', res.get("plain", ""))
    if not os.path.exists(os.path.dirname(task_instance.content_path)):
        os.makedirs(os.path.dirname(task_instance.content_path))
    with open(task_instance.content_path, "w", encoding="utf-8") as f:
        f.write(plain)
    html = driver.page_source  # 此刻的 DOM（包含已渲染的动态内容）
    if not os.path.exists(os.path.dirname(task_instance.html_path)):
        os.makedirs(os.path.dirname(task_instance.html_path))
    with open(task_instance.html_path, "w", encoding="utf-8") as f:
        f.write(html)

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

def screenshot_full_page(driver: webdriver.Chrome, out_path: Path, dpr: Optional[float] = None) -> None:
    """整页长截图：通过 CDP 获取内容尺寸并原生捕获，不做滚动拼接。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 计算页面内容尺寸
    metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    # contentSize 比 visualViewport 更可靠，含整个文档内容区域
    content_size = metrics.get("contentSize", {})
    width = int(math.ceil(content_size.get("width", 0) or 0))
    height = int(math.ceil(content_size.get("height", 0) or 0))
    if width == 0 or height == 0:
        # 退路：用 JS 获取 body 尺寸
        width = int(driver.execute_script("return Math.ceil(document.documentElement.scrollWidth||document.body.scrollWidth||0);"))
        height = int(driver.execute_script("return Math.ceil(document.documentElement.scrollHeight||document.body.scrollHeight||0);"))

    device_scale = float(dpr) if dpr and dpr > 0 else 1.0

    # 覆盖设备度量，扩大视窗到整页尺寸
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "mobile": False,
        "width": width,
        "height": height,
        "deviceScaleFactor": device_scale,
        "screenOrientation": {"type": "landscapePrimary", "angle": 0},
    })

    # 捕获位图（b64）
    data = driver.execute_cdp_cmd("Page.captureScreenshot", {
        "fromSurface": True,
        "captureBeyondViewport": True
    })
    png_b64 = data.get("data")
    out_path.write_bytes(base64.b64decode(png_b64))

    # 恢复度量，避免影响后续操作
    driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})

def add_cookies(browser, raw_cookies):
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

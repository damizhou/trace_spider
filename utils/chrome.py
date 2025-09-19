import json
import time
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
from selenium.webdriver.support.ui import WebDriverWait  # 从selenium.webdriver.support.wait改为支持ui
from tools.math_tool import generate_normal_random
from utils.task import task_instance

JS_EXTRACT_ALL_READABLE = r"""
function __extract_all_readable(){
  const minFontPx = 8; // 小于该字号视为不可读
  const BLACK = new Set(['script','style','noscript','template','pre','code','head','meta','link','title']);
  const vw = window.innerWidth || document.documentElement.clientWidth;
  const vh = window.innerHeight || document.documentElement.clientHeight;

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const uniq = arr => Array.from(new Set(arr));

  function inBlacklist(el){
    for (let n = el; n; n = n.parentElement){
      if (n.nodeType !== 1) break;
      const tag = (n.tagName||'').toLowerCase();
      if (BLACK.has(tag)) return true;
      if (n.hasAttribute('aria-hidden') && n.getAttribute('aria-hidden') === 'true') return true;
      if (n.hidden) return true;
    }
    return false;
  }

  function visibleByStyle(el){
    for (let n = el; n; n = n.parentElement){
      if (n.nodeType !== 1) break;
      const cs = window.getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse') return false;
      if (parseFloat(cs.opacity) < 0.05) return false;
      if (n === el && parseFloat(cs.fontSize) > 0 && parseFloat(cs.fontSize) < minFontPx) return false;
    }
    return true;
  }

  function rectIntersectsViewport(r){
    return !(r.right <= 0 || r.bottom <= 0 || r.left >= vw || r.top >= vh);
  }

  function hitTest(node, r){
    const pts = [
      [r.left + r.width/2, r.top + r.height/2],
      [r.left + Math.min(6, r.width*0.2), r.top + Math.min(6, r.height*0.5)],
      [r.right - Math.min(6, r.width*0.2), r.bottom - Math.min(6, r.height*0.5)]
    ];
    const p = node.parentElement;
    for (const [x0,y0] of pts){
      const x = clamp(x0, 0, vw-1), y = clamp(y0, 0, vh-1);
      const topEl = document.elementFromPoint(x, y);
      if (p && topEl && (topEl === p || p.contains(topEl))) return true;
    }
    return false;
  }

  function textNodeVisible(node){
    const range = document.createRange();
    range.selectNodeContents(node);
    const rects = range.getClientRects();
    for (const r of rects){
      if (r.width <= 0 || r.height <= 0) continue;
      if (!rectIntersectsViewport(r)) continue;   // 只要与视口相交
      if (hitTest(node, r)) return true;          // 且没有被遮挡
    }
    return false;
  }

  function looksLikeCodeLine(s, parent){
    if (!s) return false;
    const t = s.trim();
    if (t.length < 2) return false;

    // 等宽字体强指示
    try {
      const fam = window.getComputedStyle(parent).fontFamily || '';
      if (/\bmonospace\b/i.test(fam)) return true;
    } catch(e){}

    // JSON-ish
    if (/^\s*[{[]\s*(".+?"|[A-Za-z0-9_'"-]+)\s*:/.test(t)) return true;

    // 符号密度（把 '-' 放末尾避免范围解释）
    const sym = (t.match(/[{}\[\]();,<>!=+*\/%|&\-]/g) || []).length;
    const ratio = sym / Math.max(1, t.length);
    const kw = /\b(function|return|var|let|const|class|import|from|export|new|if|else|switch|case|break|continue|null|true|false|undefined|async|await|try|catch|throw)\b/.test(t);
    if ((ratio > 0.18 && kw) || ratio > 0.28) return true;

    // 疑似 hash/base64 的长 token
    if (t.split(/\s+/).some(tok => tok.length >= 40 && /[A-Za-z0-9+/_=-]{40,}/.test(tok))) return true;

    return false;
  }

  function gather(doc){
    const out = [];
    const walker = doc.createTreeWalker(doc, NodeFilter.SHOW_TEXT, {
      acceptNode(node){
        const raw = node.nodeValue || '';
        if (!/\S/.test(raw)) return NodeFilter.FILTER_REJECT;

        const p = node.parentElement;
        if (!p) return NodeFilter.FILTER_REJECT;
        if (inBlacklist(p)) return NodeFilter.FILTER_REJECT;
        if (!visibleByStyle(p)) return NodeFilter.FILTER_REJECT;

        if (!textNodeVisible(node)) return NodeFilter.FILTER_REJECT; // ← 固定只首屏

        const txt = raw.replace(/\s+/g,' ').trim();
        if (!txt) return NodeFilter.FILTER_REJECT;
        if (looksLikeCodeLine(txt, p)) return NodeFilter.FILTER_REJECT;

        return NodeFilter.FILTER_ACCEPT;
      }
    });

    let n;
    while ((n = walker.nextNode())){
      const s = n.nodeValue.replace(/\s+/g,' ').trim();
      if (!s) continue;
      if (s.length > 8000) continue;
      if (s.split(/\s+/).some(tok => tok.length > 300)) continue;
      out.push(s);
    }
    return uniq(out);
  }

  function sameOriginDocs(doc){
    const arr = [doc];
    const ifr = Array.from(doc.querySelectorAll('iframe'));
    for (const f of ifr){
      try { if (f.contentDocument) arr.push(f.contentDocument); } catch(e){}
    }
    return arr;
  }

  let lines = [];
  for (const d of sameOriginDocs(document)){
    try { lines = lines.concat(gather(d)); } catch(e){}
  }
  return uniq(lines);
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

def open_url_and_save_content(driver, url, wait_secs=8):
    driver.get(url)
    WebDriverWait(driver, wait_secs).until(lambda d: d.execute_script("return document.readyState") == "complete")
    script = JS_EXTRACT_ALL_READABLE + "\nreturn __extract_all_readable();"
    try:
        res = driver.execute_script(script) or {"textLines": [], "blocks": []}
    except Exception as e:
        # 兜底：输出前 200 字符便于你定位是哪一段导致解析问题
        raise RuntimeError(f"JS 执行失败: {e}")

    lines = res.get("textLines", []) or []
    cleaned = []
    for s in lines:
        s = " ".join(s.split())
        if not s:
            continue
        if any(len(tok) > 300 for tok in s.split()):
            continue
        cleaned.append(s)
    if not os.path.exists(os.path.dirname(task_instance.content_path)):
        os.makedirs(os.path.dirname(task_instance.content_path))
    with open(task_instance.content_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))
    html = driver.page_source  # 此刻的 DOM（包含已渲染的动态内容）
    if not os.path.exists(os.path.dirname(task_instance.html_path)):
        os.makedirs(os.path.dirname(task_instance.html_path))
    with open(task_instance.html_path, "w", encoding="utf-8") as f:
        f.write(html)
    time.sleep(3)

    os.chown(task_instance.content_path, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))

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

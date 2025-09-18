import json
import time
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
from selenium.webdriver.support.ui import WebDriverWait  # 从selenium.webdriver.support.wait改为支持ui
from tools.math_tool import generate_normal_random
from utils.task import task_instance

JS_RULE_BASED_EXTRACTION = r"""
function __extract_like_immersive(){
  // ---------- 规则：显式列出，避免空选择器 ----------
  const RULES = [
    {
      host:/github\.com$/,
      selectors:['.markdown-body','#readme','.repository-content'],
      excludeSelectors:[
        'nav','.Header','.file-navigation','footer','.footer','.cookie-banner',
        '.js-pinned-issue-list-item','.file'
      ],
      stayOriginalSelectors:['pre','code','.blob-code','table.highlight','.highlight','.CodeMirror','.ace_content','.gist']
    },
    {
      host:/wikipedia\.org$/,
      selectors:['#content','#mw-content-text','article'],
      excludeSelectors:[
        '#mw-navigation','#footer','#toc','.toc','.infobox','.navbox',
        '.catlinks','.mw-editsection','.mw-jump-link'
      ],
      stayOriginalSelectors:['pre','code','table','figure .thumb']
    },
    {
      host:/.*/,
      selectors:[
        'article','main','[role="main"]','.article','.post','.entry','.content',
        '.post-content','.markdown-body','.wiki-content','#content','#main'
      ],
      excludeSelectors:[
        'nav','footer','header','aside','.aside','.sidebar','.widget',
        '.breadcrumb','.breadcrumbs','.crumb','.toc','#toc','.menu','.toolbar',
        '.advert','.ads','.ad','.sponsor','.cookie','.subscribe','.newsletter',
        '.share','.overlay','.popup','.modal','.dialog','[aria-hidden="true"]','[hidden]'
      ],
      stayOriginalSelectors:['pre','code','samp','kbd','.hljs','.prettyprint','.syntax','.gist','.CodeMirror','.ace_content']
    }
  ];

  // ---------- 工具：容错 ----------
  const uniq = a => Array.from(new Set(a));
  const sanitize = arr => uniq((arr||[]).filter(s => typeof s === 'string' && s.trim()));
  const qsa = (root, sel) => {
    if (!sel || typeof sel !== 'string' || !sel.trim()) return [];
    try { return Array.from(root.querySelectorAll(sel)); } catch (e) { return []; }
  };

  const matchRule = h => {
    const r = RULES.find(r => r.host.test(h)) || RULES[RULES.length-1];
    // 每次使用前清洗一次，彻底去掉空/非法
    r.selectors = sanitize(r.selectors);
    r.excludeSelectors = sanitize(r.excludeSelectors);
    r.stayOriginalSelectors = sanitize(r.stayOriginalSelectors);
    return r;
  };

  const isExcluded = (el, excludes) => {
    for (const sel of excludes) {
      if (!sel) continue;
      try { if (el.closest(sel)) return true; } catch(e) {}
    }
    return false;
  };

  const isStayOriginal = (el, stays) => {
    for (const sel of stays) {
      if (!sel) continue;
      try { if (el.closest(sel)) return true; } catch(e) {}
    }
    return false;
  };

  const scoreContainer = (el) => {
    const t = (el.innerText||'').replace(/\s+/g,' ').trim();
    if (!t) return 0;
    const total = t.length;
    const linkText = qsa(el,'a').reduce((a,x)=>a+((x.innerText||'').length),0);
    const linkRatio = total ? linkText/total : 0;
    let d=0,n=el; while(n && d<10){ n=n.parentElement; d++; }
    return Math.max(0, total*(1-Math.min(0.9,linkRatio))/(1+d*0.1));
  };

  function pickMain(doc, rule){
    let c = [];
    for (const sel of rule.selectors) c.push(...qsa(doc, sel));
    c = uniq(c).filter(el => !isExcluded(el, rule.excludeSelectors));
    if (c.length){ c.sort((a,b)=>scoreContainer(b)-scoreContainer(a)); return c[0]; }
    const fb = ['article','main','[role="main"]','.content','.post','.entry','#content','#main']
      .flatMap(sel => qsa(doc, sel));
    if (fb.length){ fb.sort((a,b)=>scoreContainer(b)-scoreContainer(a)); return fb[0]; }
    return doc.body || doc.documentElement;
  }

  function extractBlocks(root, rule){
    const BLOCKS = 'h1,h2,h3,h4,h5,h6,p,li,blockquote,figcaption,dd,dt,td';
    const nodes = qsa(root, BLOCKS)
      .filter(el => !isExcluded(el, rule.excludeSelectors))
      .filter(el => !isStayOriginal(el, rule.stayOriginalSelectors));
    const out = [];
    for (const el of nodes){
      const txt = (el.innerText||'').replace(/\s+/g,' ').trim();
      if (!txt) continue;

      // 代码/JSON 兜底过滤（把 '-' 放到类尾避免范围解析）
      const symCount = (txt.match(/[{}\[\]();,<>!=+*\/%|&\-]/g)||[]).length;
      const symRatio = symCount / Math.max(1, txt.length);
      const hasKW = /\b(function|return|var|let|const|class|import|from|export|new|if|else|switch|case|break|continue|null|true|false|undefined|async|await|try|catch|throw)\b/.test(txt);
      const looksJSON = /^\s*[{[]\s*(".+?"|[A-Za-z0-9_'"-]+)\s*:/.test(txt);
      if (looksJSON || (symRatio > 0.18 && hasKW)) continue;

      if (txt.length < 2 || txt.length > 5000) continue;
      out.push({ tag: el.tagName.toLowerCase(), text: txt });
    }
    const dedup = [];
    for (const b of out){ if (!dedup.length || dedup[dedup.length-1].text !== b.text) dedup.push(b); }
    return dedup;
  }

  function sameOriginIframes(doc){
    const frames = [];
    for (const f of qsa(doc, 'iframe')){
      try { if (f.contentDocument) frames.push(f.contentDocument); } catch(e){}
    }
    return frames;
  }

  function run(doc, rule){
    let main = pickMain(doc, rule);
    let blocks = extractBlocks(main, rule);
    if (blocks.length < 5){
      const whole = extractBlocks(doc.body || doc.documentElement, rule);
      if (whole.length > blocks.length + 3) blocks = whole;
    }
    return blocks;
  }

  const rule = matchRule(location.hostname);
  let results = run(document, rule);
  for (const idoc of sameOriginIframes(document)){
    try { const add = run(idoc, rule); if (add && add.length) results = results.concat(add); } catch(e){}
  }
  return { textLines: results.map(b=>b.text), blocks: results };
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
    script = JS_RULE_BASED_EXTRACTION + "\nreturn __extract_like_immersive();"
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

import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
from selenium.webdriver.support.ui import WebDriverWait  # 从selenium.webdriver.support.wait改为支持ui
from tools.math_tool import generate_normal_random
from utils.task import task_instance


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
    if is_docker():
        headless = True
    else:
        headless = False

    pcap_path = task_instance.pcap_path
    ssl_key_log_path = pcap_path.replace('data', 'ssl_keys').replace('.pcap', '_ssl_key.log')
    print('ssl_key_log_path', ssl_key_log_path)
    if headless:
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
    chrome_options.add_argument(f"--ssl-key-log-file={ssl_key_log_path}")  # 设置 SSL 密钥日志文件路径
    # chrome_options.add_argument(f'--proxy-server=http://127.0.0.1:7890')

    # 设置实验性首选项
    prefs = {
        "profile.default_content_settings.popups": 0,
        "credentials_enable_service": False,  # 禁用密码管理器弹窗
        "profile.password_manager_enabled": False,  # 禁用密码管理器
        "download.default_directory": download_folder,  # 默认下载目录
        "download.prompt_for_download": False,  # 不提示下载
        "download.directory_upgrade": True,  # 升级下载目录
        "safebrowsing.enabled": True  # 启用安全浏览
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # 启用性能日志记录
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # 创建 WebDriver 实例
    browser = webdriver.Chrome(options=chrome_options)
    browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                            {'source': 'Object.defineProperty(navigator,"webdriver",{get:()=>undefined})'})
    return browser


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

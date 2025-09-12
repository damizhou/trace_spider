from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
from datetime import datetime

def create_chrome_driver(task_name, formatted_time, parsers):
    current_time = datetime.now()
    current_data = current_time.strftime("%Y%m%d")
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ssl_key", current_data)
    os.makedirs(data_dir, exist_ok=True)
    filename = f'{parsers}_'

    ssl_key_file_path = os.path.join(data_dir, f"{filename}{formatted_time}_{task_name}_ssl_key.log")

    # 在当前目录中创建download文件夹
    download_folder = os.path.join(os.getcwd(), 'download')
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    _ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9"
    _LANG_PRIMARY = "zh-CN"

    # 创建 ChromeOptions 实例
    chrome_options = Options()

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
    chrome_options.add_argument(f"--ssl-key-log-file={ssl_key_file_path}")
    chrome_options.add_argument(f"--lang={_LANG_PRIMARY}") # ✅ 启动语言

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
    # 创建 WebDriver 实例
    browser = webdriver.Chrome(options=chrome_options)
    browser.execute_cdp_cmd('Network.enable', {})
    browser.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': {'Accept-Language': _ACCEPT_LANGUAGE}})
    browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                            {'source': '''
                            Object.defineProperty(navigator,"webdriver",{get:()=>undefined});
                            Object.defineProperty(navigator,"language",{get:()=> "zh-CN"});
                            Object.defineProperty(navigator,"languages",{get:()=> ["zh-CN","zh"]});
                            '''.strip()})
    return browser, ssl_key_file_path




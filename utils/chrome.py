from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_chrome_driver(*, headless=True):
    # 创建 ChromeOptions 实例
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless')  # 无界面模式
    chrome_options.add_argument("--disable-gpu")  # 禁用 GPU 加速
    chrome_options.add_argument("--no-sandbox")  # 禁用沙盒（在某些系统中需要）
    chrome_options.add_argument("--disable-dev-shm-usage")  # 限制使用/dev/shm
    chrome_options.add_argument("--incognito")  # 隐身模式
    chrome_options.add_argument("--disable-application-cache")  # 禁用应用缓存
    chrome_options.add_argument("--disable-extensions")  # 禁用扩展
    chrome_options.add_argument("--disable-infobars")  # 禁用信息栏

    # 设置实验性首选项
    prefs = {
        "profile.default_content_settings.popups": 0,
        "download.default_directory": "/path/to/download/directory",
        "credentials_enable_service": False,  # 禁用密码管理器弹窗
        "profile.password_manager_enabled": False  # 禁用密码管理器
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # 创建 WebDriver 实例
    browser = webdriver.Chrome(options=chrome_options)
    browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                            {'source': 'Object.defineProperty(navigator,"webdriver",{get:()=>undefined})'})
    return browser

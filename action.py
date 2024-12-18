import json
import os
import re
import subprocess
import sys
import random
from tools.math_tool import generate_normal_random
from utils.chrome import is_docker, create_chrome_driver
from utils.logger import logger, setup_url_logger
from utils.config import config
from scrapy.crawler import CrawlerProcess
from selenium.webdriver.common.by import By
from scrapy.utils.project import get_project_settings
from trace_spider.spiders.trace import TraceSpider
import threading
import time
from traffic.capture import capture, stop_capture
from datetime import datetime
from utils.task import task_instance

duration = int(config["spider"]["duration"])
process = CrawlerProcess(get_project_settings())
crawlers_timer = None


# 清除浏览器进程
def kill_chrome_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        logger.info(f"清理浏览器进程")
        subprocess.run(['sudo', 'pkill', '-f', 'chrome'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")

# 清理流量捕获进程
def kill_tcpdump_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        logger.info(f"清理流量捕获进程")
        subprocess.run(['sudo', 'pkill', '-f', 'tcpdump'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")


# 流量捕获进程
def traffic():
    # 获取当前时间
    current_time = datetime.now()
    # 格式化输出
    formatted_time = current_time.strftime("%Y%m%d_%H%M%S")
    allowed_domain = task_instance.current_allowed_domain
    capture(allowed_domain, formatted_time, sys.argv[1:])


# 停止爬虫
def stop_crawlers():
    logger.info("定时器触发，停止所有爬虫")
    global crawlers_timer
    for crawler in process.crawlers:
        crawler.stop()
    crawlers_timer = None


# 启动定时器
def stop_crawlers_after_delay():
    global crawlers_timer
    crawlers_timer = threading.Timer(duration, stop_crawlers)
    crawlers_timer.start()


# 取消定时器
def cancel_timer():
    global crawlers_timer
    if crawlers_timer is not None:
        logger.info(f"爬虫提前结束，关闭定时器")
        crawlers_timer.cancel()


# 启动爬虫
def start_spider():
    # 添加你要运行的爬虫
    process.crawl(TraceSpider)

    logger.info(f"开始爬取数据")
    # 开启定时器
    stop_crawlers_after_delay()
    # 启动爬虫
    process.start()


def start_task():
    kill_chrome_processes()
    kill_tcpdump_processes()
    time.sleep(5)
    # 开流量收集
    traffic_thread = threading.Thread(target=traffic)
    traffic_thread.start()

    dir_path = f'huggingface_data/Pots'
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    file_path = os.path.join(dir_path, 'pots_web.json')
    browser = create_chrome_driver()
    browser.get("https://huggingface.co/posts")
    # 5️⃣ 使用 XPath 定位按钮 (XPath 方法)
    button = browser.find_element(By.XPATH,
                                  '//button[contains(@class, "btn mx-4 w-48 text-smd") and contains(text(), "Load more")]')

    # 6️⃣ 确保按钮在视野内
    browser.execute_script("arguments[0].scrollIntoView(true);", button)
    # 5️⃣ 使用 XPath 提取所有 class="relative" 的HTML元素
    prelength = 0
    is_bottom = False
    while not is_bottom:
        try:
            elements = browser.find_elements(By.XPATH, '//*[@class="relative"]')
            print(f"第{len(elements) / 10}次提取内容，数量为{len(elements)}")
            for elenium in elements[-10:]:

                target_div = elenium.find_element(By.XPATH,
                                                  './/div[contains(@class, "relative overflow-hidden break-words px-4 text-smd/6")]')

                # 6️⃣ 提取该 div 中的所有文本内容 (包括所有的嵌套 span 和子元素的文本)
                text_content = target_div.text
                cleaned_content = re.sub(r'\n\s*\n+', '\n', text_content)
                cleaned_content = "\n".join([line.strip() for line in cleaned_content.splitlines()])
                # print("📘 主要的文本内容：\n", cleaned_content)

                # 7️⃣ 使用 XPath 提取该 div 中的所有链接 (a标签)
                links = target_div.find_elements(By.XPATH, './/a[@href]')

                # 8️⃣ 遍历所有的链接，获取链接的文本和URL
                extracted_links = []
                for link in links:
                    link_text = link.text
                    link_url = link.get_attribute('href')
                    extracted_links.append((link_text, link_url))

                # 9️⃣ 输出所有链接的文本和URL
                # for i, (link_text, link_url) in enumerate(extracted_links, start=1):
                #     print(f"🔗 链接 {i}:")
                #     print(f"  - 链接文本: {link_text}")
                #     print(f"  - 链接地址: {link_url}\n")

                # 🔥 组织数据
                data = {"content": cleaned_content, "links": extracted_links}

                # 🔥 保存为JSON文件, 'w') as f:
                with open(file_path, 'a', encoding='utf-8') as f:
                    json.dump(data, f)
                    f.write("\n")

            # 7️⃣ 单击按钮
            button.click()
            print("Clicked 'Load more' button")
            random_integer = random.randint(5, 15)  # 包括1和10
            time.sleep(generate_normal_random() + random_integer)
            elements = browser.find_elements(By.XPATH, '//*[@class="relative"]')
            if len(elements) == prelength:
                attemp_index = 0
                for i in range(5):
                    print("再次尝试点击按钮")
                    # 7️⃣ 单击按钮
                    button.click()
                    print("Clicked 'Load more' button")
                    random_integer = random.randint(5, 15)  # 包括1和10
                    time.sleep(generate_normal_random() + random_integer)
                    elements = browser.find_elements(By.XPATH, '//*[@class="relative"]')
                    if len(elements) == prelength:
                        attemp_index += 1

                if attemp_index == 5:
                    is_bottom = True
            prelength = len(elements)


        except Exception as e:
            print(f"❌ 发生错误: {e}")


    logger.info(f"爬取数据结束, 等待10秒.让浏览器加载完所有已请求的页面")
    time.sleep(10)


    kill_chrome_processes()
    logger.info(f"等待TCP结束挥手完成")
    # time.sleep(60)

    # 关流量收集
    logger.info(f"关流量收集")
    stop_capture()

    logger.info(f"{task_instance.current_start_url}流量收集结束，共爬取{task_instance.requesturlNum}个页面")
    kill_tcpdump_processes()
    cancel_timer()


if __name__ == "__main__":
    if is_docker():
        start_task()
    else:
        start_spider()

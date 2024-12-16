import os
import subprocess
import sys
from selenium.webdriver.common.by import By

from tools.math_tool import generate_normal_random
from utils.chrome import is_docker, create_chrome_driver, scroll_to_bottom
from utils.logger import logger, setup_url_logger
from utils.config import config
from scrapy.crawler import CrawlerProcess
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
    if duration > 0:
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
    index = 0
    traffic_thread.start()
    download_dir = "./download"  # 更改为您的实际下载路径
    original_filename = "README.md"
    original_filepath = os.path.join(download_dir, original_filename)
    # start_spider()
    with open('./huggingface_data/huggingface_dataset_text_url_list_chinese.txt', 'r') as f:
        urls = f.readlines()
    for url in urls:
        browser = create_chrome_driver()
        try:
            readme_uelr = url + '/raw/main/README.md'
            browser.get(readme_uelr)
            scroll_to_bottom(browser)
            raw_content = browser.find_element(By.TAG_NAME, 'pre').text
            file_name = url.split('/')[-1].replace('\n', '')
            print('file_name', file_name)
            logger.info(f"{file_name}的Readme爬取完成。当前第{index}个页面，剩余{len(urls) - index}个页面。")
            with open(f'./huggingface_data/Readmes/{file_name}.md', 'w', encoding='utf-8') as file:
                file.write(raw_content)
            index += 1
        except Exception as e:
            readme_uelr = url + '/resolve/main/README.md'
            browser.get(readme_uelr)
            file_name = url.split('/')[-1].replace('\n', '') + '.md'
            new_filepath = os.path.join(download_dir, file_name)
            is_download_finished = False
            while not is_download_finished:
                if os.path.exists(original_filepath):
                    is_download_finished = True
                    # 重命名文件
                    os.rename(original_filepath, new_filepath)
                    print(f"File renamed from {original_filename} to {new_filepath}")
                else:
                    time.sleep(generate_normal_random())

            logger.info(f"{file_name}的Readme爬取完成。当前第{index}个页面，剩余{len(urls) - index}个页面。")
            index += 1

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

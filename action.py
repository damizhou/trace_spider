import subprocess
import sys
from utils.chrome import create_chrome_driver, scroll_to_bottom
from utils.logger import logger
from utils.config import config
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from selenium.webdriver.common.by import By
import threading
import time
from traffic.capture import capture, stop_capture
from datetime import datetime
from utils.task import task_instance
import json

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


def start_task():
    kill_chrome_processes()
    kill_tcpdump_processes()
    time.sleep(5)
    # 开流量收集
    traffic_thread = threading.Thread(target=traffic)

    traffic_thread.start()
    browser = create_chrome_driver()
    with open('organizations_output_data.json', 'r', encoding='utf-8') as f:
        urls = json.load(f)
    index = 0
    data = []
    for url in urls:
        browser.get(url)
        logger.info(f"{browser.current_url}页面加载完成")
        user_profile = browser.find_element(By.XPATH, '//*[@id="user_profile"]')
        organization_name = user_profile.find_element(By.XPATH, './/h2[@class="user_login"]/a').text
        fa_star = user_profile.find_element(By.XPATH, './/div[@class="row"]/div[@class="user_value col-xs-9"]').text
        rank = user_profile.find_element(By.XPATH, './/div[@class="row"]/div[@class="user_value col-xs-7"]').text
        github_url = user_profile.find_element(By.XPATH,
                                               './/div[@class="row"]/div[@class="go_to_github col-xs-12"]/a').get_attribute(
            'href')

        organization_data = {'organization_name': organization_name, 'fa_star': fa_star, 'rank': rank,
                             'github_url': github_url}
        data.append(organization_data)
        print('organization_data', organization_data)



    logger.info(f"爬取数据结束, 等待10秒.让浏览器加载完所有已请求的页面")
    time.sleep(10)

    # 将数据保存为JSON格式的文件
    with open('organizations_detail_output_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    #
    kill_chrome_processes()
    logger.info(f"等待TCP结束挥手完成")
    time.sleep(60)

    # 关流量收集
    logger.info(f"关流量收集")
    stop_capture()

    logger.info(f"{task_instance.current_start_url}流量收集结束，共爬取{task_instance.requesturlNum}个页面")
    kill_tcpdump_processes()


if __name__ == "__main__":
    start_task()

import subprocess

from utils.chrome import is_docker
from utils.logger import logger
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
        result = subprocess.run(['sudo', 'pkill', '-f', 'chrome'], check=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")


# 流量捕获进程
def traffic():
    # 获取当前时间
    current_time = datetime.now()
    # 格式化输出
    formatted_time = current_time.strftime("%Y%m%d_%H_%M_%S")
    allowed_domain = task_instance.current_allowed_domain
    capture(allowed_domain, formatted_time)


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
    logger.info(f"清理浏览器进程")
    kill_chrome_processes()
    # 开流量收集
    traffic_thread = threading.Thread(target=traffic)

    traffic_thread.start()

    start_spider()
    logger.info(f"爬取数据结束, 等待10秒.让浏览器加载完所有已请求的页面")
    time.sleep(10)

    logger.info(f"清理浏览器进程")
    kill_chrome_processes()
    logger.info(f"等待TCP结束挥手完成")
    time.sleep(60)

    # 关流量收集
    logger.info(f"关流量收集")
    stop_capture()

    logger.info(f"{task_instance.current_start_url}流量收集结束，共爬取{task_instance.requesturlNum}个页面")
    cancel_timer()


if __name__ == "__main__":
    if is_docker():
        start_task()
    else:
        start_spider()

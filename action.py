import subprocess
import sys

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


# 清除浏览器进程
def kill_chrome_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        result = subprocess.run(['sudo', 'pkill', '-f', 'chrome'], check=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        print(result.stdout.decode('utf-8'))
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")


# 流量捕获进程
def traffic():
    # 获取当前时间
    current_time = datetime.now()
    # 格式化输出
    formatted_time = current_time.strftime("%Y%m%d%H%M%S")
    allowed_domain = task_instance.current_allowed_domain
    capture(allowed_domain, formatted_time)


# 启动爬虫
def start_spider():
    def stop_crawlers_after_delay(process, delay):
        def stop_crawlers():
            logger.info("定时器触发，停止所有爬虫")
            for crawler in process.crawlers:
                crawler.stop()

        timer = threading.Timer(delay, stop_crawlers)
        timer.start()

    process = CrawlerProcess(get_project_settings())

    # 添加你要运行的爬虫
    process.crawl(TraceSpider)

    logger.info(f"开始爬取数据")
    stop_crawlers_after_delay(process, duration)
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

    # 关流量收集
    logger.info(f"关流量收集")
    stop_capture()


if __name__ == "__main__":
    start_task()
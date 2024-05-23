import subprocess
from utils.logger import logger
from utils.config import config
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from trace_spider.spiders.trace import TraceSpider
import threading
import time
from traffic.capture import capture, stop_capture
from traffic.handle_traffic import pcap2flowlog
import queue
from datetime import datetime


def kill_chrome_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        result = subprocess.run(['sudo', 'pkill', '-f', 'chrome'], check=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        print(result.stdout.decode('utf-8'))
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")


def traffic(TASK_NAME, VPS_NAME):
    # 获取当前时间
    current_time = datetime.now()
    # 格式化输出
    formatted_time = current_time.strftime("%Y%m%d%H%M%S")
    logger.info("流量采集开始")

    traffic_name = capture(TASK_NAME, VPS_NAME, formatted_time)


# 启动爬虫
def start_spider():
    process = CrawlerProcess(get_project_settings())

    # 添加你要运行的爬虫
    process.crawl(TraceSpider)

    # 启动爬虫
    process.start()


def main():
    mode = config["spider"]["mode"]
    allowed_domain = config["spider"]["allowed_domain"]
    logger.info(f"开始捕获流量，模式{mode}")
    # 开流量收集
    traffic_thread = threading.Thread(
        target=traffic, args=(mode, allowed_domain)
    )
    logger.info(f"清理浏览器进程")
    kill_chrome_processes()
    logger.info(f"开始采集流量")
    traffic_thread.start()
    time.sleep(1)
    logger.info(f"开始爬取数据")
    start_spider()
    logger.info(f"爬取数据结束")
    time.sleep(1)
    logger.info(f"清理浏览器进程")
    kill_chrome_processes()

    # 关流量收集
    logger.info(f"关流量收集")
    stop_capture()
    traffic_thread.join()
    time.sleep(1)


if __name__ == "__main__":
    main()

import subprocess

from utils.chrome import is_docker, create_chrome_driver
from utils.logger import logger
from utils.config import config
import threading
import time
from traffic.capture import capture, stop_capture
from datetime import datetime
from utils.task import task_instance

duration = int(config["spider"]["duration"])
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
def traffic(index=0):
    # 获取当前时间
    current_time = datetime.now()
    # 格式化输出
    formatted_time = current_time.strftime("%Y%m%d_%H_%M_%S")
    allowed_domain = f"zh.wikipedia.org"
    capture(allowed_domain, formatted_time, f"{index}")


# 清理流量捕获进程
def kill_tcpdump_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        logger.info(f"清理流量捕获进程")
        subprocess.run(['sudo', 'pkill', '-f', 'tcpdump'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")


def start_task(urldict):
    kill_chrome_processes()
    kill_tcpdump_processes()
    index = urldict['id']
    curid = urldict['curid']
    url = f'https://zh.wikipedia.org/wiki?curid={curid}'
    # 开流量收集
    traffic_thread = threading.Thread(target=traffic, kwargs={"index": index} )
    traffic_thread.start()

    logger.info(f"创建浏览器")
    browser = create_chrome_driver()
    logger.info(f"开始访问第{index}的词条：{url}")
    browser.get(url)
    logger.info(f"爬取数据结束, 等待10秒.让浏览器加载完所有已请求的页面")
    time.sleep(10)

    logger.info(f"清理浏览器进程")
    kill_chrome_processes()
    logger.info(f"等待TCP结束挥手完成")
    time.sleep(60)

    # 关流量收集
    logger.info(f"关流量收集")
    stop_capture()


if __name__ == "__main__":
    for urldict in task_instance.urls:
        start_task(urldict)

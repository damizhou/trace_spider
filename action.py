import os
import subprocess
import sys

from utils.chrome import create_chrome_driver
from utils.logger import logger
import threading
import time
from traffic.capture import capture, stop_capture
from datetime import datetime
from utils.task import task_instance

allowed_domain = f"zh.wikipedia.org"

# 清除浏览器进程
def kill_chrome_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        result = subprocess.run(['sudo', 'pkill', '-f', 'chrome'], check=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")


# 流量捕获进程
def traffic(index=0, formatted_time=None):
    # 获取当前时间
    current_time = datetime.now()
    # 格式化输出
    capture(allowed_domain, formatted_time, f"{index}")

# 清理流量捕获进程
def kill_tcpdump_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        # logger.info(f"清理流量捕获进程")
        subprocess.run(['sudo', 'pkill', '-f', 'tcpdump'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")



def start_task():
    url = 'https://zh.wikipedia.org/wiki?curid=5916857'

    formatted_time = datetime.now().strftime("%Y%m%d_%H_%M_%S")
    kill_chrome_processes()
    kill_tcpdump_processes()
    time.sleep(1)

    # 开流量收集
    traffic_thread = threading.Thread(target=traffic, kwargs={"index": index, "formatted_time":formatted_time} )
    traffic_thread.start()
    time.sleep(1)
    logger.info(f"创建浏览器")
    browser, ssl_key_file_path = create_chrome_driver(allowed_domain, formatted_time, f"{index}")
    browser.get(url)
    logger.info(f"爬取数据结束, 等待10秒.让浏览器加载完所有已请求的页面")
    time.sleep(10)

    browser.close()
    logger.info(f"清理浏览器进程")
    kill_chrome_processes()
    logger.info(f"等待TCP结束挥手完成，耗时60秒")
    time.sleep(60)

    # 关流量收集
    logger.info(f"关流量收集")
    pcap_path = stop_capture()
    os.chown(ssl_key_file_path, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))


if __name__ == "__main__":
    start_task()

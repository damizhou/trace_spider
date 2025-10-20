import os
import subprocess
from pathlib import Path
from utils.chrome import create_chrome_driver, open_url_and_save_content
from utils.logger import logger
from utils.config import config
import threading
import time
from traffic.capture import capture, stop_capture
from datetime import datetime
from utils.task import task_instance
from concurrent.futures import ThreadPoolExecutor, as_completed

duration = int(config["spider"]["duration"])
crawlers_timer = None


# 清除浏览器进程
def kill_chrome_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        subprocess.run(['pkill', '-f', 'chromedriver'], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(['pkill', '-f', 'google-chrome'], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")


# 流量捕获进程
def traffic(index):
    # 获取当前时间
    current_time = datetime.now()
    # 格式化输出
    formatted_time = current_time.strftime("%Y%m%d_%H_%M_%S")
    allowed_domain = task_instance.current_allowed_domain
    capture(allowed_domain, formatted_time, f"{index}")


# 清理流量捕获进程
def kill_tcpdump_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        logger.info(f"清理流量捕获进程")
        subprocess.run(['sudo', 'pkill', '-f', 'tcpdump'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")

def _chown_r(path: Path, uid: int, gid: int):
    subprocess.run(["chown", "-R", f"{uid}:{gid}", str(path)], check=True)

def start_task(session, current_id, current_url, year):
    kill_chrome_processes()
    kill_tcpdump_processes()
    time.sleep(1)

    # 开流量收集
    traffic_thread = threading.Thread(target=traffic, kwargs={"index": f"{session}_{current_id}_{year}"} )
    traffic_thread.start()
    time.sleep(1)

    logger.info(f"创建浏览器")
    browser = create_chrome_driver()
    # 保存网页内容
    is_finished = False
    try:
        open_url_and_save_content(browser, current_url)
        logger.info(f"爬取数据结束, 等待10秒.让浏览器加载完所有已请求的页面")
        time.sleep(15)
        is_finished = True

    except Exception as e:
        logger.error(f"爬取 {current_url} 失败: {e}")
    try:
        browser.quit()
    except Exception as e:
        logger.warning(f"browser.quit() 异常: {e}")
    logger.info(f"清理浏览器进程")
    kill_chrome_processes()
    logger.info(f"等待TCP结束挥手完成")
    if is_finished:
        time.sleep(60)

    # 关流量收集
    logger.info(f"关流量收集")
    stop_capture()

if __name__ == "__main__":
    for url in task_instance.urls:
        current_url = url.get('URL')
        section = url.get('Section')
        current_id = url.get('ID')
        year = url.get('Year')
        start_task(section, current_id, current_url, year)

import json
import os
import random
import subprocess
import time

from utils import project_path
from utils.config import config
from utils.logger import setup_logging, logger
import threading
from utils.task import task_instance
from utils.chrome import create_chrome_driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from pytrends.request import TrendReq
import pandas as pd


# duration = int(config["spider"]["duration"])


# def run_action_script():
#     # 使用 subprocess 运行 action.py
#     subprocess.run(['python', 'action.py'])
#
#
# def main():
#     task_instance.current_index = 0
#     logger.info(f"开始任务")
#     logger.info(
#         f"本次任务共计采集{len(task_instance.urls)}个页面，预计采集时间{len(task_instance.urls) * duration / 60}分钟")
#     logger.info(f"任务URL列表：{task_instance.urls}")
#     while task_instance.current_index != len(task_instance.urls):
#         with open('./utils/running.json', 'w') as f:
#             json.dump({'currentIndex': task_instance.current_index}, f)
#         logger.info(f"当前第{task_instance.current_index + 1}个任务，任务URL为{task_instance.current_start_url}，"
#                     f"剩余时间{(len(task_instance.urls) - task_instance.current_index) * duration / 60}分钟")
#         # 创建一个线程来运行 action.py
#         action_thread = threading.Thread(target=run_action_script)
#
#         # 启动线程
#         action_thread.start()
#
#         # 等待线程完成
#         action_thread.join()
#         task_instance.current_index += 1
#
#     logger.info(f"任务完成")


def main():
    keyword_list_path = os.path.join(project_path, "google_search_keyword_list")
    print('keyword_list_path', keyword_list_path)
    with open(keyword_list_path, "r", encoding='utf-8') as file:
        keyword_list = set(line.strip() for line in file)
    # 打印集合内容
    print(keyword_list)
    logger.info(f"已从{keyword_list_path}中获取关键词列表")
    # random.shuffle(google_search_keyword_list)  # 洗牌url列表

    driver = create_chrome_driver(headless=False)
    driver.get(r'https://www.google.com')
    for keyword in keyword_list:
        search_box = driver.find_element(By.NAME, 'q')
        search_box.clear()
        search_box.send_keys(keyword)
        search_box.send_keys(Keys.RETURN)
        logger.info(f'页面标题 : {driver.title}')
        # 向下滚动6次
        for i in range(6):
            # 页面滑到最下方
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)


if __name__ == "__main__":
    main()

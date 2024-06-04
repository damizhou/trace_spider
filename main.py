import json
import subprocess
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

def get_words():
    # 创建 TrendReq 对象
    pytrends = TrendReq(hl='en-US', tz=360)

    # 获取实时热门搜索词
    trending_searches_df = pytrends.trending_searches(pn='united_states')  # 可以根据需要更改地区

    # 打印热门搜索词
    print(trending_searches_df)

    # 保存到 CSV 文件
    trending_searches_df.to_csv('trending_searches.csv', index=False)


def main():
    driver = create_chrome_driver()
    driver.get(r'https://www.google.com')
    print(f'页面标题 1111 : {driver.title}')
    search_box = driver.find_element(By.NAME, 'q')
    search_box.send_keys('Selenium Python')
    search_box.send_keys(Keys.RETURN)
    driver.implicitly_wait(5)  # 简单的等待5秒
    print(f'页面标题 2222 : {driver.title}')

    search_box = driver.find_element(By.NAME, 'q')
    search_box.clear()
    search_box.send_keys('Dallas Mavericks')
    search_box.send_keys(Keys.RETURN)
    driver.implicitly_wait(5)  # 简单的等待5秒
    print(f'页面标题 3333 : {driver.title}')
    pass


if __name__ == "__main__":
    main()
    # get_words()


# Bharatiya Janata Party
# England vs Bosnia and Herzegovina
# Afghanistan vs Uganda
# Tamilnadu Election Result 2024
# Djokovic
# Venom: The Last Dance
# England football
# AP Election Results 2024
# Sensex today
# Kanlaon Volcano
# Nvidia and AMD square off in fight to take control of AI
# India election results
# Sri Lanka vs South Africa
# Berkshire Hathaway
# GameStop
# David Yong
# Sensex
# Nvidia
# Claudia Sheinbaum
# Nifty 50
# Rob Burrow
# Aneurysm
# Maldives
# Rupert Murdoch
# Mbappe
# Gaza ceasefire
# Chee Hong Tat
# Champions League
# Champions League final
# UFC 302
# Zelensky
# Narendra Modi
# UEFA
# Jose Mourinho
# Trump
# Lennart Thy
# In-N-Out Singapore
# Salesforce
# Rafah
# Ticketmaster
# Dallas Mavericks
# Mavs
# All Eyes on Rafah meaning
# Bill Walton
# Singapore Open
# Pope Francis
# Palestine
# Djokovic
# Celtics
# Gaza
# Rafah
# Johnny Wactor
# Enzo Maresca
# Rafael Nadal
# Seatrium
# Memorial Day
# Papua New Guinea
# Dallas Mavericks
# Rishi Sunak
# T20 World Cup

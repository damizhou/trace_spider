import json
import sys
from utils.config import config
from utils.logger import logger
import threading
from utils.task import task_instance
import subprocess
from pathlib import Path

duration = int(config["spider"]["duration"])


def run_action_script():
    # __file__  =  主脚本的路径（如 main.py）
    # 用 Path 计算出同目录下的 action.py
    action_path = Path(__file__).with_name("action.py")

    # sys.executable 指向当前进程的解释器（.venv\Scripts\python.exe）
    command = [sys.executable, str(action_path), *sys.argv[1:]]

    # 建议加 check=True，这样子进程异常会直接抛出
    subprocess.run(command, check=True)


def main():
    task_instance.current_index = 0
    logger.info(f"开始任务")
    logger.info(f"本次任务共计采集{len(task_instance.urls)}个页面，预计单个网站采集时间{duration / 60}分钟，"
                f"共计采集{len(task_instance.urls) * duration / 60}分钟")
    logger.info(f"任务URL列表：{task_instance.urls}")
    while task_instance.current_index != len(task_instance.urls):
        with open('./utils/running.json', 'w') as f:
            json.dump({'currentIndex': task_instance.current_index}, f)
        logger.info(f"当前第{task_instance.current_index + 1}个任务，任务URL为{task_instance.current_start_url}，"
                    f"剩余时间{(len(task_instance.urls) - task_instance.current_index) * duration / 60}分钟")
        # 创建一个线程来运行 action.py
        action_thread = threading.Thread(target=run_action_script)

        # 启动线程
        action_thread.start()

        # 等待线程完成
        action_thread.join()
        task_instance.current_index += 1

    logger.info(f"任务完成")


if __name__ == "__main__":
    main()
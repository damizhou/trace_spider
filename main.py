import json
import subprocess
from utils.config import config
from utils.logger import setup_logging, logger
import threading
from utils.task import task_instance

duration = int(config["spider"]["duration"])


def run_action_script():
    # 使用 subprocess 运行 action.py
    subprocess.run(['python', 'action.py'])


def main():
    task_instance.current_index = 0
    logger.info(f"开始任务")
    logger.info(
        f"本次任务共计采集{len(task_instance.urls)}个页面，预计采集时间{len(task_instance.urls) * duration / 60}分钟")
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

import subprocess
from action import kill_tcpdump_processes
from utils.logger import logger
import threading
from utils.task import task_instance

def run_action_script():
    # 使用 subprocess 运行 action.py
    subprocess.run(['python', 'action.py'])


def main():
    task_instance.current_index = 0
    logger.info(f"开始任务")

    # 创建一个线程来运行 action.py
    action_thread = threading.Thread(target=run_action_script)

    # 启动线程
    action_thread.start()

    # 等待线程完成
    action_thread.join()
    kill_tcpdump_processes()

    logger.info(f"任务完成")

if __name__ == "__main__":
    main()

import json
import sys
from utils.config import config
from utils.logger import logger
import threading
from utils.task import task_instance
import subprocess

duration = int(config["spider"]["duration"])


def run_action_script():
    command = ['python', 'action.py'] + sys.argv[1:]
    # 使用 subprocess 运行 action.py
    subprocess.run(command)


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
        kill_residue_processes()
        # 创建一个线程来运行 action.py
        action_thread = threading.Thread(target=run_action_script)

        # 启动线程
        action_thread.start()

        # 等待线程完成
        action_thread.join()
        task_instance.current_index += 1

    logger.info(f"任务完成")

def kill_residue_processes():
    try:
        # Run the command to kill all processes containing 'chrome'
        subprocess.run('pgrep -f "action.py" | xargs kill -9', shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr.decode('utf-8')}")

def dealVPN():
    # 执行带有 sudo 权限的 bash 脚本
    try:
        # 使用 sudo 权限执行 start.sh
        process = subprocess.Popen(["bash", '/app/clash-for-linux/start.sh'], stdout=subprocess.PIPE)
        output, error = process.communicate()
        if error is None:
            logger.info("代理启动成功")

    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    if sys.argv[3] != 'novpn':
        dealVPN()
    main()

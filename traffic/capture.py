from utils.config import config
from utils.logger import logger
import os
from datetime import datetime
import time
import shutil
from utils import project_path
import subprocess

should_stop_capture = False


def capture(TASK_NAME, VPS_NAME, formatted_time):
    traffic_dir = os.path.join(project_path, "data", TASK_NAME, "row_pcap")
    os.makedirs(traffic_dir, exist_ok=True)

    traffic_name = os.path.join(traffic_dir, f"{formatted_time}_{VPS_NAME}.pcap")

    # 设置tcpdump命令的参数
    tcpdump_command = [
        "tcpdump",
        "-w",
        traffic_name,  # 输出文件的路径
    ]
    global process
    # 开流量收集
    process = subprocess.Popen(tcpdump_command)

    logger.info("开始捕获流量")
    return traffic_name


def stop_capture():
    global process
    process.terminate()


def move_log(log_path, dst_path):
    if not os.path.exists(os.path.dirname(dst_path)):
        os.makedirs(os.path.dirname(dst_path))
    shutil.move(log_path, dst_path)


if __name__ == "__main__":
    capture("www.baidu.com", "TEST", "1111111", "tcp")
    time.sleep(9)

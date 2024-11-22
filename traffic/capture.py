from utils.logger import logger
import os
import time
import shutil
from utils import project_path
import subprocess
import psutil
from datetime import datetime

from utils.task import task_instance

should_stop_capture = False


def capture(TASK_NAME, formatted_time, parsers):
    current_time = datetime.now()
    current_data = current_time.strftime("%Y%m%d")
    dataDir = os.path.join(project_path, "data", current_data)
    os.makedirs(dataDir, exist_ok=True)
    # 格式化输出
    os.chown(dataDir, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))
    traffic_dir = os.path.join(dataDir, TASK_NAME)
    os.makedirs(traffic_dir, exist_ok=True)
    os.chown(traffic_dir, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))
    filename = 'zh.wikipedia.org_'
    # for parser in parsers:
    #     filename += f"{parser}_"

    traffic_name = os.path.join(traffic_dir, f"{filename}{formatted_time}_{TASK_NAME}.pcap")
    task_instance.traffic_name = traffic_name
    # 设置tcpdump命令的参数
    tcpdump_command = [
        "tcpdump",
        "-w",
        traffic_name,  # 输出文件的路径
    ]
    global process
    # 开流量收集
    process = subprocess.Popen(tcpdump_command)
    #
    logger.info("开始捕获流量")
    return traffic_name


def stop_capture():
    global process
    # 获取当前进程的PID
    pid = process.pid

    # 使用 psutil 获取进程信息
    p = psutil.Process(pid)

    # 获取进程的启动参数
    cmdline = p.cmdline()
    file_path = cmdline[-1]
    os.chown(file_path, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))
    process.terminate()


def move_log(log_path, dst_path):
    if not os.path.exists(os.path.dirname(dst_path)):
        os.makedirs(os.path.dirname(dst_path))
    shutil.move(log_path, dst_path)


if __name__ == "__main__":
    capture("www.baidu.com", "TEST", "1111111", "tcp")
    time.sleep(9)

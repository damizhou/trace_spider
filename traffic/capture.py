from utils.logger import logger
import os
import time
import shutil
from utils import project_path
import subprocess
import psutil

should_stop_capture = False
process = ''

def capture(TASK_NAME, formatted_time):
    dataDir = os.path.join(project_path, "data")
    os.makedirs(dataDir, exist_ok=True)
    traffic_dir = os.path.join(dataDir, TASK_NAME)
    os.makedirs(traffic_dir, exist_ok=True)
    if os.getenv('HOST_UID') is not None:
        os.chown(dataDir, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))
        os.chown(traffic_dir, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))

    traffic_name = os.path.join(traffic_dir, f"{formatted_time}_{TASK_NAME}.pcap")

    # 设置tcpdump命令的参数
    tcpdump_command = [
        "tcpdump",
        "-w",
        traffic_name,  # 输出文件的路径
    ]

    # 开流量收集
    process = subprocess.Popen(tcpdump_command)
    #
    logger.info("开始捕获流量")
    return traffic_name


def stop_capture():
    # 获取当前进程的PID
    pid = process.pid

    # 使用 psutil 获取进程信息
    p = psutil.Process(pid)

    # 获取进程的启动参数
    cmdline = p.cmdline()
    file_path = cmdline[-1]
    if os.getenv('HOST_UID') is not None:
        os.chown(file_path, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))
    process.terminate()


def move_log(log_path, dst_path):
    if not os.path.exists(os.path.dirname(dst_path)):
        os.makedirs(os.path.dirname(dst_path))
    shutil.move(log_path, dst_path)


if __name__ == "__main__":
    capture("www.baidu.com", "TEST", "1111111", "tcp")
    time.sleep(9)

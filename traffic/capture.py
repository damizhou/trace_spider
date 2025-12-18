from utils.logger import logger
import os
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

    traffic_dir = os.path.join(dataDir, TASK_NAME)
    os.makedirs(traffic_dir, exist_ok=True)

    parsers = parsers.replace(":", "").replace("/", "").replace("?", "").replace("/", "")
    filename = f'{parsers}_'

    traffic_name = os.path.join(traffic_dir, f"{filename}{formatted_time}_{TASK_NAME}.pcap")
    task_instance.pcap_path = traffic_name
    # 设置tcpdump命令的参数
    tcpdump_command = [
        "tcpdump",
        "-w",
        traffic_name,  # 输出文件的路径
    ]

    logger.info(f'tcpdump_command:{tcpdump_command}')
    global process
    # 开流量收集
    process = subprocess.Popen(tcpdump_command)
    #
    logger.info("开始捕获流量")
    return traffic_name


def stop_capture():
    global process
    # 取输出文件路径
    pid = process.pid
    p = psutil.Process(pid)
    cmdline = p.cmdline()
    file_path = cmdline[-1]
    os.chown(file_path, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))

    # 先优雅终止，再等待；若不退出再 kill，并最终 wait()，确保不会留僵尸
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        finally:
            try:
                process.wait(timeout=3)
            except Exception:
                pass
    return file_path


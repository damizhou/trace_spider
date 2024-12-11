from datetime import datetime
from utils import project_path
import logging
import logging.handlers
import os

from utils.chrome import is_docker
from utils.task import task_instance


# 配置日志基本设置
def setup_logging():
    logs_dir = os.path.join(project_path, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    if is_docker():
        os.chown(logs_dir, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))

    # 获取当前时间
    current_time = datetime.now()
    # 格式化输出
    formatted_time = current_time.strftime("%Y%m%d")

    filename = formatted_time + ".log"

    # 创建一个logger
    logger = logging.getLogger(filename.split(".")[0])
    logger.setLevel(logging.DEBUG)  # 可以根据需要设置不同的日志级别

    # 创建一个handler，用于写入日志文件
    log_file = os.path.join(logs_dir, filename)

    # 用于写入日志文件，当文件大小超过100MB时进行滚动
    file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=3,
                                                        encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # 创建一个handler，用于将日志输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 定义handler的输出格式
    # formatter = logging.Formatter
    # ('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 给logger添加handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# 配置日志基本设置
def setup_url_logger(traffic_name):
    global url_logger
    # 创建一个handler，用于写入日志文件
    log_file = traffic_name.replace(".pcap", ".log").replace("data", "url_logs")
    directory_path = os.path.dirname(log_file)
    os.makedirs(directory_path, exist_ok=True)
    if is_docker():
        os.chown(directory_path, int(os.getenv('HOST_UID')), int(os.getenv('HOST_GID')))
    allowed_domain = task_instance.current_allowed_domain
    # 创建一个logger
    logger = logging.getLogger(allowed_domain)
    logger.setLevel(logging.DEBUG)  # 可以根据需要设置不同的日志级别

    # 用于写入日志文件，当文件大小超过100MB时进行滚动
    file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=3,
                                                        encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # 创建一个handler，用于将日志输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 定义handler的输出格式
    # formatter = logging.Formatter
    # ('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 给logger添加handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    url_logger = logger
    return logger

logger = setup_logging()
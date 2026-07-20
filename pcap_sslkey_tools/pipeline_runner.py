#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import logging
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========= 只改这里 =========
SOURCE_ROOT = r"/home/pcz/x_trace_spider*"      # 源基础路径（支持通配）
DEST_ROOT   = r"/netdisk/x_with_ssl_key/collection_without_login"    # 目的基础路径（pcap 在这里的 pcap 子目录）
COPY_WORKERS = 32                               # copy 并发进程数
# ========= 只改这里 =========
def setup_logger():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- Step 1: copy_guardian ----------
def step_copy_guardian():
    import copy_files as cf  # 你的新版 copy_guardian 已把 .pcap 目标设为 DEST_ROOT/pcap
    # 覆盖其全局变量
    if hasattr(cf, "SOURCE_ROOT"):      cf.SOURCE_ROOT      = SOURCE_ROOT
    if hasattr(cf, "DEST_ROOT"):        cf.DEST_ROOT        = DEST_ROOT
    if hasattr(cf, "WORKERS"):          cf.WORKERS          = COPY_WORKERS
    if hasattr(cf, "DRY_RUN"):          cf.DRY_RUN          = False         # 演练：仅打印计划，不真实复制；正式跑改为 False
    if hasattr(cf, "OVERRIDE_DATE"):    cf.OVERRIDE_DATE    = None

    logging.info("开始 copy_files ...")
    cf.main()
    logging.info("copy_files 完成。")



def main():
    setup_logger()

    # 确保同目录可 import 那五个脚本
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    # 1) 复制
    step_copy_guardian()

    logging.info("✅ 全流程完成。")

if __name__ == "__main__":
    main()

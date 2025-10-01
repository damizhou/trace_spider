#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========= 只改这里 =========
SOURCE_ROOT = r"/home/pcz/theguardian_trace_spider*"   # 源基础路径（支持通配）
DEST_ROOT   = r"/netdisk/theguardian_with_temp"     # 目的基础路径（pcap 在这里的 pcap 子目录）
COPY_WORKERS = 32                                            # copy 并发进程数
# ========= 只改这里 =========
def ensure_root_or_reexec():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        # 以同一解释器重新执行当前脚本，保留环境变量（-E）
        os.execvp("sudo", ["sudo", "-E", sys.executable] + sys.argv)

def ensure_root():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise SystemExit("必须以 root 运行。示例：sudo python3 pipeline_runner.py")

def setup_logger():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- Step 1: copy_guardian ----------
def step_copy_guardian():
    import copy_guardian as cg  # 你的新版 copy_guardian 已把 .pcap 目标设为 DEST_ROOT/pcap
    # 覆盖其全局变量
    if hasattr(cg, "SOURCE_ROOT"): cg.SOURCE_ROOT = SOURCE_ROOT
    if hasattr(cg, "DEST_ROOT"):   cg.DEST_ROOT   = DEST_ROOT
    if hasattr(cg, "WORKERS"):     cg.WORKERS     = COPY_WORKERS
    if hasattr(cg, "DRY_RUN"):     cg.DRY_RUN     = False  # 演练：仅打印计划，不真实复制；正式跑改为 False
    if hasattr(cg, "OVERRIDE_DATE"):     cg.OVERRIDE_DATE = None

    logging.info("[1/4] 开始 copy_guardian ...")
    cg.main()
    logging.info("[1/4] copy_guardian 完成。")

# ---------- Step 2: filter 两个并发 ----------
def _run_filter_pcap():
    import filter_pcap_outliers as fpo
    # 注入目录
    if hasattr(fpo, "BASE_DIR"): fpo.BASE_DIR = f"{DEST_ROOT}/pcap"
    return fpo.main()

def _run_filter_ssl():
    import filter_ssl_key_outliers as fso
    if hasattr(fso, "BASE_DIR"): fso.BASE_DIR = f"{DEST_ROOT}/ssl_key"
    return fso.main()

def step_filters_parallel():
    logging.info("[2/4] 并发执行 filter_pcap_outliers / filter_ssl_key_outliers ...")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(_run_filter_pcap), ex.submit(_run_filter_ssl)]
        for fut in as_completed(futs):
            fut.result()
    logging.info("[2/4] 两个过滤脚本完成。")

# ---------- Step 3: cleanup_unmatched ----------
def step_cleanup_unmatched():
    import cleanup_unmatched as cu
    if hasattr(cu, "PCAP_DIR_DEFAULT"): cu.PCAP_DIR_DEFAULT         = f"{DEST_ROOT}/pcap"
    if hasattr(cu, "SSL_DIR_DEFAULT"): cu.SSL_DIR_DEFAULT           = f"{DEST_ROOT}/ssl_key"
    if hasattr(cu, "CONTENT_DIR_DEFAULT"): cu.CONTENT_DIR_DEFAULT   = f"{DEST_ROOT}/content"
    if hasattr(cu, "HTML_DIR_DEFAULT"): cu.HTML_DIR_DEFAULT     = f"{DEST_ROOT}/html"
    logging.info("[3/4] 执行 cleanup_unmatched ...")
    cu.main()
    logging.info("[3/4] cleanup_unmatched 完成。")

# ---------- Step 4: find_missing_pcaps ----------
def step_find_missing():
    import find_missing_pcaps as fmp
    if hasattr(fmp, "PCAP_DIR"): fmp.PCAP_DIR = f"{DEST_ROOT}/pcap"
    logging.info("[4/4] 执行 find_missing_pcaps ...")
    fmp_result = fmp.main()
    logging.info("[4/4] find_missing_pcaps 完成。")
    return fmp_result

def copy_temp_to_destination():
    import copy_temp_to_destination as ctd
    logging.info("执行 copy_temp_to_destination ...")
    ctd.main()
    logging.info("copy_temp_to_destination 完成。")

def main():
    # ensure_root_or_reexec()
    setup_logger()

    # 确保同目录可 import 那五个脚本
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    # 1) 复制
    step_copy_guardian()
    # 2) 并发过滤
    step_filters_parallel()
    # 3) 清理不匹配
    step_cleanup_unmatched()
    # 4) 统计缺失
    # step_find_missing_result = step_find_missing()

    # 4) 移动到最终位置
    copy_temp_to_destination()

    logging.info("✅ 全流程完成。")
    # return step_find_missing_result

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import shutil
import logging
import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# ===== 全局常量 =====
SOURCE_ROOT = r"/home/pcz/2000_theguardian_trace_spider*"   # 源基础路径
DEST_ROOT   = r"/netdisk/theguardian_with_ssl_key/2000"   # 目的基础路径
WORKERS     = 8      # 并发进程数

def ensure_root():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise SystemExit("必须以 root 运行。示例：sudo python3 copy_guardian.py")

def setup_logger():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def list_files(pattern: str):
    files = glob.glob(pattern)
    return [f for f in files if os.path.isfile(f)]

def copy_one(src: str, dest_dir: str) -> tuple[str, bool, str]:
    try:
        dst_dir = Path(dest_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / Path(src).name
        if dst.exists():
            return (src, True, "exists, skipped")
        # 覆盖复制
        shutil.copy2(src, dst)
        return (src, True, "")
    except Exception as e:
        return (src, False, str(e))

def chown_recursive(path: str):
    # 用 sudo 提权前的真实用户；没取到就退化为 USER，再不行用 root
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"
    subprocess.run(["chown", "-R", f"{user}:{user}", path], check=False)

def main():
    ensure_root()
    setup_logger()

    jobs = [
        (f"{SOURCE_ROOT}/content/2025*/theguardian.com/*theguardian.com.txt",
         f"{DEST_ROOT}/content"),
        (f"{SOURCE_ROOT}/data/2025*/theguardian.com/*theguardian.com.pcap",
         f"{DEST_ROOT}/pcap"),
        (f"{SOURCE_ROOT}/ssl_key/2025*/theguardian.com/*theguardian.com_ssl_key.log",
         f"{DEST_ROOT}/ssl_key"),
        (f"{SOURCE_ROOT}/html/2025*/theguardian.com/*theguardian.com.html",
         f"{DEST_ROOT}/html"),
    ]

    tasks = []
    total_found = 0
    for pattern, dest_dir in jobs:
        files = list_files(pattern)
        total_found += len(files)
        if files:
            logging.info(f"匹配到 {len(files)} 个文件：{pattern}")
            tasks.extend((f, dest_dir) for f in files)
        else:
            logging.warning(f"未匹配到文件：{pattern}")

    if total_found == 0:
        logging.error("没有任何源文件可复制，退出。")
        return

    ok_cnt = 0
    fail_cnt = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(copy_one, src, dest_dir) for (src, dest_dir) in tasks]
        for fut in as_completed(futures):
            src, ok, msg = fut.result()
            if ok:
                ok_cnt += 1
            else:
                fail_cnt += 1
                logging.error(f"FAIL: {src} -> {msg}")

    logging.info(f"复制完成：成功 {ok_cnt}，失败 {fail_cnt}，总计 {ok_cnt + fail_cnt}。")

    target_root = f"{DEST_ROOT}"
    chown_recursive(target_root)
    logging.info(f"已执行：sudo chown -R $USER:$USER {target_root}")
    logging.info("结束。")

if __name__ == "__main__":
    main()

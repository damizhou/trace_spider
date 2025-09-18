#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import glob
import os
from pathlib import Path
import shutil
import logging
from typing import Tuple
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
DEFAULT_DEST_ROOT = Path("/netdisk/theguardian_with_ssl_key")

def any_dir_exists(dir_glob: str) -> bool:
    """任一匹配项存在且为目录则返回 True。"""
    for p in glob.glob(dir_glob):
        if os.path.isdir(p):
            return True
    return False

def move_matches(pattern: str, dest_dir: Path, force: bool = True) -> Tuple[int, int]:
    """
    按通配 pattern 找文件并移动到 dest_dir（等价 mv -f）。
    返回 (移动文件数, 总字节数)
    """
    matches = sorted(set(glob.glob(pattern, recursive=True)))
    dest_dir.mkdir(parents=True, exist_ok=True)

    moved_cnt = 0
    moved_bytes = 0

    for src_str in matches:
        src = Path(src_str)
        if not src.is_file():
            continue

        try:
            size = src.stat().st_size
        except FileNotFoundError:
            continue

        target = dest_dir / src.name
        try:
            if target.exists() and force:
                try:
                    target.unlink()
                except IsADirectoryError:
                    shutil.rmtree(target)

            shutil.move(str(src), str(target))
            moved_cnt += 1
            moved_bytes += size
            logging.info("MOVED: %s -> %s", src, target)
        except Exception as e:
            logging.error("FAILED: %s -> %s (%s)", src, target, e)

    if not matches:
        logging.info("NO MATCH: %s", pattern)

    return moved_cnt, moved_bytes

def main():
    dest_ssl   = DEFAULT_DEST_ROOT / "ssl_key"
    dest_pcap  = DEFAULT_DEST_ROOT / "pcap"
    dest_cont  = DEFAULT_DEST_ROOT / "content"

    tasks = [
        # ssl_key
        {
            "precheck_dir_glob": "/home/pcz/theguardian_trace_spider*/ssl_keys/",
            "pattern": "/home/pcz/theguardian_trace_spider*/ssl_keys/2025*/theguardian.com/*theguardian.com_ssl_key.log",
            "dest": dest_ssl,
            "name": "ssl_keys",
        },
        # pcap
        {
            "precheck_dir_glob": "/home/pcz/theguardian_trace_spider*/data/",
            "pattern": "/home/pcz/theguardian_trace_spider*/data/2025*/theguardian.com/*theguardian.com.pcap",
            "dest": dest_pcap,
            "name": "pcap",
        },
        # content
        {
            "precheck_dir_glob": "/home/pcz/theguardian_trace_spider*/content/",
            "pattern": "/home/pcz/theguardian_trace_spider*/content/2025*/theguardian.com/*theguardian.com.txt",
            "dest": dest_cont,
            "name": "content",
        },
    ]

    total_files = 0
    total_bytes = 0

    for t in tasks:
        if not any_dir_exists(t["precheck_dir_glob"]):
            logging.warning("SKIP %-8s：缺少前置目录 %s", t["name"], t["precheck_dir_glob"])
            continue

        logging.info("=== TASK %-8s ===\nPRECHECK: %s\nPATTERN : %s\nDEST    : %s",
                     t["name"], t["precheck_dir_glob"], t["pattern"], t["dest"])
        cnt, size = move_matches(t["pattern"], t["dest"], force=True)
        logging.info("=== DONE  %-8s === moved %d files, %d bytes\n", t["name"], cnt, size)
        total_files += cnt
        total_bytes += size

    logging.info("ALL DONE: moved %d files, %d bytes total. DEST_ROOT=%s", total_files, total_bytes, DEFAULT_DEST_ROOT)

    # === post-step: 递归 chown pcap 给原调用者（非 root）===
    owner = os.environ.get("USER")
    if not owner:
        logging.warning("CHOWN SKIP: 无法确定调用者用户名（缺少 SUDO_USER/USER）")
        return
    if dest_pcap.exists():
        try:
            subprocess.run(["chown", "-R", f"{owner}:{owner}", str(dest_pcap)], check=True)
            logging.info('CHOWN DONE: chown -R %s:%s "%s"', owner, owner, dest_pcap)
        except subprocess.CalledProcessError as e:
            logging.error("CHOWN FAIL: %s", e)
    else:
        logging.info("CHOWN SKIP: 目标不存在 %s", dest_pcap)

if __name__ == "__main__":
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise SystemExit("必须以 root 运行。示例：sudo python move_assets.py")
    main()

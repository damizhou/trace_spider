#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只移动“目标日期(默认=本地昨天)”目录中的四类文件（content/html/pcap/ssl_key）。
判定依据为目录层级 YYYYMMDD（不解析文件名）。
- 可作为库调用：覆盖模块全局变量后直接 main()
- 亦可命令行运行：支持 --dry-run / --date / --dest-root / --workers / --source-glob 等
- 并发复制；已存在则跳过；保留元数据(copy2)；强调可读与可移植
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# ========= 可被外部覆盖的模块级变量（库调用用到） =========
# 若设置 SOURCE_ROOT（字符串或glob），优先使用它；否则使用 SPIDER_ROOT_GLOBS（多glob）
SOURCE_ROOT: Optional[str] = None
SPIDER_ROOT_GLOBS: List[str] = [
    r"/home/pcz/theguardian_trace_spider*",
]

DEST_ROOT: str = os.environ.get("DEST_ROOT", r"/netdisk/theguardian_with_temp")
WORKERS: int = int(os.environ.get("COPY_WORKERS", "8"))
DRY_RUN: bool = os.environ.get("DRY_RUN", "0").lower() in {"1", "true", "yes"}
OVERRIDE_DATE: Optional[str] = os.environ.get("COPY_DATE")
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


# ========= 日志 =========
def setup_logger(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="%(asctime)s [%(levelname)s] %(message)s")


# ========= 日期与源根 =========
def resolve_target_date(override: Optional[str]) -> str:
    """返回目标日期(YYYYMMDD)。优先用 override；否则用本地“昨天”"""
    if override:
        if len(override) != 8 or not override.isdigit():
            raise SystemExit("日期必须为 YYYYMMDD，例如 20250929")
        return override
    y = datetime.now() - timedelta(days=1)
    return y.strftime("%Y%m%d")


def discover_source_roots(globs: Sequence[str]) -> List[str]:
    """展开 globs 找到实际存在的抓取根目录，并排序去重"""
    roots: List[str] = []
    for pattern in globs:
        for p in glob.glob(pattern):
            if Path(p).is_dir():
                roots.append(p)
    roots = sorted(set(roots))
    if not roots:
        logging.error("未发现任何匹配的抓取根目录，请检查 SOURCE_ROOT/SPIDER_ROOT_GLOBS 或路径是否存在。")
    else:
        logging.info("发现抓取根目录：%s", ", ".join(roots))
    return roots


# ========= 任务构造与执行 =========
def list_files(pattern: str) -> List[str]:
    files = glob.glob(pattern)
    return [f for f in files if Path(f).is_file()]


def build_tasks_for_date(roots: Sequence[str], ymd: str, dest_root: str) -> List[Tuple[str, str]]:
    """
    仅匹配形如：
      <root>/content/YYYYMMDD/theguardian.com/*theguardian.com.txt
      <root>/data/YYYYMMDD/theguardian.com/*theguardian.com.pcap
      <root>/ssl_key/YYYYMMDD/theguardian.com/*theguardian.com_ssl_key.log
      <root>/html/YYYYMMDD/theguardian.com/*theguardian.com.html
    返回 (src_file, dest_dir) 列表
    """
    tasks: List[Tuple[str, str]] = []
    for root in roots:
        # content
        for f in list_files(f"{root}/content/{ymd}/theguardian.com/*theguardian.com.txt"):
            tasks.append((f, f"{dest_root}/content"))
        # pcap（源目录名为 data）
        for f in list_files(f"{root}/data/{ymd}/theguardian.com/*theguardian.com.pcap"):
            tasks.append((f, f"{dest_root}/pcap"))
        # ssl_key
        for f in list_files(f"{root}/ssl_key/{ymd}/theguardian.com/*theguardian.com_ssl_key.log"):
            tasks.append((f, f"{dest_root}/ssl_key"))
        # html
        for f in list_files(f"{root}/html/{ymd}/theguardian.com/*theguardian.com.html"):
            tasks.append((f, f"{dest_root}/html"))
    return tasks


def copy_one(src: str, dest_dir: str) -> Tuple[str, bool, str, Optional[str]]:
    """
    复制单个文件。
    返回: (源文件, 是否OK, 消息, 实际目标路径或None)
      - 已存在：("exists, skipped", None)
      - 成功复制：("", 目标路径)
      - 失败：("错误信息", None)
    """
    try:
        dst_dir = Path(dest_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / Path(src).name
        if dst.exists():
            return (src, True, "exists, skipped", None)
        shutil.copy2(src, dst)
        return (src, True, "", str(dst))
    except Exception as e:
        return (src, False, str(e), None)


# ========= 统一的执行入口（库/CLI 共用） =========
def run(
    *,
    dry_run: Optional[bool] = None,
    date: Optional[str] = None,
    dest_root: Optional[str] = None,
    workers: Optional[int] = None,
    source_globs: Optional[Sequence[str]] = None,
    log_level: Optional[str] = None,
) -> None:
    """
    统一执行函数：
    - 参数为 None 时使用模块级变量（便于库调用时外部覆盖）
    """
    # 参数优先级：显式参数 > 模块变量
    _dry_run = DRY_RUN if dry_run is None else dry_run
    _date = resolve_target_date(OVERRIDE_DATE if date is None else date)
    _dest_root = DEST_ROOT if dest_root is None else dest_root
    _workers = WORKERS if workers is None else workers
    _log_level = LOG_LEVEL if log_level is None else log_level

    setup_logger(_log_level)

    # 源根选择：若设置了 SOURCE_ROOT（单字符串/单glob），优先；否则用 SPIDER_ROOT_GLOBS 或传入的 source_globs
    effective_globs: Sequence[str]
    if source_globs is not None:
        effective_globs = list(source_globs)
    elif SOURCE_ROOT:
        effective_globs = [SOURCE_ROOT]
    else:
        effective_globs = SPIDER_ROOT_GLOBS

    logging.info("仅处理目标日期目录：%s", _date)
    logging.info("目标根目录：%s", _dest_root)
    logging.info("dry-run=%s, workers=%s", "on" if _dry_run else "off", _workers)

    roots = discover_source_roots(effective_globs)
    if not roots:
        raise SystemExit(1)

    tasks = build_tasks_for_date(roots, _date, _dest_root)
    total = len(tasks)
    if total == 0:
        logging.warning("目标日期 %s 下未发现任何可复制文件。", _date)
        return

    # 统计四类
    stats = {"content": 0, "pcap": 0, "ssl_key": 0, "html": 0}
    for _, d in tasks:
        cat = Path(d).name
        if cat in stats:
            stats[cat] += 1

    if _dry_run:
        logging.info("======== DRY RUN 计划(不落盘) ========")
        for src, dest_dir in tasks:
            dst = Path(dest_dir) / Path(src).name
            print(f"PLAN: {src}  ->  {dst}")
        logging.info("======== 计划统计 ========")
        logging.info(
            "总计: %d | content=%d, pcap=%d, ssl_key=%d, html=%d",
            total, stats["content"], stats["pcap"], stats["ssl_key"], stats["html"]
        )
        return

    ok_cnt = 0
    fail_cnt = 0
    moved_cnt = 0
    with ProcessPoolExecutor(max_workers=max(1, _workers)) as ex:
        futures = [ex.submit(copy_one, src, dest_dir) for (src, dest_dir) in tasks]
        for fut in as_completed(futures):
            src, ok, msg, dst_path = fut.result()
            if ok:
                ok_cnt += 1
                if msg == "":
                    moved_cnt += 1
            else:
                fail_cnt += 1
                logging.error("FAIL: %s -> %s", src, msg)

    logging.info(
        "复制完成：成功 %d（其中新复制 %d，已存在跳过 %d），失败 %d，总计 %d。",
        ok_cnt, moved_cnt, ok_cnt - moved_cnt, fail_cnt, ok_cnt + fail_cnt
    )
    logging.info(
        "类别统计：content=%d, pcap=%d, ssl_key=%d, html=%d",
        stats["content"], stats["pcap"], stats["ssl_key"], stats["html"]
    )


# ========= 库/CLI 入口 =========
def main() -> None:
    """库调用推荐：覆盖模块变量后直接 main()；CLI 调用则走 run_cli()"""
    run()  # 使用模块级变量（可能被外部覆盖）


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="只复制目标日期(默认=本地昨天)的 theguardian 四类数据到目标根目录",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--dry-run", action="store_true", help="演练模式：仅打印计划，不产生真实文件移动")
    p.add_argument("--date", metavar="YYYYMMDD", default=None, help="指定要处理的日期；不提供则使用本地昨天")
    p.add_argument("--dest-root", default=DEST_ROOT, help="目标根目录（将创建 content/html/pcap/ssl_key 四个子目录）")
    p.add_argument("--workers", type=int, default=WORKERS, help="并发进程数（非 dry-run 时生效）")
    p.add_argument("--source-glob", dest="source_globs", action="append",
                   help="源抓取根目录的 glob，可重复传多次；不传则使用 SOURCE_ROOT 或默认两条")
    p.add_argument("--log-level", default=LOG_LEVEL, choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="日志级别")
    return p


def run_cli() -> None:
    args = build_parser().parse_args()
    run(
        dry_run=args.dry_run,
        date=args.date,
        dest_root=args.dest_root,
        workers=args.workers,
        source_globs=args.source_globs,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    run_cli()

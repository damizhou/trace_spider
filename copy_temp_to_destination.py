#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多进程复制：
将 /netdisk/theguardian_with_temp/{content,html,pcap,ssl_key} 下的文件，
按文件名中的年份复制到 /netdisk/theguardian_with_ssl_key/<YEAR>/<SUBDIR>/。

- 默认 32 进程（--workers 可调）
- 默认不覆盖；已存在且大小相同 → SKIP；大小不同也 SKIP（除非 --overwrite）
- 支持 --dry-run 试运行
"""

from __future__ import annotations
import argparse
import re
import shutil
from pathlib import Path
from typing import Iterable, Tuple
from functools import partial
from concurrent.futures import ProcessPoolExecutor
import merge_all_csv as mac

SOURCE_ROOT = Path("/netdisk/theguardian_with_temp")
DEST_ROOT   = Path("/netdisk/theguardian_with_ssl_key")
SUBDIRS = ("content", "html", "pcap", "ssl_key")
YEAR_MIN, YEAR_MAX = 1990, 2035

# 预编译正则（顶层定义以便子进程复用）
YEAR_TOKEN_RE = re.compile(r"_(\d{4})_")   # _YYYY_
DATE_TOKEN_RE = re.compile(r"_(\d{8})_")   # _YYYYMMDD_


def extract_year_from_name(name: str) -> int:
    """优先取 '_YYYY_' 首个落在范围的年份；否则回退 '_YYYYMMDD_' 的前四位。"""
    for y in YEAR_TOKEN_RE.findall(name):
        yi = int(y)
        if YEAR_MIN <= yi <= YEAR_MAX:
            return yi
    m = DATE_TOKEN_RE.search(name)
    if m:
        yi = int(m.group(1)[:4])
        if YEAR_MIN <= yi <= YEAR_MAX:
            return yi
    raise ValueError(f"无法从文件名中解析年份: {name}")


def compute_destination(src: Path, dest_root: Path) -> Path:
    """目标路径：<dest_root>/<year>/<subdir>/<filename>"""
    subdir = src.parent.name
    if subdir not in SUBDIRS:
        raise ValueError(f"不支持的子目录: {subdir}（应为 {SUBDIRS} 之一）")
    year = extract_year_from_name(src.name)
    return dest_root / str(year) / subdir / src.name


def iter_source_files(source_root: Path, subdirs: Iterable[str]) -> Iterable[Path]:
    """遍历四类子目录的所有文件（含子目录）。"""
    for sub in subdirs:
        base = source_root / sub
        if not base.exists():
            continue
        yield from (p for p in base.rglob("*") if p.is_file())


def copy_one(src: Path, dst: Path, overwrite: bool, dry_run: bool) -> Tuple[str, str]:
    """
    子进程执行：复制一个文件，返回 (status, message)
    status ∈ {'COPY','SKIP','DRYRUN','ERROR'}
    """
    try:
        dst_parent = dst.parent
        dst_parent.mkdir(parents=True, exist_ok=True)

        if dst.exists() and not overwrite:
            try:
                if dst.stat().st_size == src.stat().st_size:
                    return "SKIP", f"[SKIP] 已存在且大小相同: {dst}"
                else:
                    return "SKIP", f"[SKIP] 已存在（大小不同，未开启 --overwrite）: {dst}"
            except OSError:
                return "SKIP", f"[SKIP] 已存在（无法读取大小，未开启 --overwrite）: {dst}"

        if dry_run:
            return "DRYRUN", f"[DRYRUN] {src} -> {dst}"

        shutil.copy2(src, dst)
        return "COPY", f"[COPY] {src} -> {dst}"

    except Exception as e:
        return "ERROR", f"[ERROR] {src}: {e}"


def process_one(src: Path, dest_root: Path, overwrite: bool, dry_run: bool) -> Tuple[str, str]:
    """包装：计算目标路径后调用 copy_one（便于在主进程中做 map）。"""
    try:
        dst = compute_destination(src, dest_root)
        return copy_one(src, dst, overwrite=overwrite, dry_run=dry_run)
    except Exception as e:
        return "ERROR", f"[ERROR] {src}: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="多进程复制：按文件名中的年份把 temp 下文件复制到 with_ssl_key/<YEAR>/<SUBDIR>/"
    )
    parser.add_argument("--source", type=Path, default=SOURCE_ROOT, help="源根目录（默认：/netdisk/theguardian_with_temp）")
    parser.add_argument("--dest",   type=Path, default=DEST_ROOT,   help="目标根目录（默认：/netdisk/theguardian_with_ssl_key）")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的目标文件（默认不覆盖）")
    parser.add_argument("--dry-run",   action="store_true", help="试运行，仅打印将要执行的操作")
    parser.add_argument("--workers",   type=int, default=32, help="进程数（默认：32）")
    args = parser.parse_args()

    total = copied = skipped = dryrun = errors = 0

    worker = partial(
        process_one,
        dest_root=args.dest,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    # 注意：ProcessPoolExecutor.map 按输入顺序产出结果
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for status, msg in ex.map(worker, iter_source_files(args.source, SUBDIRS), chunksize=64):
            total += 1
            print(msg)
            if status == "COPY":
                copied += 1
            elif status == "SKIP":
                skipped += 1
            elif status == "DRYRUN":
                dryrun += 1
            elif status == "ERROR":
                errors += 1

    tail = "（试运行）" if args.dry_run else ""
    print(f"\n完成。共发现 {total} 个文件；复制 {copied}；跳过 {skipped}；"
          f"{'试运行条目 ' + str(dryrun) + '；' if args.dry_run else ''}错误 {errors}。{tail}")


if __name__ == "__main__":
    main()
    mac.main()

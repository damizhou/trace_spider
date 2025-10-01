#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多进程重置并复制：
- 源：/netdisk/theguardian_with_temp/{content,html,pcap,ssl_key}
- 目标：/netdisk/theguardian_with_ssl_key/<YEAR>/{content,html,pcap,ssl_key}
- 年份取文件名“第二个下划线与第三个下划线之间”的片段（第3个token）
- 目标文件名会移除该年份片段
- 复制前，对将写入的“对应年份”的四个子目录执行删除并重建
- 默认 32 进程；实时输出日志；默认不覆盖
"""

from __future__ import annotations
import argparse
import shutil
from pathlib import Path
from typing import Iterable, Tuple, Set, List
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

SOURCE_ROOT = Path("/temp_theguardian/theguardian_with_temp")
DEST_ROOT   = Path("/netdisk/theguardian_with_ssl_key")
SUBDIRS = ("content", "html", "pcap", "ssl_key")

# ========== 规则函数 ==========

def parse_year_and_new_name(filename: str) -> Tuple[int, str]:
    """
    从文件名中取“第3个token”为年份，并返回移除该token后的新文件名。
    示例:
      in : commentisfree_77145_2013_20250921_21_44_07_theguardian.com.pcap
      out: (2013, commentisfree_77145_20250921_21_44_07_theguardian.com.pcap)
    """
    parts = filename.split("_")
    if len(parts) < 3:
        raise ValueError(f"文件名不符合规则（下划线不足3段）：{filename}")
    year_token = parts[2]
    try:
        year = int(year_token)
    except ValueError:
        raise ValueError(f"第3段不是年份：{filename}")

    # 移除年份段（第3个token）
    new_name = "_".join(parts[:2] + parts[3:])
    return year, new_name


def compute_destination(src: Path, dest_root: Path) -> Path:
    """
    目标路径：<dest_root>/<year>/<subdir>/<new_name-without-year>
    """
    subdir = src.parent.name
    if subdir not in SUBDIRS:
        raise ValueError(f"不支持的子目录: {subdir}")
    year, new_name = parse_year_and_new_name(src.name)
    return dest_root / str(year) / subdir / new_name


def iter_source_files(source_root: Path, subdirs: Iterable[str]) -> Iterable[Path]:
    """遍历四类子目录下所有文件（含子目录）。"""
    for sub in subdirs:
        base = source_root / sub
        if not base.exists():
            continue
        yield from (p for p in base.rglob("*") if p.is_file())


# ========== 复制与并行 ==========

def copy_one(src: Path, dst: Path, overwrite: bool, dry_run: bool) -> Tuple[str, str]:
    """
    子进程执行：复制一个文件，返回 (status, message)
    status ∈ {'COPY','SKIP','DRYRUN','ERROR'}
    """
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)

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
    """包装：计算目标路径后调用 copy_one。"""
    try:
        dst = compute_destination(src, dest_root)
        return copy_one(src, dst, overwrite=overwrite, dry_run=dry_run)
    except Exception as e:
        return "ERROR", f"[ERROR] {src}: {e}"


# ========== 预清理（按年份） ==========

def collect_years_from_source(source_root: Path) -> Set[int]:
    """扫描源目录，收集所有将要写入的年份集合。"""
    years: Set[int] = set()
    for p in iter_source_files(source_root, SUBDIRS):
        try:
            y, _ = parse_year_and_new_name(p.name)
            years.add(y)
        except Exception:
            # 名字不符规则的文件直接跳过，不参与清理
            pass
    return years


def reset_year_dirs(dest_root: Path, years: Iterable[int], dry_run: bool) -> None:
    """
    对于给定年份集合，删除并重建 <dest_root>/<year>/{content,html,pcap,ssl_key}
    """
    for y in sorted(set(years)):
        for sub in SUBDIRS:
            d = dest_root / str(y) / sub
            if d.exists():
                if dry_run:
                    print(f"[DRYRUN-RESET] 将删除目录: {d}", flush=True)
                else:
                    shutil.rmtree(d, ignore_errors=True)
                    print(f"[RESET] 已删除目录: {d}", flush=True)
            # 重建空目录
            if dry_run:
                print(f"[DRYRUN-RESET] 将创建目录: {d}", flush=True)
            else:
                d.mkdir(parents=True, exist_ok=True)
                print(f"[RESET] 已创建目录: {d}", flush=True)


# ========== 主流程 ==========

def main() -> None:
    parser = argparse.ArgumentParser(description="多进程重置并复制（年份=文件名第3段；目标名去年份段）")
    parser.add_argument("--source",   type=Path, default=SOURCE_ROOT, help="源根目录（默认：/temp_theguardian/theguardian_with_temp）")
    parser.add_argument("--dest",     type=Path, default=DEST_ROOT,   help="目标根目录（默认：/netdisk/theguardian_with_ssl_key）")
    parser.add_argument("--workers",  type=int,  default=32,          help="进程数（默认：32）")
    parser.add_argument("--overwrite", action="store_true",           help="允许覆盖已存在目标文件（默认不覆盖）")
    parser.add_argument("--dry-run",   action="store_true",           help="试运行：打印计划删除与复制，不实际操作")
    parser.add_argument("--no-reset",  action="store_true",           help="跳过按年份删除并重建目录（默认会重置）")
    args = parser.parse_args()

    # 先收集将写入的年份，并按要求清理目标目录
    years = collect_years_from_source(args.source)
    if not args.no_reset:
        reset_year_dirs(args.dest, years, dry_run=args.dry_run)

    # 并行复制（实时打印）
    total = copied = skipped = dryrun = errors = 0
    inflight_limit = max(4 * args.workers, 256)

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        src_iter = iter_source_files(args.source, SUBDIRS)

        # 先提交一批任务
        inflight = set()
        try:
            for _ in range(inflight_limit):
                src = next(src_iter)
                fut = ex.submit(process_one, src, args.dest, args.overwrite, args.dry_run)
                inflight.add(fut)
        except StopIteration:
            pass

        # 谁先完成就先打印，并及时补充新任务
        while inflight:
            done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
            for fut in done:
                status, msg = fut.result()
                total += 1
                print(msg, flush=True)
                if status == "COPY":
                    copied += 1
                elif status == "SKIP":
                    skipped += 1
                elif status == "DRYRUN":
                    dryrun += 1
                elif status == "ERROR":
                    errors += 1

                # 尝试补充一个新任务，维持窗口
                try:
                    src = next(src_iter)
                    inflight.add(ex.submit(process_one, src, args.dest, args.overwrite, args.dry_run))
                except StopIteration:
                    pass

    tail = "（试运行）" if args.dry_run else ""
    print(f"\n完成。共处理 {total} 个条目；复制 {copied}；跳过 {skipped}；"
          f"{'试运行条目 ' + str(dryrun) + '；' if args.dry_run else ''}错误 {errors}。{tail}", flush=True)


if __name__ == "__main__":
    main()

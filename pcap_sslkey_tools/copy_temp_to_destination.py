#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按文件名中的年份分发复制 The Guardian 临时数据 → 归档目录。

源目录结构（固定四类）：
  /netdisk/theguardian_with_temp/
    ├─ content/
    ├─ html/
    ├─ pcap/
    └─ ssl_key/

文件命名示例：
  pcap/commentisfree_77145_2013_20250921_21_44_07_theguardian.com.pcap
  html/artanddesign_11_2022_20250920_16_56_53_theguardian.com.html
  ssl_key/stage_186_2003_20250922_00_15_24_theguardian.com_ssl_key.log
  content/books_8017_2005_20250922_00_07_43_theguardian.com.txt

目标目录结构：
  /netdisk/theguardian_with_ssl_key/<YEAR>/<SUBDIR>/<FILENAME>

YEAR 通过文件名中「_YYYY_」首个可用的四位年份提取（1990–2035），
若未命中则回退使用文件名中的日期段「_YYYYMMDD_」前四位。
"""

from __future__ import annotations
import argparse
import re
import shutil
from pathlib import Path
from typing import Iterable

# 默认路径可通过命令行参数覆盖
SOURCE_ROOT = Path("/netdisk/theguardian_with_temp")
DEST_ROOT = Path("/netdisk/theguardian_with_ssl_key")
SUBDIRS = ("content", "html", "pcap", "ssl_key")
YEAR_MIN, YEAR_MAX = 1990, 2035

YEAR_TOKEN_RE = re.compile(r"_(\d{4})_")      # 匹配 _YYYY_
DATE_TOKEN_RE = re.compile(r"_(\d{8})_")      # 匹配 _YYYYMMDD_


def extract_year_from_name(name: str) -> int:
    """
    从文件名中提取年份：
    1) 优先取首个落在 [YEAR_MIN, YEAR_MAX] 的 "_YYYY_"；
    2) 否则回退到 "_YYYYMMDD_" 的前四位。
    若均失败则抛出 ValueError。
    """
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
    """
    由源路径计算目标路径：<dest_root>/<year>/<subdir>/<filename>
    """
    subdir = src.parent.name
    if subdir not in SUBDIRS:
        raise ValueError(f"不支持的子目录: {subdir}（应为 {SUBDIRS} 之一）")
    year = extract_year_from_name(src.name)
    return dest_root / str(year) / subdir / src.name


def iter_source_files(source_root: Path, subdirs: Iterable[str]) -> Iterable[Path]:
    """
    遍历四类子目录下所有文件（包含子文件夹）。
    """
    for sub in subdirs:
        base = source_root / sub
        if not base.exists():
            continue
        # rglob('*') 允许未来扩展更深层目录；只对文件操作
        yield from (p for p in base.rglob("*") if p.is_file())


def copy_one(src: Path, dst: Path, overwrite: bool, dry_run: bool) -> str:
    """
    执行一次复制。返回操作说明字符串（用于打印）。
    跳过规则：目标已存在且尺寸与源一致时直接跳过。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not overwrite:
        try:
            if dst.stat().st_size == src.stat().st_size:
                return f"[SKIP] 已存在且大小相同: {dst}"
        except OSError:
            # 如果 stat 失败，后续按需复制
            pass
    if dry_run:
        return f"[DRYRUN] {src} -> {dst}"
    shutil.copy2(src, dst)
    return f"[COPY] {src} -> {dst}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按文件名中的年份把 /netdisk/theguardian_with_temp 下文件复制到 /netdisk/theguardian_with_ssl_key/<YEAR>/<SUBDIR>/"
    )
    parser.add_argument("--source", type=Path, default=SOURCE_ROOT, help="源根目录（默认：/netdisk/theguardian_with_temp）")
    parser.add_argument("--dest", type=Path, default=DEST_ROOT, help="目标根目录（默认：/netdisk/theguardian_with_ssl_key）")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的目标文件（默认不覆盖，且同大小即跳过）")
    parser.add_argument("--dry-run", action="store_true", help="试运行，仅打印将要执行的操作，不真正复制")
    args = parser.parse_args()

    total, copied, skipped = 0, 0, 0
    for src in iter_source_files(args.source, SUBDIRS):
        total += 1
        try:
            dst = compute_destination(src, args.dest)
            msg = copy_one(src, dst, overwrite=args.overwrite, dry_run=args.dry_run)
            print(msg)
            if msg.startswith("[COPY]"):
                copied += 1
            elif msg.startswith("[SKIP]"):
                skipped += 1
        except Exception as e:
            print(f"[ERROR] {src}: {e}")

    print(f"\n完成。共发现 {total} 个文件；复制 {copied} 个；跳过 {skipped} 个。"
          f"{'（试运行）' if args.dry_run else ''}")


if __name__ == "__main__":
    main()

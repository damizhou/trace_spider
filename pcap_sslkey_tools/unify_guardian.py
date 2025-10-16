#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Guardian 四夹统一 + CSV 补缺清单（并发版）

目录结构（以某年为例）:
  /netdisk/theguardian_with_ssl_key/{YEAR}/
      content/  html/  pcap/  ssl_key/  theguardian_all_reformat/

规则概要：
1) 四夹统一：
   - 同一前缀（形如 section_id，例：artanddesign_1）在 content/html/pcap/ssl_key 四夹中
     必须各有且仅有 1 个文件；缺失任一夹则删除其余夹中该前缀的所有残留。
   - 单个夹内若同一前缀存在多份（不同时间戳版本），保留“最新”一份（优先按文件名内
     的 YYYYMMDD_HH_MM_SS 比较，兜底按 mtime），删除其他。

2) CSV 补缺（并发）：
   - 逐年扫描 theguardian_all_reformat/*.csv（支持逗号/制表/分号分隔; 自动识别）。
   - 仅校验 pcap 是否存在目标前缀（section_id）；如不存在，则把该行追加至
     /home/pcz/code/trace_spider/theguardian_records.csv ，并加列 Year=年份目录名。
   - 并发策略：每个 CSV 一个进程（可用 --csv-workers 限流）。子进程只读，主进程统一去重与写出。

使用示例：
  # 先演练（不删不写）
  python unify_guardian.py --dry-run --years=2012,2013

  # 实际执行（默认处理所有年份目录）
  python unify_guardian.py

  # 并发限流为 8
  python unify_guardian.py --years=2012 --csv-workers=8
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

# ========================== 常量与基础配置 ==========================

BASE_DEFAULT = Path("/netdisk/theguardian_with_ssl_key").resolve()
RECORDS_DEFAULT = Path("/home/pcz/code/trace_spider/theguardian_records.csv").resolve()
FOUR_DIRS = ("content", "html", "pcap", "ssl_key")

# 前缀提取：第二个下划线之前部分（section_id）
# 例：artanddesign_1_20251009_15_14_23_theguardian.com.html  -> artanddesign_1
PREFIX_RE = re.compile(r"^([^_]+)_(\d+)_")

# 时间戳提取：_YYYYMMDD_HH_MM_SS_（中间可有其它字段）
TS_RE = re.compile(r"_(\d{4})(\d{2})(\d{2})_(\d{2})_(\d{2})_(\d{2})_")

# ========================== 日志 ==========================

def setup_logging(log_path: Optional[Path]) -> None:
    fmt = "[%(asctime)s] %(levelname)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt, handlers=handlers)

# ========================== 工具函数 ==========================

def extract_prefix(name: str) -> Optional[str]:
    """抽取 section_id 前缀；失败返回 None。"""
    m = PREFIX_RE.match(name)
    if not m:
        return None
    return f"{m.group(1)}_{m.group(2)}"


def extract_ts_key(name: str) -> Optional[Tuple[int, int, int, int, int, int]]:
    """从文件名中抽取时间戳（YYYYMMDD_HH_MM_SS），失败返回 None。"""
    m = TS_RE.search(name)
    if not m:
        return None
    y, M, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
    return (y, M, d, h, mi, s)


def choose_latest(files: List[Path]) -> Path:
    """
    在一组同前缀文件中选择“最新”：
    优先按文件名时间戳（若有）比较；否则按 mtime（修改时间）。
    """
    def key(p: Path):
        ts = extract_ts_key(p.name)
        mtime = p.stat().st_mtime
        return (ts is not None, ts if ts is not None else (0, 0, 0, 0, 0, 0), mtime)

    return sorted(files, key=key)[-1]


def list_year_dirs(base: Path, years: Optional[List[int]]) -> List[Path]:
    """列出要处理的年份目录。"""
    out = []
    if years:
        for y in years:
            p = base / f"{y}"
            if p.is_dir():
                out.append(p)
            else:
                logging.warning("年份目录不存在: %s", p)
    else:
        for p in sorted(base.iterdir()):
            if p.is_dir() and p.name.isdigit():
                try:
                    yy = int(p.name)
                except ValueError:
                    continue
                if 1900 <= yy <= 2100:
                    out.append(p)
    return out


def open_dict_reader_with_autodelim(csv_path: Path):
    """
    打开 CSV/TSV 并自动识别分隔符，返回 (file_handle, DictReader, delimiter)。
    由调用方负责关闭 file_handle（建议 with 管理）。
    """
    f = csv_path.open("r", encoding="utf-8-sig", newline="")
    sample = f.read(4096) or ""
    f.seek(0)
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])
        delimiter = dialect.delimiter
    except Exception:
        # 简单回退启发：首行是否存在显著分隔
        first_line = sample.splitlines()[0] if sample else ""
        if first_line.count("\t") >= 2 and "Section\t" in first_line:
            delimiter = "\t"
        elif first_line.count(";") >= 2 and "Section;" in first_line:
            delimiter = ";"
        else:
            delimiter = ","
    reader = csv.DictReader(f, delimiter=delimiter)
    return f, reader, delimiter


def build_pcap_prefixes(pcap_dir: Path) -> Set[str]:
    """
    扫描该年 pcap 目录，返回已有的前缀集合（形如 'section_id'）。
    """
    prefixes: Set[str] = set()
    if not pcap_dir.is_dir():
        return prefixes
    for p in pcap_dir.iterdir():
        if not p.is_file():
            continue
        if not p.name.endswith(".pcap"):
            continue
        pref = extract_prefix(p.name)
        if pref:
            prefixes.add(pref)
    return prefixes


# ========================== 四夹统一 ==========================

def unify_four_dirs_for_year(year_dir: Path, dry_run: bool) -> Tuple[int, int, int]:
    """
    执行一年的“四夹统一”：
      - 各夹内同前缀多版本去重，只留最新；
      - 四夹缺一即删掉该前缀的全部候选；
    返回: (kept, removed, affected_prefixes)
          kept: 统一后各夹保留的前缀计数之和（4 个夹之和，不是前缀组数）
          removed: 实际删除的文件个数
          affected_prefixes: 因不完整而被删除的前缀组个数
    """
    per_dir: Dict[str, Dict[str, List[Path]]] = {d: {} for d in FOUR_DIRS}
    for d in FOUR_DIRS:
        dp = year_dir / d
        if not dp.is_dir():
            logging.warning("缺少目录: %s", dp)
            continue
        for p in dp.iterdir():
            if not p.is_file():
                continue
            pref = extract_prefix(p.name)
            if not pref:
                # 非标准命名，不处理
                continue
            per_dir[d].setdefault(pref, []).append(p)

    # 单夹内同前缀多份 -> 只留最新
    to_keep: Dict[str, Dict[str, Path]] = {d: {} for d in FOUR_DIRS}
    to_del: List[Path] = []

    for d in FOUR_DIRS:
        for pref, files in per_dir[d].items():
            if len(files) == 1:
                to_keep[d][pref] = files[0]
            else:
                latest = choose_latest(files)
                to_keep[d][pref] = latest
                for f in files:
                    if f != latest:
                        to_del.append(f)
                        logging.info("[去重] %s 同前缀多份，仅保留最新: %s  删除: %s",
                                     d, latest.name, f.name)

    # 四夹交集：完整前缀
    prefix_sets = [set(to_keep[d].keys()) for d in FOUR_DIRS]
    valid_prefixes = set.intersection(*prefix_sets) if prefix_sets else set()

    # 不完整的前缀：删光其余残留
    all_prefixes = set().union(*prefix_sets) if prefix_sets else set()
    invalid_prefixes = all_prefixes - valid_prefixes
    for pref in sorted(invalid_prefixes):
        for d in FOUR_DIRS:
            f = to_keep[d].get(pref)
            if f:
                to_del.append(f)
                logging.info("[不完整删除] 缺少成组文件，前缀=%s  目录=%s  删除: %s",
                             pref, d, f.name)
                to_keep[d].pop(pref, None)

    # 实际删除（去重 inode）
    removed = 0
    if to_del:
        uniq: List[Path] = []
        seen_inodes = set()
        for f in to_del:
            try:
                st = f.stat()
            except FileNotFoundError:
                continue
            key = (st.st_dev, st.st_ino)
            if key in seen_inodes:
                continue
            seen_inodes.add(key)
            uniq.append(f)

        for f in uniq:
            if dry_run:
                logging.info("[DRY-RUN] 将删除: %s", f)
            else:
                try:
                    f.unlink()
                    removed += 1
                    logging.info("已删除: %s", f)
                except FileNotFoundError:
                    pass
                except Exception as e:
                    logging.error("删除失败: %s  (%s)", f, e)

    kept = sum(len(to_keep[d]) for d in FOUR_DIRS)
    affected = len(invalid_prefixes)
    logging.info("年目录 %s 统一完成：保留(各夹总和)=%d  删除文件=%d  不完整前缀=%d",
                 year_dir.name, kept, removed, affected)
    return kept, removed, affected


# ========================== CSV 并发补缺 ==========================

def _worker_process_csv(csv_path: str,
                        year_str: str,
                        pcap_prefixes: Set[str]) -> Tuple[str, List[Tuple[str, str, str, str]], Optional[str]]:
    """
    子进程：处理单个 CSV，返回 (csv_path, missing_rows, error)
      missing_rows: List[(Section, ID, URL, Year)]
      error: 若列缺失/读取失败则返回字符串描述
    """
    csvp = Path(csv_path)
    missing: List[Tuple[str, str, str, str]] = []
    seen_local: Set[Tuple[str, str]] = set()  # (section,id) 去重（单 CSV 内）

    try:
        fh, reader, delim = open_dict_reader_with_autodelim(csvp)
        with fh:
            cols = {(k or "").strip().lower(): k for k in (reader.fieldnames or [])}
            need = {"section", "id", "url"}
            if not need.issubset(cols.keys()):
                return (csv_path, [], f"列缺失 分隔符={repr(delim)} 现有列={reader.fieldnames}")

            for row in reader:
                section = (row.get(cols["section"], "") or "").strip()
                id_ = str(row.get(cols["id"], "") or "").strip()
                url = (row.get(cols["url"], "") or "").strip()
                if not section or not id_:
                    continue

                k2 = (section, id_)
                if k2 in seen_local:
                    continue
                seen_local.add(k2)

                prefix = f"{section}_{id_}"
                if prefix in pcap_prefixes:
                    continue  # pcap 已存在，无需补
                missing.append((section, id_, url, year_str))

        return (csv_path, missing, None)

    except Exception as e:
        return (csv_path, [], f"{type(e).__name__}: {e}")


def collect_missing_from_csv(year_dir: Path,
                             records_path: Path,
                             dry_run: bool,
                             dedup_existing: bool,
                             csv_workers: Optional[int] = None) -> Tuple[int, int]:
    """
    并发读取 theguardian_all_reformat/*.csv ，仅以 pcap 是否存在判定缺失；
    每个 CSV 启动一个进程（默认），可用 csv_workers 限流。
    返回: (found_missing, wrote)
    """
    reformat_dir = year_dir / "theguardian_all_reformat"
    pcap_dir = year_dir / "pcap"
    if not reformat_dir.is_dir():
        logging.warning("缺少目录: %s", reformat_dir)
        return (0, 0)

    # 读取既有 records 去重（仅主进程做）
    existing: Set[Tuple[str, str, str, str]] = set()
    if dedup_existing and records_path.is_file():
        try:
            with records_path.open("r", encoding="utf-8-sig", newline="") as f:
                r = csv.DictReader(f)
                for row in r:
                    k = (row.get("Section", ""),
                         row.get("ID", ""),
                         row.get("URL", ""),
                         row.get("Year", ""))
                    existing.add(k)
        except Exception as e:
            logging.warning("读取既有记录失败(忽略去重): %s", e)

    # 当年 CSV 列表
    csv_paths = sorted(reformat_dir.glob("*.csv"))
    if not csv_paths:
        logging.info("年目录 %s 无 CSV 文件。", year_dir.name)
        return (0, 0)

    # 预构建 pcap 前缀集合（一次 IO，子进程直接查 set）
    pcap_prefixes = build_pcap_prefixes(pcap_dir)

    # 工作者数量
    max_workers = len(csv_paths) if not csv_workers or csv_workers <= 0 else min(csv_workers, len(csv_paths))
    logging.info("按 CSV 并发处理：CSV 总数=%d  进程数=%d", len(csv_paths), max_workers)

    all_missing: List[Tuple[str, str, str, str]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_worker_process_csv, str(p), year_dir.name, pcap_prefixes)
                for p in csv_paths]
        for fut in as_completed(futs):
            csv_path, missing_rows, err = fut.result()
            if err:
                logging.warning("CSV 列缺失/读取失败(跳过): %s  %s", csv_path, err)
            if missing_rows:
                all_missing.extend(missing_rows)

    # 主进程层面去重（合并多 CSV 的重复项 + 去掉已存在记录）
    if all_missing:
        before = len(all_missing)
        # 保序去重：dict.fromkeys 可保持首次出现顺序（3.7+）
        all_missing = [t for t in dict.fromkeys(all_missing)]
        if existing:
            all_missing = [t for t in all_missing if t not in existing]
        after = len(all_missing)
        if after < before:
            logging.info("去重后缺失记录：%d -> %d", before, after)

    wrote = 0
    if all_missing:
        if dry_run:
            for k in all_missing:
                logging.info("[DRY-RUN] 将写入缺失记录: %s", k)
        else:
            records_path.parent.mkdir(parents=True, exist_ok=True)
            file_exists = records_path.exists()
            with records_path.open("a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Section", "ID", "URL", "Year"])
                for row in all_missing:
                    writer.writerow(list(row))
                    wrote += 1
            logging.info("缺失记录已追加到: %s  条数=%d", records_path, wrote)
    else:
        logging.info("年目录 %s 无缺失记录。", year_dir.name)

    return (len(all_missing), wrote)


# ========================== 主程序 ==========================

def main():
    ap = argparse.ArgumentParser(description="统一 Guardian 四个目录并按 CSV 生成缺失清单（并发版）")
    ap.add_argument("--base-dir", type=Path, default=BASE_DEFAULT,
                    help="根目录（含年份子目录），默认 /netdisk/theguardian_with_ssl_key")
    ap.add_argument("--years", type=str, default="",
                    help="逗号分隔的年份列表；留空=自动扫描所有年份目录，例如 2012,2013")
    ap.add_argument("--records", type=Path, default=RECORDS_DEFAULT,
                    help="缺失清单输出 CSV 路径，默认 /home/pcz/code/trace_spider/theguardian_records.csv")
    ap.add_argument("--dry-run", action="store_true",
                    help="演练：不真正删除/写文件，只输出计划")
    ap.add_argument("--no-dedup-existing", action="store_true",
                    help="追加缺失清单时不去重既有记录")
    ap.add_argument("--skip-unify", action="store_true",
                    help="跳过第一步统一四夹")
    ap.add_argument("--skip-missing", action="store_true",
                    help="跳过第二步按 CSV 补缺清单")
    ap.add_argument("--csv-workers", type=int, default=0,
                    help="处理 CSV 的并发进程数；默认=0 表示每个 CSV 启动一个进程")
    ap.add_argument("--log", type=Path, default=Path(f"./unify_guardian_{datetime.now():%Y%m%d_%H%M%S}.log"),
                    help="日志文件路径（默认写到当前目录）")
    args = ap.parse_args()

    setup_logging(args.log)

    # 解析年份
    years = None
    if args.years.strip():
        years = []
        for tok in args.years.split(","):
            tok = tok.strip()
            if tok.isdigit():
                years.append(int(tok))
            else:
                logging.warning("忽略非法年份: %s", tok)

    base = args.base_dir.resolve()
    if not base.is_dir():
        logging.error("根目录不存在: %s", base)
        sys.exit(2)

    year_dirs = list_year_dirs(base, years)
    if not year_dirs:
        logging.warning("未发现年份目录，退出。")
        return

    total_kept = total_removed = total_aff = 0
    total_missing = total_written = 0

    for ydir in year_dirs:
        logging.info("==== 处理年份目录: %s ====", ydir)
        if not args.skip_unify:
            kept, removed, affected = unify_four_dirs_for_year(ydir, dry_run=args.dry_run)
            total_kept += kept
            total_removed += removed
            total_aff += affected

        if not args.skip_missing:
            found, wrote = collect_missing_from_csv(
                ydir,
                args.records,
                dry_run=args.dry_run,
                dedup_existing=not args.no_dedup_existing,
                csv_workers=args.csv_workers
            )
            total_missing += found
            total_written += wrote

    logging.info("==== 全部完成 ====")
    logging.info("统一统计：保留(各夹前缀计数总和)=%d  删除文件=%d  不完整前缀=%d",
                 total_kept, total_removed, total_aff)
    logging.info("补缺统计：发现缺失=%d  已写入=%d  输出=%s",
                 total_missing, total_written, args.records)


if __name__ == "__main__":
    # 避免 Windows 平台多进程递归导入问题；Linux 下也保持习惯性保护
    main()

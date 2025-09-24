#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 /netdisk/theguardian_with_ssl_key/<year> 下的 pcap 映射到 CSV（guardian_{section}_{year}-Jan-01_to_{year}-Dec-31.csv），
并把记录写入 MySQL 表 theguardian_content。

表字段规则：
- id: 自增（不显式赋值）
- title: 取自 URL 最后段（做了 unquote）
- url: 来自 CSV 的 URL
- type: CSV 的 Section
- year: 年份目录名（int）
- sensitive_flag: -1
- classify_status: 0
- traffic_status: 0
- pcap_path: 实际 pcap 完整路径
- ssl_key_path: 若存在，匹配同名前缀 + "_ssl_key.log"
- content_path: 若存在，匹配同名前缀 + ".txt"
- html_path: 若存在，匹配同名前缀 + ".html"
- update_time / classify_time / traffic_time: 走表默认 CURRENT_TIMESTAMP
- traffic_feature: NULL

幂等策略：
- 逐年加载库内已有的 pcap_path 集合，跳过已存在记录
"""

from __future__ import annotations
import configparser
import csv
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Optional, List, Set
from urllib.parse import urlparse, unquote

# -------- 可按需修改的常量 --------
BASE_DIR = Path("/netdisk/theguardian_with_ssl_key")
TABLE_NAME = "theguardian_content"
BATCH_SIZE = 1000
CONFIG_FILE = Path(__file__).with_name("db_config.ini")

# pcap 文件名解析：section_id_YYYYMMDD_HH_MM_SS_theguardian.com.pcap
PCAP_RE = re.compile(
    r"^(?P<section>[a-z0-9_-]+)_(?P<id>\d+)_\d{8}_\d{2}_\d{2}_\d{2}_theguardian\.com\.pcap$",
    re.IGNORECASE,
)

# 对应文件扩展
EXT_SSL = "_ssl_key.log"
EXT_TXT = ".txt"
EXT_HTML = ".html"


@dataclass(frozen=True)
class Record:
    title: str
    url: str
    type: str
    year: int
    sensitive_flag: int
    classify_status: int
    traffic_status: int
    pcap_path: str
    ssl_key_path: Optional[str]
    content_path: Optional[str]
    html_path: Optional[str]
    traffic_feature: Optional[str] = None


def load_db_cfg(cfg_file: Path) -> dict:
    cp = configparser.ConfigParser()
    if not cfg_file.exists():
        raise FileNotFoundError(f"缺少数据库配置文件：{cfg_file}")
    cp.read(cfg_file, encoding="utf-8")
    if "mysql" not in cp:
        raise ValueError("db_config.ini 中缺少 [mysql] 节")
    section = cp["mysql"]
    return {
        "host": section.get("host", "127.0.0.1"),
        "port": section.getint("port", 3306),
        "user": section.get("user", ""),
        "password": section.get("password", ""),
        "database": section.get("database", ""),
        "charset": section.get("charset", "utf8mb4"),
    }


def connect_mysql(cfg: dict):
    try:
        import pymysql
    except ModuleNotFoundError as e:
        print("缺少依赖：pymysql，请先安装：pip install pymysql", file=sys.stderr)
        raise
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg["charset"],
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def sniff_csv_delimiter(sample_path: Path) -> str:
    """尽量稳妥：优先 Sniffer；失败则逗号"""
    try:
        with sample_path.open("r", encoding="utf-8", newline="") as f:
            head = f.read(4096)
        dialect = csv.Sniffer().sniff(head, delimiters=",;\t|")
        return dialect.delimiter
    except Exception:
        return ","


def build_map_section_id_to_url(csv_dir: Path, year: int) -> Dict[Tuple[str, int], str]:
    """
    读取该年的所有 guardian_*.csv，构建 (Section, ID) -> URL 映射。
    CSV 预期列：Section, ID, URL（不区分大小写；会做 strip）。
    """
    mapping: Dict[Tuple[str, int], str] = {}

    if not csv_dir.is_dir():
        return mapping

    csv_files = sorted(csv_dir.glob("guardian_*_{}-Jan-01_to_{}-Dec-31.csv".format(year, year)))
    for csv_file in csv_files:
        delim = sniff_csv_delimiter(csv_file)
        with csv_file.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=delim)
            # 兼容大小写/空白
            # 标题标准化
            def norm(k: str) -> str:
                return (k or "").strip().lower()

            field_map = {norm(k): k for k in reader.fieldnames or []}
            for required in ("section", "id", "url"):
                if required not in field_map:
                    raise ValueError(f"CSV 缺少列 {required}: {csv_file}")

            for row in reader:
                try:
                    section = (row[field_map["section"]] or "").strip()
                    id_str = (row[field_map["id"]] or "").strip()
                    url = (row[field_map["url"]] or "").strip()
                    if not section or not id_str or not url:
                        continue
                    key = (section, int(id_str))
                    # 若重复，后者覆盖前者（一般不会）
                    mapping[key] = url
                except Exception:
                    # 某行异常则跳过
                    continue

    return mapping


def url_to_title(url: str) -> str:
    """从 URL 取最后一段作为标题（去掉查询、去掉尾斜杠，unquote）"""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    seg = path.split("/")[-1] if path else ""
    # 有些链接可能以数字/空结尾，兜底给整段最后
    title = unquote(seg) if seg else unquote(path)
    return title or ""


def iter_pcap_files(pcap_dir: Path):
    """遍历 pcap 目录，返回 (file_path, section, id)"""
    for p in sorted(pcap_dir.glob("*.pcap")):
        m = PCAP_RE.match(p.name)
        if not m:
            continue
        section = m.group("section")
        idx = int(m.group("id"))
        yield p, section, idx


def derive_sibling_paths(year_dir: Path, stem: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    根据 pcap 的 stem（不含扩展名）推导 ssl_key/content/html 的文件路径，存在则返回绝对路径，否则 None。
    """
    ssl_dir = year_dir / "ssl_key"
    content_dir = year_dir / "content"
    html_dir = year_dir / "html"

    ssl_path = (ssl_dir / f"{stem}{EXT_SSL}").as_posix() if ssl_dir.is_dir() and (ssl_dir / f"{stem}{EXT_SSL}").exists() else None
    content_path = (content_dir / f"{stem}{EXT_TXT}").as_posix() if content_dir.is_dir() and (content_dir / f"{stem}{EXT_TXT}").exists() else None
    html_path = (html_dir / f"{stem}{EXT_HTML}").as_posix() if html_dir.is_dir() and (html_dir / f"{stem}{EXT_HTML}").exists() else None
    return ssl_path, content_path, html_path


def load_existing_pcap_set_by_year(conn, year: int) -> Set[str]:
    """
    按年加载库内已有记录的 pcap_path 集合（用前缀 LIKE 过滤，避免全表扫描）。
    """
    prefix = f"{BASE_DIR.as_posix().rstrip('/')}/{year}/pcap/%"
    sql = f"SELECT pcap_path FROM {TABLE_NAME} WHERE pcap_path LIKE %s"
    with conn.cursor() as cur:
        cur.execute(sql, (prefix,))
        rows = cur.fetchall()
    return {r["pcap_path"] for r in rows if r.get("pcap_path")}


def insert_batch(conn, rows: List[Record]) -> int:
    if not rows:
        return 0
    cols = (
        "title", "url", "type", "year",
        "sensitive_flag", "classify_status", "traffic_status",
        "pcap_path", "ssl_key_path", "content_path", "html_path", "traffic_feature"
    )
    placeholders = ", ".join(["%s"] * len(cols))
    sql = f"INSERT INTO {TABLE_NAME} ({', '.join(cols)}) VALUES ({placeholders})"
    data = [
        (
            r.title, r.url, r.type, r.year,
            r.sensitive_flag, r.classify_status, r.traffic_status,
            r.pcap_path, r.ssl_key_path, r.content_path, r.html_path, r.traffic_feature
        ) for r in rows
    ]
    with conn.cursor() as cur:
        cur.executemany(sql, data)
    return len(rows)


def main():
    start_ts = time.time()
    cfg = load_db_cfg(CONFIG_FILE)
    conn = connect_mysql(cfg)
    total_inserted = 0
    total_skipped_no_csv = 0
    total_skipped_existing = 0
    total_skipped_no_url = 0

    try:
        if not BASE_DIR.is_dir():
            print(f"[FATAL] 根目录不存在：{BASE_DIR}", file=sys.stderr)
            return

        # 遍历年份目录（仅处理包含 pcap/ 的年份）
        year_dirs = [p for p in sorted(BASE_DIR.iterdir()) if p.is_dir() and p.name.isdigit()]
        for year_dir in year_dirs:
            year = int(year_dir.name)
            pcap_dir = year_dir / "pcap"
            if not pcap_dir.is_dir():
                print(f"[SKIP] {year} 无 pcap/，整年跳过")
                continue

            csv_dir = year_dir / "theguardian_all_reformat"
            mapping = build_map_section_id_to_url(csv_dir, year)
            if not mapping:
                print(f"[WARN] {year} 未发现可用 CSV 映射（{csv_dir}），该年的 pcap 将全部跳过")
                total_skipped_no_csv += sum(1 for _ in iter_pcap_files(pcap_dir))
                continue

            existing_pcap = load_existing_pcap_set_by_year(conn, year)
            print(f"[INFO] {year}: 已存在 {len(existing_pcap)} 条记录，将跳过重复 pcap_path")

            batch: List[Record] = []
            batch_count = 0
            inserted_this_year = 0

            for pcap_file, section, idx in iter_pcap_files(pcap_dir):
                pcap_path = pcap_file.as_posix()
                if pcap_path in existing_pcap:
                    total_skipped_existing += 1
                    continue

                key = (section, idx)
                url = mapping.get(key)
                if not url:
                    total_skipped_no_url += 1
                    continue

                title = url_to_title(url)
                stem = pcap_file.stem  # 不含 .pcap
                ssl_key_path, content_path, html_path = derive_sibling_paths(year_dir, stem)

                rec = Record(
                    title=title,
                    url=url,
                    type=section,
                    year=year,
                    sensitive_flag=-1,
                    classify_status=0,
                    traffic_status=0,
                    pcap_path=pcap_path,
                    ssl_key_path=ssl_key_path,
                    content_path=content_path,
                    html_path=html_path,
                    traffic_feature=None,
                )
                batch.append(rec)
                if len(batch) >= BATCH_SIZE:
                    n = insert_batch(conn, batch)
                    conn.commit()
                    inserted_this_year += n
                    total_inserted += n
                    batch_count += 1
                    print(f"[INFO] {year}: 批次 {batch_count} 已插入 {n} 条（累计 {inserted_this_year}）")
                    batch.clear()

            if batch:
                n = insert_batch(conn, batch)
                conn.commit()
                inserted_this_year += n
                total_inserted += n
                batch_count += 1
                print(f"[INFO] {year}: 批次 {batch_count} 已插入 {n} 条（累计 {inserted_this_year}）")
                batch.clear()

            print(f"[DONE] {year}: 新增 {inserted_this_year} 条")

        dur = time.time() - start_ts
        print(f"\n[SUMMARY] 新增: {total_inserted} | 跳过(无CSV): {total_skipped_no_csv} | 跳过(已存在): {total_skipped_existing} | 跳过(无URL映射): {total_skipped_no_url} | 用时: {dur:.1f}s")

    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
非递归扫描 /netdisk/wiki_with_ssl_key/pcap 目录下的 .pcap 文件：
- 文件名形如 1006692_20250817_11_06_01_zh.wikipedia.org.pcap
  其中 1006692 = 表 wikicontent_test 的主键 id（唯一）
- 若该 id 的 ssl_key_path 为空 且 classify_status=1 且 traffic_status=1，则更新
  pcap_path 与 ssl_key_path（其他字段不变）
"""

import os
import re
import sys
import traceback
from typing import Optional
import pymysql  # pip install pymysql

# ======== 硬编码区（按需修改）========
PCAP_DIR = "/netdisk/wiki_with_ssl_key/pcap"     # 仅扫描这一层
SSL_DIR  = "/netdisk/wiki_with_ssl_key/ssl_key"

MYSQL_HOST = "82.157.167.184"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "cLYUP^CH"
MYSQL_DB = "nsdbs"
TABLE_NAME = "wikicontent"

DRY_RUN = False            # True=只打印计划，不写库
REQUIRE_SSL_EXISTS = True  # True=只有对应 ssl_key 文件存在才更新

# 文件名正则：id_YYYYMMDD_HH_MM_SS_zh.wikipedia.org.pcap
FNAME_RE = re.compile(
    r"^(?P<id>\d+)_\d{8}_\d{2}_\d{2}_\d{2}_zh\.wikipedia\.org\.pcap$"
)
# ====================================


def iter_pcap_files_non_recursive(base_dir: str):
    """只遍历当前目录，不递归子目录。"""
    try:
        with os.scandir(base_dir) as it:
            for entry in it:
                if entry.is_file() and entry.name.endswith(".pcap"):
                    yield entry.path
    except FileNotFoundError:
        print(f"[ERROR] 目录不存在：{base_dir}", file=sys.stderr)


def parse_id_from_filename(path: str) -> Optional[int]:
    m = FNAME_RE.match(os.path.basename(path))
    if not m:
        return None
    return int(m.group("id"))


def derive_ssl_key_path(pcap_path: str) -> str:
    base = os.path.basename(pcap_path)
    stem = base[:-5]  # 去掉 .pcap
    return os.path.join(SSL_DIR, f"{stem}_ssl_key.log")


def get_db_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        autocommit=True,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
    )


def update_paths_for_id(cur, _id: int, pcap_path: str, ssl_key_path: str) -> int:
    """
    满足条件才更新：
      - ssl_key_path 为 NULL 或 ''
      - classify_status = 1
      - traffic_status = 1
    返回影响行数
    """
    sql = f"""
        UPDATE {TABLE_NAME}
        SET pcap_path=%s, ssl_key_path=%s
        WHERE id=%s
          AND (ssl_key_path IS NULL OR ssl_key_path='')
          AND classify_status=1
          AND traffic_status=1
    """
    cur.execute(sql, (pcap_path, ssl_key_path, _id))
    return cur.rowcount


def main():
    total = 0
    badname = 0
    skip_ssl_missing = 0
    will_update = 0
    updated = 0
    noop = 0

    try:
        conn = get_db_conn()
    except Exception as e:
        print("[ERROR] 无法连接数据库：", e, file=sys.stderr)
        sys.exit(2)

    with conn:
        with conn.cursor() as cur:
            for pcap in iter_pcap_files_non_recursive(PCAP_DIR):
                total += 1
                _id = parse_id_from_filename(pcap)
                if _id is None:
                    badname += 1
                    print(f"[WARN] 文件名不匹配，跳过：{pcap}")
                    continue

                ssl_path = derive_ssl_key_path(pcap)

                if REQUIRE_SSL_EXISTS and not os.path.exists(ssl_path):
                    skip_ssl_missing += 1
                    print(f"[SKIP] ssl_key 不存在，略过 id={_id} -> {ssl_path}")
                    continue

                print(f"[PLAN] id={_id}\n       pcap={pcap}\n       ssl ={ssl_path}")
                will_update += 1

                if DRY_RUN:
                    continue

                try:
                    affected = update_paths_for_id(cur, _id, pcap, ssl_path)
                    if affected > 0:
                        updated += 1
                        print(f"[OK] 已更新 id={_id}（受影响行={affected}）")
                    else:
                        noop += 1
                        print(f"[NOOP] 条件不满足或无此 id，未更新 id={_id}")
                except Exception:
                    print(f"[ERROR] 更新 id={_id} 失败：\n{traceback.format_exc()}", file=sys.stderr)

    print("\n===== 汇总（非递归）=====")
    print(f"扫描文件数: {total}")
    print(f"文件名不匹配: {badname}")
    print(f"跳过（ssl_key 不存在）: {skip_ssl_missing}")
    print(f"计划更新条目: {will_update}" + ("  [DRY-RUN]" if DRY_RUN else ""))
    if not DRY_RUN:
        print(f"数据库实际更新成功: {updated}")
        print(f"数据库未更新（条件未满足/无此 id）: {noop}")


if __name__ == "__main__":
    main()

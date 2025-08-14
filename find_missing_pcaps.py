#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import sys

# —— 配置 ——
# .pcap 文件所在目录（一层）
PCAP_DIR = "/netdisk/wiki_with_ssl_key/pcap"
# CSV 文件路径，包含 id 列
CSV_FILE = "./wikicontent_130w.csv"
# 输出缺失记录的 CSV 文件路径
OUTPUT_CSV_FILE = "./missing_records.csv"
# CSV 分隔符，若为制表符则设置为 "\t"，默认 ","
DELIMITER = "\t"


def main():
    # 1. 提取目录中所有 .pcap 文件的前缀 ID
    try:
        filenames = os.listdir(PCAP_DIR)
    except OSError as e:
        print(f"无法读取目录 {PCAP_DIR}：{e}", file=sys.stderr)
        sys.exit(1)

    pcap_ids = set()
    for fname in filenames:
        if fname.lower().endswith(".pcap"):
            prefix = fname.split("_", 1)[0]
            pcap_ids.add(prefix)

    # 2. 读取 CSV 文件中的 id 列
    csv_ids = []
    rows = []  # 保存所有 CSV 行
    try:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=DELIMITER)
            fieldnames = reader.fieldnames
            if not fieldnames or "id" not in fieldnames:
                print(f"CSV 文件中未找到名为 'id' 的列，当前列头：{fieldnames}", file=sys.stderr)
                sys.exit(1)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        print(f"CSV 文件 {CSV_FILE} 不存在。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"读取 CSV 时出错：{e}", file=sys.stderr)
        sys.exit(1)

    # 3. 计算缺失的 ID
    missing = []
    for row in rows:
        if row["id"] in pcap_ids:
            continue
        else:
            missing.append(row)
            print(row["id"])
    print('找到的记录数:', len(missing))

    # 4. 重置新的csv文件
    if os.path.exists(OUTPUT_CSV_FILE):
        os.remove(OUTPUT_CSV_FILE)

   # 5. 保存缺失记录到新的 CSV 文件
    try:
        with open(OUTPUT_CSV_FILE, "w", newline="", encoding="utf-8") as outf:
            writer = csv.DictWriter(outf, fieldnames=fieldnames, delimiter=DELIMITER)
            writer.writeheader()
            for row in missing:
                writer.writerow(row)
            print(f"缺失文件已写入{OUTPUT_CSV_FILE}")
    except Exception as e:
        print(f"写入缺失记录文件时出错：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

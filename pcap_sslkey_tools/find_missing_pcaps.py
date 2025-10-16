#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import sys

# —— 配置 ——
# .pcap 文件所在目录（一层）
PCAP_DIR = "/temp_theguardian/theguardian_with_temp/pcap"
# CSV 文件路径，包含 id 列
CSV_FILE = "/home/pcz/code/trace_spider/theguardian_records.csv"
# CSV_FILE = "../missing_records.csv"
# 输出缺失记录的 CSV 文件路径
# OUTPUT_CSV_FILE = "./missing_records.csv"
OUTPUT_CSV_FILE = "/home/pcz/code/trace_spider/theguardian_records.csv"
# CSV 分隔符，若为制表符则设置为 "\t"，默认 ","
DELIMITER = ","


def main() -> bool:
    # 1. 提取目录中所有 .pcap 文件的前缀 ID
    try:
        filenames = os.listdir(PCAP_DIR)
    except OSError as e:
        print(f"无法读取目录 {PCAP_DIR}：{e}", file=sys.stderr)
        sys.exit(1)

    pcap_ids = set()
    for fname in filenames:
        if fname.lower().endswith(".pcap"):
            elements = fname.split("_")
            prefix = elements[0]
            index = elements[1]
            year = elements[2]
            target = f"{prefix}_{index}_{year}"
            if target in pcap_ids:
                print(f"警告：发现重复的 .pcap 文件前缀 ID：{target}, filename:{fname}", file=sys.stderr)
            pcap_ids.add(target)
        else:
            print(f"跳过非 .pcap 文件：{fname}")
    print(f"目录 {PCAP_DIR} 中找到 {len(pcap_ids)} 个 .pcap 文件前缀 ID。")

    # 2. 读取 CSV 文件中的 id 列
    rows = []  # 保存所有 CSV 行
    try:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=DELIMITER)
            fieldnames = reader.fieldnames
            if not fieldnames or "ID" not in fieldnames:
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
    print(f"CSV 文件 {CSV_FILE} 中读取了 {len(rows)} 条记录。")

    # 3. 计算缺失的 ID
    missing = []
    for row in rows:
        target = f"{row['Section']}_{row['ID']}_{row['Year']}"
        if target in pcap_ids:
            pcap_ids.remove(target)  # 防止重复打印
            continue
        else:
            missing.append(row)
            # print(target)
    print('找到缺失的记录数:', len(missing))

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

    if missing:
        return True
    else:
        return False


if __name__ == "__main__":
    main()

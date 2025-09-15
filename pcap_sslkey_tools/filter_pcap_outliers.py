#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import statistics

# BASE_DIR = '/netdisk/wiki'
BASE_DIR = '/netdisk/theguardian_with_ssl_key/pcap'
OUTLIER_DIR = os.path.join(BASE_DIR, 'outliers')

def find_pcap_files(base_dir):
    """返回 base_dir 下（仅一层）所有 .pcap 文件的绝对路径列表"""
    return [
        os.path.join(base_dir, fn)
        for fn in os.listdir(base_dir)
        if fn.lower().endswith('.pcap')
           and os.path.isfile(os.path.join(base_dir, fn))
    ]

def main():
    # 1. 收集所有 pcap 文件及其大小
    files = find_pcap_files(BASE_DIR)
    if not files:
        print(f"No .pcap files found in {BASE_DIR}")
        return

    lower = 245041

    removed = []
    for fp in files:
        size = os.path.getsize(fp)
        if size < lower:
            os.remove(fp)
            removed.append(fp)
            print(f"  {fp} — {size} bytes")

    print(f"removed {len(removed)} files.")

if __name__ == '__main__':
    main()

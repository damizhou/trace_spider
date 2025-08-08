#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import statistics

BASE_DIR = '/netdisk/wiki'
OUTLIER_DIR = os.path.join(BASE_DIR, 'outliers')

def find_pcap_files(base_dir):
    """返回 base_dir 下（仅一层）所有 .pcap 文件的绝对路径列表"""
    return [
        os.path.join(base_dir, fn)
        for fn in os.listdir(base_dir)
        if fn.lower().endswith('.pcap')
           and os.path.isfile(os.path.join(base_dir, fn))
    ]

def compute_normal_bounds(sizes):
    """
    基于正态分布：计算均值 μ、标准差 σ
    并返回下限 μ - 3σ、上限 μ + 3σ
    """
    mu = statistics.mean(sizes)
    # 如果你认为样本就是全集，用 pstdev；若认为是样本的一部分，可用 stdev
    sigma = statistics.pstdev(sizes)
    lower = mu - sigma
    upper = mu + sigma
    return lower, upper, mu, sigma

def main():
    # 1. 收集所有 pcap 文件及其大小
    files = find_pcap_files(BASE_DIR)
    if not files:
        print(f"No .pcap files found in {BASE_DIR}")
        return

    sizes = [os.path.getsize(f) for f in files]

    # 2. 计算 μ、σ 和正常范围
    lower, upper, mu, sigma = compute_normal_bounds(sizes)
    print(f"均值 μ = {mu:.2f} bytes，σ = {sigma:.2f} bytes")
    print(f"正常大小范围：[{lower:.2f}, {upper:.2f}] bytes")

    # 3. 准备 outliers 目录
    os.makedirs(OUTLIER_DIR, exist_ok=True)

    # 4. 剔除（移动）超出 3σ 范围的文件
    removed = []
    for fp, sz in zip(files, sizes):
        if sz < lower:
            dst = os.path.join(OUTLIER_DIR, os.path.basename(fp))
            shutil.move(fp, dst)
            removed.append((fp, sz))

    # 5. 打印结果
    if removed:
        print("以下文件大小超出 3σ 范围，已移至 outliers：")
        for fp, sz in removed:
            print(f"  {fp} — {sz} bytes")
    else:
        print("未发现超出 3σ 范围的文件。")
    print(f"removed {len(removed)} files.")

if __name__ == '__main__':
    main()

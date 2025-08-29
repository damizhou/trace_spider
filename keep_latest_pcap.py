#!/usr/bin/env python3
import argparse
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# 匹配示例：
# 34657_20250812_09_24_11_zh.wikipedia.org.pcap
FNAME_RE = re.compile(r'^(\d+)_([0-9]{8}_[0-9]{2}_[0-9]{2}_[0-9]{2})_.*\.pcap$')

def parse_ts(ts: str) -> datetime:
    # '20250812_09_24_11' -> datetime
    return datetime.strptime(ts, '%Y%m%d_%H_%M_%S')

def scan_pcap(dir_path: Path) -> List[Path]:
    pcs = []
    with os.scandir(dir_path) as it:
        for e in it:
            if not e.is_file():
                continue
            # 只看 .pcap 结尾
            if not e.name.endswith('.pcap'):
                continue
            pcs.append(Path(e.path))
    return pcs

def plan_deletions(files: List[Path]) -> Tuple[Dict[str, Path], Dict[str, List[Path]]]:
    """
    返回：
      keep:   每个id保留的最新文件
      remove: 每个id将删除的旧文件列表
    """
    latest: Dict[str, Tuple[datetime, Path]] = {}
    bucket: Dict[str, List[Tuple[datetime, Path]]] = {}

    for fp in files:
        m = FNAME_RE.match(fp.name)
        if not m:
            # 不符合命名规则，跳过
            continue
        fid, ts = m.group(1), m.group(2)
        dt = parse_ts(ts)
        bucket.setdefault(fid, []).append((dt, fp))
        if (fid not in latest) or (dt > latest[fid][0]):
            latest[fid] = (dt, fp)

    keep: Dict[str, Path] = {}
    remove: Dict[str, List[Path]] = {}

    for fid, (dt_keep, fp_keep) in latest.items():
        keep[fid] = fp_keep
        # 该ID下其余文件全部删除
        olds = []
        for dt, fp in bucket.get(fid, []):
            if fp != fp_keep:
                olds.append(fp)
        if olds:
            remove[fid] = sorted(olds, key=lambda p: p.name)  # 仅为输出整齐
    return keep, remove

def human_size(n: int) -> str:
    for unit in ['B','KB','MB','GB','TB']:
        if n < 1024:
            return f"{n:.2f}{unit}"
        n /= 1024
    return f"{n:.2f}PB"

def main():
    dset_dir = r'/netdisk/wiki_with_ssl_key/pcap'

    files = scan_pcap(dset_dir)
    keep, remove = plan_deletions(files)

    # 汇总统计
    to_delete: List[Path] = [fp for lst in remove.values() for fp in lst]
    total_bytes = 0
    for fp in to_delete:
        try:
            total_bytes += fp.stat().st_size
        except FileNotFoundError:
            pass


    print("\n=== 计划删除的旧文件（按ID分组） ===")
    if not to_delete:
        print("无可删除的旧文件。")
    else:
        for fid in sorted(remove.keys(), key=int):
            print(f"\nID {fid}:")
            for fp in remove[fid]:
                try:
                    sz = human_size(fp.stat().st_size)
                except FileNotFoundError:
                    sz = "N/A"
                print(f"  {fp.name}  ({sz})")

        print(f"\n合计待删除文件数: {len(to_delete)}")
        print(f"预计可释放空间: {human_size(total_bytes)}")

    print("\n[Dry-run] 未执行删除。确认无误后，可加 --delete 参数实际删除。")
    return

    # 实际删除
    print("\n开始删除 ...")
    success, fail = 0, 0
    for fp in to_delete:
        try:
            fp.unlink()
            success += 1
        except Exception as e:
            print(f"删除失败: {fp}  错误: {e}")
            fail += 1

    print(f"删除完成：成功 {success}，失败 {fail}。")

if __name__ == "__main__":
    main()

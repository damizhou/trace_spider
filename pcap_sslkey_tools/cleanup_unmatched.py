#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from pathlib import Path
import stat

PCAP_DIR_DEFAULT = "/netdisk/github_with_ssl_key/pcap"
SSL_DIR_DEFAULT  = "/netdisk/github_with_ssl_key/ssl_key"

def scan_pairs(dir_path: Path, mode: str):
    """
    返回：
      - prefix_to_path: {prefix: 文件完整路径}
      - files: 全部符合模式的文件列表
    mode: "pcap" 或 "ssl"
    """
    prefix_to_path = {}
    files = []
    with os.scandir(dir_path) as it:
        for e in it:
            if not e.is_file():
                continue
            name = e.name
            if mode == "pcap" and name.endswith(".pcap"):
                prefix = name[:-len(".pcap")]
            elif mode == "ssl" and name.endswith("_ssl_key.log"):
                prefix = name[:-len("_ssl_key.log")]
            else:
                continue
            p = dir_path / name
            files.append(p)
            # 假设无重名，若有重复，保留较新的那个
            if prefix in prefix_to_path:
                # 选择最近修改的
                if p.stat().st_mtime > prefix_to_path[prefix].stat().st_mtime:
                    prefix_to_path[prefix] = p
            else:
                prefix_to_path[prefix] = p
    return prefix_to_path, files

def safe_delete(path: Path, try_chmod: bool):
    try:
        os.remove(path)
        return True, None
    except PermissionError as e:
        if try_chmod:
            try:
                # 给自己加写权限再试一次
                os.chmod(path, path.stat().st_mode | stat.S_IWUSR)
                os.remove(path)
                return True, None
            except Exception as e2:
                return False, f"PermissionError，chmod后仍失败: {e2}"
        return False, f"PermissionError: {e}"
    except FileNotFoundError:
        return True, None  # 已被其它进程删掉也算成功
    except Exception as e:
        return False, str(e)

def main():

    pcap_dir = Path(PCAP_DIR_DEFAULT)
    ssl_dir  = Path(SSL_DIR_DEFAULT)

    if not pcap_dir.is_dir() or not ssl_dir.is_dir():
        raise SystemExit(f"目录不存在：pcap={pcap_dir} ssl={ssl_dir}")

    pcap_map, _ = scan_pairs(pcap_dir, "pcap")
    ssl_map,  _ = scan_pairs(ssl_dir, "ssl")

    pcap_prefixes = set(pcap_map.keys())
    ssl_prefixes  = set(ssl_map.keys())

    only_pcap = pcap_prefixes - ssl_prefixes   # 这些 pcap 没有对应的 ssl_key，应删除
    only_ssl  = ssl_prefixes  - pcap_prefixes  # 这些 ssl_key 没有对应的 pcap，应删除

    to_delete = [pcap_map[p] for p in sorted(only_pcap)] + [ssl_map[p] for p in sorted(only_ssl)]

    print(f"pcap 总数: {len(pcap_prefixes)}, ssl_key 总数: {len(ssl_prefixes)}")
    print(f"不匹配的 pcap: {len(only_pcap)} 个，不匹配的 ssl_key: {len(only_ssl)} 个")
    if not to_delete:
        print("✅ 没有需要删除的文件，一切已匹配。")
        return

    print("\n将删除以下文件：")
    for p in to_delete:
        print(str(p))



    print("\n开始删除 ...")
    ok, fail = 0, 0
    for p in to_delete:
        success, err = safe_delete(p, True)
        if success:
            ok += 1
        else:
            fail += 1
            print(f"❌ 删除失败: {p}\n   原因: {err}")

    print(f"\n完成。成功删除 {ok} 个，失败 {fail} 个。")

if __name__ == "__main__":
    main()

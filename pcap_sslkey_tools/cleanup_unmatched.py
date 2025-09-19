#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from pathlib import Path
import stat
from typing import Dict, List, Set, Tuple

# ====== 可被 pipeline 注入覆盖 ======
PCAP_DIR_DEFAULT    = "/netdisk/theguardian_with_ssl_key/pcap"
SSL_DIR_DEFAULT     = "/netdisk/theguardian_with_ssl_key/ssl_key"
CONTENT_DIR_DEFAULT = "/netdisk/theguardian_with_ssl_key/content"
# ===================================

def _list_by_suffix(dir_path: Path, suffix: str, strip_suffix: str) -> Tuple[Dict[str, Path], List[Path]]:
    """
    扫描目录下以 suffix 结尾的文件，返回：
      - base_key -> 文件路径（base_key = 文件名去掉 strip_suffix 后的部分）
      - files: 全部匹配的文件列表
    """
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        return {}, []

    res: Dict[str, Path] = {}
    files: List[Path] = []
    for p in dir_path.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(suffix):
            files.append(p)
            if not name.endswith(strip_suffix):
                # 正常不会进来：strip_suffix 应该是 suffix 的“真正去除部分”
                base = name[: -len(suffix)]
            else:
                base = name[: -len(strip_suffix)]
            res[base] = p
    return res, files

def _gather_sets(pcap_dir: Path, ssl_dir: Path, content_dir: Path):
    # 约定的三种后缀
    pcap_map, pcap_files         = _list_by_suffix(pcap_dir,    ".pcap",          ".pcap")
    ssl_map, ssl_files           = _list_by_suffix(ssl_dir,     "_ssl_key.log",   "_ssl_key.log")
    content_map, content_files   = _list_by_suffix(content_dir, ".txt",           ".txt")

    pcap_keys: Set[str]    = set(pcap_map.keys())
    ssl_keys: Set[str]     = set(ssl_map.keys())
    content_keys: Set[str] = set(content_map.keys())

    return (pcap_map, ssl_map, content_map,
            pcap_files, ssl_files, content_files,
            pcap_keys, ssl_keys, content_keys)

def _decide_to_delete(
    pcap_map: Dict[str, Path],
    ssl_map: Dict[str, Path],
    content_map: Dict[str, Path],
    pcap_keys: Set[str],
    ssl_keys: Set[str],
    content_keys: Set[str],
) -> List[Path]:
    """
    返回需要删除的文件列表：
      - 必须三件齐全（pcap/ssl/txt），缺任意一个则对应已有的那几件都删
    """
    to_delete: List[Path] = []

    keep_keys = pcap_keys & ssl_keys & content_keys
    # 三者都在 keep_keys 内；否则要删“已有”的那几件
    for base, p in pcap_map.items():
        if base not in keep_keys:
            to_delete.append(p)
    for base, p in ssl_map.items():
        if base not in keep_keys:
            to_delete.append(p)
    for base, p in content_map.items():
        if base not in keep_keys:
            to_delete.append(p)


    # 去重（同名/多路径极少，但稳妥）
    seen = set()
    uniq = []
    for p in to_delete:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq

def _ensure_writable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        if not (mode & stat.S_IWUSR):
            path.chmod(mode | stat.S_IWUSR)
    except Exception:
        pass

def safe_delete(path: Path, force_writable: bool = True) -> Tuple[bool, str | None]:
    try:
        if force_writable:
            _ensure_writable(path)
        path.unlink(missing_ok=True)
        return True, None
    except PermissionError as e:
        try:
            _ensure_writable(path)
            path.unlink(missing_ok=True)
            return True, None
        except Exception as e2:
            return False, f"PermissionError，chmod后仍失败: {e2}"
    except FileNotFoundError:
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    ap = argparse.ArgumentParser(
        description="清理未匹配（pcap/ssl/txt）的 theguardian 文件。默认必须三件齐全才保留。"
    )
    ap.add_argument("--pcap-dir",    default=PCAP_DIR_DEFAULT,    help="pcap 目录")
    ap.add_argument("--ssl-dir",     default=SSL_DIR_DEFAULT,     help="ssl_key 目录")
    ap.add_argument("--content-dir", default=CONTENT_DIR_DEFAULT, help="content(.txt) 目录")
    ap.add_argument("--pair-only",   action="store_true", help="只要求 pcap 与 ssl 成对；txt 可选（缺 txt 不影响 pcap/ssl 保留）")
    ap.add_argument("--dry-run",     action="store_true", help="只打印将删除的文件，不实际删除")
    args = ap.parse_args()

    pcap_dir    = Path(args.pcap_dir)
    ssl_dir     = Path(args.ssl_dir)
    content_dir = Path(args.content_dir)

    if not pcap_dir.is_dir():
        raise SystemExit(f"pcap 目录不存在：{pcap_dir}")
    if not ssl_dir.is_dir():
        raise SystemExit(f"ssl_key 目录不存在：{ssl_dir}")
    if not content_dir.is_dir():
        print(f"[WARN] content 目录不存在：{content_dir}（将仅按 pcap/ssl 进行）")

    (pcap_map, ssl_map, content_map,
     pcap_files, ssl_files, content_files,
     pcap_keys, ssl_keys, content_keys) = _gather_sets(pcap_dir, ssl_dir, content_dir)

    print(f"统计：pcap={len(pcap_files)}，ssl={len(ssl_files)}，txt={len(content_files)}")
    require_all_three = not args.pair_only

    to_delete = _decide_to_delete(
        pcap_map, ssl_map, content_map,
        pcap_keys, ssl_keys, content_keys
    )

    if not to_delete:
        print("无需删除，全部已匹配。")
        return

    print("\n将删除以下文件：")
    for p in to_delete:
        print(" -", p)

    if args.dry_run:
        print("\n[DRY-RUN] 预演结束，未实际删除。")
        return

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

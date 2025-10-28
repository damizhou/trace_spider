#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple
import stat

# ===== 可被外部注入覆盖的默认目录 =====
PCAP_DIR_DEFAULT    = "/netdisk/news_receiver/dailymail.co.uk/pcap"
SSL_DIR_DEFAULT     = "/netdisk/news_receiver/dailymail.co.uk/ssl_key"
CONTENT_DIR_DEFAULT = "/netdisk/news_receiver/dailymail.co.uk/content"
HTML_DIR_DEFAULT    = "/netdisk/news_receiver/dailymail.co.uk/html"
# =====================================

def _list_by_suffix(dir_path: Path, suffix: str) -> Tuple[Dict[str, Path], List[Path]]:
    """
    返回:
      - base_key -> 文件路径 （base_key = 文件名去掉 suffix 后的部分）
      - files: 全部匹配文件列表
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
            base = name[: -len(suffix)]
            res[base] = p
    return res, files

def _gather_maps(
    pcap_dir: Path, ssl_dir: Path, content_dir: Path, html_dir: Path
):
    pcap_map, pcap_files       = _list_by_suffix(pcap_dir,    ".pcap")
    ssl_map, ssl_files         = _list_by_suffix(ssl_dir,     "_ssl_key.log")
    content_map, content_files = _list_by_suffix(content_dir, ".txt")
    html_map, html_files       = _list_by_suffix(html_dir,    ".html")

    pcap_keys: Set[str]    = set(pcap_map.keys())
    ssl_keys: Set[str]     = set(ssl_map.keys())
    content_keys: Set[str] = set(content_map.keys())
    html_keys: Set[str]    = set(html_map.keys())

    return (pcap_map, ssl_map, content_map, html_map,
            pcap_files, ssl_files, content_files, html_files,
            pcap_keys, ssl_keys, content_keys, html_keys)

def decide_deletions_strict_all4(
    pcap_map: Dict[str, Path],
    ssl_map: Dict[str, Path],
    content_map: Dict[str, Path],
    html_map: Dict[str, Path],
    pcap_keys: Set[str],
    ssl_keys: Set[str],
    content_keys: Set[str],
    html_keys: Set[str],
) -> List[Path]:
    """
    严格四件齐全：只保留四个集合的交集 key；对不在交集内的 key，已存在的那些文件全部删除。
    """
    keep = pcap_keys & ssl_keys & content_keys & html_keys
    to_del: List[Path] = []

    for base, p in pcap_map.items():
        if base not in keep: to_del.append(p)
    for base, p in ssl_map.items():
        if base not in keep: to_del.append(p)
    for base, p in content_map.items():
        if base not in keep: to_del.append(p)
    for base, p in html_map.items():
        if base not in keep: to_del.append(p)

    # 去重
    seen, uniq = set(), []
    for p in to_del:
        if p not in seen:
            uniq.append(p); seen.add(p)
    return uniq

def _ensure_writable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        if not (mode & stat.S_IWUSR):
            path.chmod(mode | stat.S_IWUSR)
    except Exception:
        pass

def safe_delete(path: Path) -> Tuple[bool, str | None]:
    try:
        _ensure_writable(path)
        path.unlink(missing_ok=True)
        return True, None
    except FileNotFoundError:
        return True, None
    except PermissionError as e:
        try:
            _ensure_writable(path)
            path.unlink(missing_ok=True)
            return True, None
        except Exception as e2:
            return False, f"PermissionError，chmod后仍失败: {e2}"
    except Exception as e:
        return False, str(e)

def main():
    ap = argparse.ArgumentParser(
        description="清理未成套的 theguardian 文件（严格四件齐全：pcap/ssl/txt/html）。缺一删其余。"
    )
    ap.add_argument("--pcap-dir",    default=PCAP_DIR_DEFAULT,    help="pcap 目录")
    ap.add_argument("--ssl-dir",     default=SSL_DIR_DEFAULT,     help="ssl_key 目录")
    ap.add_argument("--content-dir", default=CONTENT_DIR_DEFAULT, help="content(.txt) 目录")
    ap.add_argument("--html-dir",    default=HTML_DIR_DEFAULT,    help="html(.html) 目录")
    ap.add_argument("--dry-run",     action="store_true",         help="预演：只打印将删除的文件，不实际删除")
    args = ap.parse_args()

    pcap_dir    = Path(args.pcap_dir)
    ssl_dir     = Path(args.ssl_dir)
    content_dir = Path(args.content_dir)
    html_dir    = Path(args.html_dir)

    # 目录存在性不强制：若某目录不存在，等价于该类一个都没有 -> 将删光其它三类（你当前的“缺一删其余”严格语义）
    (pcap_map, ssl_map, content_map, html_map,
     pcap_files, ssl_files, content_files, html_files,
     pcap_keys, ssl_keys, content_keys, html_keys) = _gather_maps(
        pcap_dir, ssl_dir, content_dir, html_dir
    )

    total = len(pcap_files) + len(ssl_files) + len(content_files) + len(html_files)
    print(f"统计：pcap={len(pcap_files)}，ssl={len(ssl_files)}，txt={len(content_files)}，html={len(html_files)}，合计={total}")

    to_delete = decide_deletions_strict_all4(
        pcap_map, ssl_map, content_map, html_map,
        pcap_keys, ssl_keys, content_keys, html_keys
    )

    if not to_delete:
        print("无需删除，全部四件齐全。")
        return

    print("\n将删除以下文件（缺一删其余）：")
    for p in to_delete:
        print(" -", p)

    if args.dry_run:
        print("\n[DRY-RUN] 预演结束，未实际删除。")
        return

    print("\n开始删除 ...")
    ok, fail = 0, 0
    for p in to_delete:
        success, err = safe_delete(p)
        if success:
            ok += 1
        else:
            fail += 1
            print(f"❌ 删除失败: {p}\n   原因: {err}")

    print(f"\n完成。成功删除 {ok} 个，失败 {fail} 个。")

if __name__ == "__main__":
    main()

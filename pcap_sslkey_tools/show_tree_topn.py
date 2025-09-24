#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
show_tree_topn.py — 每一级目录只展示前 N 个条目（可选目录优先、深度限制）。
用法示例：
  python show_tree_topn.py /path/to/dir            # 每级显示 2 个（默认）
  python show_tree_topn.py -n 3 -a --dirs-first .  # 每级 3 个，包含隐藏，目录优先
  python show_tree_topn.py -n 2 -L 2 /var/log      # 深度 2
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
from typing import Iterable, List, Tuple

def list_entries(
    p: Path, include_hidden: bool, dirs_first: bool
) -> List[os.DirEntry]:
    try:
        it = list(os.scandir(p))
    except PermissionError:
        return []
    items = [e for e in it if include_hidden or not e.name.startswith(".")]
    if dirs_first:
        items.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.casefold()))
    else:
        items.sort(key=lambda e: e.name.casefold())
    return items

def print_tree(
    root: Path,
    max_entries: int,
    include_hidden: bool,
    dirs_first: bool,
    max_depth: int | None,
    prefix: str = "",
    level: int = 0,
) -> None:
    if max_depth is not None and level > max_depth:
        return
    entries = list_entries(root, include_hidden, dirs_first)
    if max_depth is not None and level == max_depth:
        # 到达最大深度，只报数量不再下钻
        extra = len(entries)
        if extra:
            print(f"{prefix}└── … (+{extra} more)")
        return

    show = entries[:max_entries]
    extra = len(entries) - len(show)

    for idx, e in enumerate(show):
        is_last = (idx == len(show) - 1) and (extra == 0)
        connector = "└── " if is_last else "├── "
        name = e.name
        try:
            is_dir = e.is_dir(follow_symlinks=False)
        except PermissionError:
            is_dir = False

        # 符号链接标注
        try:
            is_link = e.is_symlink()
        except OSError:
            is_link = False
        label = name + ("/" if is_dir else "")
        if is_link:
            try:
                target = os.readlink(e.path)
                label += f" -> {target}"
            except OSError:
                pass

        print(f"{prefix}{connector}{label}")

        # 下级前缀：保留竖线表示还有同级，或空格表示末尾
        child_prefix = prefix + ("    " if connector.startswith("└") else "│   ")

        if is_dir:
            print_tree(
                Path(e.path),
                max_entries,
                include_hidden,
                dirs_first,
                max_depth,
                prefix=child_prefix,
                level=level + 1,
            )

    if extra > 0:
        # 额外条目提示行，总是作为“末尾”打印
        print(f"{prefix}└── … (+{extra} more)")

def main() -> None:
    ap = argparse.ArgumentParser(
        description="以树形结构展示目录，每一级目录只显示前 N 个条目。"
    )
    ap.add_argument("path", nargs="?", default=".", help="根目录，默认当前目录")
    ap.add_argument("-n", "--max-entries", type=int, default=2, help="每级显示的最大条目数，默认 2")
    ap.add_argument("-a", "--all", action="store_true", help="包含隐藏文件/目录")
    ap.add_argument("--dirs-first", action="store_true", help="目录优先排序")
    ap.add_argument("-L", "--level", type=int, default=None, help="最大深度（根为 0）")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"路径不存在：{root}", file=sys.stderr); sys.exit(1)

    print(root)
    if root.is_dir():
        print_tree(
            root=root,
            max_entries=max(1, args.max_entries),
            include_hidden=args.all,
            dirs_first=args.dirs_first,
            max_depth=args.level,
        )

if __name__ == "__main__":
    main()

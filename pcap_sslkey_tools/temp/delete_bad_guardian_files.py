#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Delete files under /netdisk/theguardian_with_ssl_key whose filename has a
4-character token between the 2nd and 3rd underscore (i.e., the 3rd token).
- Skips any directory named 'theguardian_all_reformat'.
- Dry-run by default; use --apply to actually delete.
"""

from __future__ import annotations
import argparse
import logging
import os
from pathlib import Path
from typing import Iterator

DEFAULT_ROOT = "/netdisk/theguardian_with_ssl_key"
IGNORE_DIR_NAME = "theguardian_all_reformat"

def iter_files(root: Path, ignore_dir: str = IGNORE_DIR_NAME) -> Iterator[Path]:
    """Yield all file paths under root, skipping any subtree named `ignore_dir`."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # Prune ignored directories in-place to avoid descending into them
        dirnames[:] = [d for d in dirnames if d != ignore_dir]
        for fn in filenames:
            yield Path(dirpath) / fn

def third_token_len_is_4(filename: str) -> bool:
    """
    Split basename by '_' and check the 3rd token (index 2).
    Return True if it exists and has length == 4 (e.g., '2006').
    """
    tokens = filename.split("_")
    if len(tokens) < 3:
        return False
    t = tokens[2]
    # 更稳妥地要求是4位数字；如果只需长度==4，把 .isdigit() 去掉
    return len(t) == 4 and t.isdigit()

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete misnamed Guardian files whose 3rd token is 4 chars (year)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(DEFAULT_ROOT),
        help=f"scan root (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete files (omit for dry-run)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="verbose logging",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)

    root: Path = args.root
    if not root.is_dir():
        logging.error("Root path does not exist or is not a directory: %s", root)
        raise SystemExit(2)

    total = 0
    matched = 0
    deleted = 0

    for path in iter_files(root):
        total += 1
        name = path.name
        if third_token_len_is_4(name):
            matched += 1
            if args.apply:
                try:
                    path.unlink()
                    deleted += 1
                    logging.info("DELETED: %s", path)
                except Exception as e:
                    logging.error("Failed to delete %s: %s", path, e)
            else:
                logging.info("[dry-run] would delete: %s", path)

    logging.info("Scanned files: %d", total)
    logging.info("Matched (3rd token len==4): %d", matched)
    if args.apply:
        logging.info("Deleted: %d", deleted)
    else:
        logging.info("No file deleted (dry-run). Use --apply to actually delete.")

if __name__ == "__main__":
    main()

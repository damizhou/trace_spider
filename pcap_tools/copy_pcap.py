#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import concurrent.futures as cf
import shutil
import os
import pwd
from typing import List, Tuple

# ---- 固定规则（按需改动这几项即可） ----
SOURCE_ROOT = Path("/home/pcz")
SOURCE_GLOB = "github_trace_spider*"
MONTH_GLOB  = "202510*"
DEST_ROOT   = Path("/netdisk/github_with_ssl_key/fcr")

# 源子目录 -> 目标叶子目录 映射
MAPPINGS = [
    ("data",    "pcap"),
    ("ssl_key", "ssl_key"),
    ("content", "content"),
    ("html",    "html"),
]

WORKERS   = 16           # 线程数（IO 密集通常 8~32 合理）
FILE_MODE = 0o644
DIR_MODE  = 0o755


def resolve_target_owner() -> Tuple[int, int]:
    """
    返回希望设置给目标文件/目录的 (uid, gid)。
    - 若以 sudo 运行，优先使用 SUDO_UID/SUDO_GID（或 SUDO_USER）。
    - 若以 pkexec 运行，尝试 PKEXEC_UID 推断。
    - 否则使用当前进程的 uid/gid。
    """
    try:
        euid = os.geteuid()
        if euid == 0:
            sudo_uid = os.environ.get("SUDO_UID")
            sudo_gid = os.environ.get("SUDO_GID")
            if sudo_uid and sudo_gid:
                return int(sudo_uid), int(sudo_gid)

            sudo_user = os.environ.get("SUDO_USER")
            if sudo_user:
                pw = pwd.getpwnam(sudo_user)
                return pw.pw_uid, pw.pw_gid

            pk_uid = os.environ.get("PKEXEC_UID")
            if pk_uid:
                uid = int(pk_uid)
                pw = pwd.getpwuid(uid)
                return uid, pw.pw_gid
        # 非 root 或未检测到 sudo/pkexec 情况
        return os.getuid(), os.getgid()
    except Exception:
        # 兜底
        return os.getuid(), os.getgid()


def iter_source_files(src_subdir: str) -> List[Path]:
    """列出指定源子目录下 2025-10 月份 github.com/** 的所有文件。"""
    files: List[Path] = []
    for root in SOURCE_ROOT.glob(SOURCE_GLOB):
        month_base = root / src_subdir
        for month_dir in month_base.glob(MONTH_GLOB):
            gh = month_dir / "github.com"
            if not gh.exists():
                continue
            files.extend([p for p in gh.rglob("*") if p.is_file()])
    return files


def rel_after_github(p: Path) -> Path:
    """返回路径中 github.com/ 之后的相对路径。"""
    parts = p.parts
    try:
        i = parts.index("github.com")
        return Path(*parts[i + 1:])
    except ValueError:
        return Path(p.name)


def ensure_dir(d: Path, uid: int, gid: int) -> None:
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chown(d, uid, gid)
    except PermissionError:
        pass
    try:
        os.chmod(d, DIR_MODE)
    except PermissionError:
        pass


def same_file(src: Path, dst: Path) -> bool:
    """用 size+mtime 粗判是否相同，便于增量跳过。"""
    try:
        s, d = src.stat()
        return s.st_size == d.st_size and int(s.st_mtime) == int(d.st_mtime)
    except FileNotFoundError:
        return False


def copy_one(src: Path, dst_base: Path, uid: int, gid: int) -> Tuple[bool, str]:
    """复制单个文件并修正属主/权限；返回 (是否成功, 简短说明)。"""
    try:
        dst = dst_base / rel_after_github(src)
        ensure_dir(dst.parent, uid, gid)

        if dst.exists() and same_file(src, dst):
            try: os.chown(dst, uid, gid)
            except PermissionError: pass
            try: os.chmod(dst, FILE_MODE)
            except PermissionError: pass
            return True, "skip"

        shutil.copy2(src, dst)  # 保留 mtime
        try: os.chown(dst, uid, gid)
        except PermissionError: pass
        try: os.chmod(dst, FILE_MODE)
        except PermissionError: pass
        return True, "copied"
    except Exception as e:
        return False, f"error:{e}"


def run() -> None:
    uid, gid = resolve_target_owner()
    print(f"target owner uid={uid} gid={gid}")

    # 预建目标根及四个叶子目录
    for _, dest_leaf in MAPPINGS:
        ensure_dir(DEST_ROOT / dest_leaf, uid, gid)

    # 组装全部复制计划
    plan: List[Tuple[Path, Path]] = []
    for src_subdir, dest_leaf in MAPPINGS:
        files = iter_source_files(src_subdir)
        dest_base = DEST_ROOT / dest_leaf
        plan.extend((f, dest_base) for f in files)

    total = len(plan)
    print(f"待处理文件: {total}")

    ok = err = 0
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(copy_one, f, base, uid, gid) for f, base in plan]
        for i, fut in enumerate(cf.as_completed(futures), 1):
            success, msg = fut.result()
            ok += int(success)
            err += int(not success)
            if i % 500 == 0 or not success:
                print(f"[{i}/{total}] {msg}")

    print(f"完成：成功 {ok}，失败 {err}")


if __name__ == "__main__":
    run()

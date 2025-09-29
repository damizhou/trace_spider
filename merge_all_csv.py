# merge_csvs.py
from __future__ import annotations
from pathlib import Path
from typing import List
import pandas as pd
import csv
import auto_spider as autospider
import pcap_sslkey_tools.pipeline_runner as runner

ROOT_DIR_DEFAULT = "/netdisk/theguardian_with_ssl_key"
OUTPUT_CSV_DEFAULT = "theguardian_records.csv"

def _detect_delimiter(fp: Path, sample_size: int = 4096) -> str:
    """自动识别分隔符（逗号/制表符/分号/竖线）。"""
    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
        sample = f.read(sample_size)
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"]).delimiter
    except csv.Error:
        return ","  # 兜底

def _read_one_csv(fp: Path) -> pd.DataFrame:
    delim = _detect_delimiter(fp)
    last_err = None
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin1"):
        try:
            df = pd.read_csv(fp, sep=delim, encoding=enc, dtype=str, keep_default_na=False)
            return df
        except UnicodeDecodeError as e:
            last_err = e
            continue
    # 若编码都不行，抛最后一次错误
    raise last_err if last_err else RuntimeError(f"无法读取: {fp}")

def _normalize_df(df: pd.DataFrame, year: str) -> pd.DataFrame:
    """按你原有列约定，只保留 Section, ID, URL；清理空白并附加 Year 列。"""
    wanted = [c for c in ("Section", "ID", "URL") if c in df.columns]
    if not wanted:
        # 没有任何目标列就跳过
        return pd.DataFrame(columns=["Section", "ID", "URL", "Year"])
    df = df[wanted].copy()

    if "Section" in df.columns:
        df["Section"] = df["Section"].astype(str).str.strip()
    if "URL" in df.columns:
        df["URL"] = df["URL"].astype(str).str.strip()
    if "ID" in df.columns:
        # 先保留原 ID，但后续会重排
        df["ID"] = df["ID"].astype(str).str.strip()

    df["Year"] = str(year)
    # 统一列顺序
    cols = [c for c in ("Section", "ID", "URL", "Year") if c in df.columns] + \
           [c for c in ("Section", "ID", "URL", "Year") if c not in df.columns]
    return df.reindex(columns=["Section", "ID", "URL", "Year"])

def merge_guardian_csvs_all_years(
    root_dir: str = ROOT_DIR_DEFAULT,
    output_csv: str = OUTPUT_CSV_DEFAULT,
) -> tuple[pd.DataFrame, Path]:
    """
    合并 /netdisk/theguardian_with_ssl_key 下各年份目录：
    - 仅在“年份目录中 **不存在** pcap/”时，读取其 theguardian_all_reformat/ 下所有 *.csv
    - 自动识别分隔符与常见编码
    - 只保留列: Section, ID, URL，并添加 Year 列
    - 全局按 URL 去重（保留第一条）
    - 全局按 Section 重新编号 ID 从 1 开始
    - 输出 UTF-8、无索引
    """
    root = Path(root_dir)
    if not root.exists():
        raise FileNotFoundError(f"根目录不存在: {root}")

    dfs: List[pd.DataFrame] = []
    year_dirs = sorted([p for p in root.iterdir() if p.is_dir()])

    total_files = 0
    skipped_years = []
    used_years = []

    for ydir in year_dirs:
        year = ydir.name
        # 跳过非数字年份目录
        if not year.isdigit():
            continue

        # 你的要求：如果年份目录下存在 pcap/，这一年的 theguardian_all_reformat 直接跳过
        if (ydir / "pcap").is_dir():
            skipped_years.append(year)
            continue

        reformat_dir = ydir / "theguardian_all_reformat"
        if not reformat_dir.is_dir():
            continue

        csv_files = sorted(reformat_dir.glob("*.csv"))
        if not csv_files:
            continue

        used_years.append(year)
        for fp in csv_files:
            df = _read_one_csv(fp)
            df = _normalize_df(df, year)
            if not df.empty:
                dfs.append(df)
                total_files += 1

    if not dfs:
        raise FileNotFoundError("没有可合并的 CSV（可能都被 pcap 条件跳过或目录为空）。")

    merged = pd.concat(dfs, ignore_index=True)

    # 按 Section 重排 ID 从 1 开始；若缺失 Section 列，填 'unknown'
    if "Section" not in merged.columns:
        merged["Section"] = "unknown"

    # 分组编号
    def _reindex_ids(grp: pd.DataFrame) -> pd.DataFrame:
        grp = grp.copy()
        grp["ID"] = range(1, len(grp) + 1)
        return grp

    merged = merged.groupby("Section", sort=True, group_keys=False).apply(_reindex_ids)

    # 列顺序固定
    merged = merged.reindex(columns=["Section", "ID", "URL", "Year"])

    # 保存
    out_path = Path(output_csv).resolve()
    merged.to_csv(out_path, index=False, encoding="utf-8")
    print(f"[完成] 写入: {out_path}")
    print(f"[统计] 参与年份: {sorted(set(used_years))}")
    print(f"[统计] 跳过年份(存在 pcap): {sorted(set(skipped_years))}")
    print(f"[统计] 读取文件数: {total_files}, 合并总行数: {len(merged)}")
    return merged, out_path

def main():
    # 默认参数可改
    # merged, csv_path = merge_guardian_csvs_all_years(
    #     root_dir=ROOT_DIR_DEFAULT,
    #     output_csv=OUTPUT_CSV_DEFAULT,
    # )
    # csv_path = r'/home/pcz/code/trace_spider/theguardian_records.csv'
    # if hasattr(autospider, "CSV_PATH"):         autospider.CSV_PATH = f"{csv_path}"
    # autospider.main()
    # index = 0
    if hasattr(autospider, "DEST_ROOT"):     runner.DEST_ROOT = ROOT_DIR_DEFAULT
    pipeline_runner_result = runner.main()
    # while pipeline_runner_result:
    #     index += 1
    #     autospider.main()
    #     pipeline_runner_result = runner.main()
    #     if index >= 5:
    #         print("超过5轮，停止。")
    #         break

if __name__ == "__main__":
    main()


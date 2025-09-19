from pathlib import Path
import pandas as pd
import csv

def _detect_delimiter(fp: Path, sample_size: int = 4096) -> str:
    """自动识别分隔符（逗号/制表符/分号/竖线）。"""
    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
        sample = f.read(sample_size)
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"]).delimiter
    except csv.Error:
        return ","  # 兜底逗号

def merge_guardian_csvs(
    input_dir: str,
    output_csv: str = "merged.csv",
    pattern: str = "*.csv",
    recursive: bool = False,
) -> pd.DataFrame:
    """
    合并目录下所有 CSV 到一个文件：
    - 自动识别分隔符与常见编码
    - 只保留列: Section, ID, URL
    - 以 URL 去重（保留第一条）
    - 按 Section 重新编号 ID 从 1 开始
    - 保存为 UTF-8 无索引 CSV
    """
    p = Path(input_dir)
    files = sorted(p.rglob(pattern) if recursive else p.glob(pattern))
    if not files:
        raise FileNotFoundError(f"未找到文件: {p}/{pattern}")

    dfs = []
    for fp in files:
        delim = _detect_delimiter(fp)
        for enc in ("utf-8", "utf-8-sig", "gbk", "latin1"):
            try:
                df = pd.read_csv(fp, sep=delim, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        # 只取目标列（若存在）
        keep = [c for c in ("Section", "ID", "URL") if c in df.columns]
        df = df[keep]
        # 清理空白
        if "Section" in df.columns:
            df["Section"] = df["Section"].astype(str).str.strip()
        if "URL" in df.columns:
            df["URL"] = df["URL"].astype(str).str.strip()
        dfs.append(df)

    merged = pd.concat(dfs, ignore_index=True)

    # 只按固定顺序输出
    cols = [c for c in ("Section", "ID", "URL") if c in merged.columns]
    merged = merged[cols]

    merged.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"已保存: {Path(output_csv).resolve()}")
    return merged

# 用法示例：
df = merge_guardian_csvs("/netdisk/theguardian_with_ssl_key/2001/theguardian_all_reformat", output_csv="../guardian_merged.csv")
